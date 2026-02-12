"""Trained Tier-1 binary classification QSAR model backend.

Loads classification model checkpoints produced by the edeon_train orchestrator
and executes binary hazard predictions with calibrated probabilities,
inductive conformal prediction sets, and applicability domain auditing.
"""

import os
import yaml
import json
import logging
import numpy as np
from pathlib import Path
from typing import List, Optional, Tuple, Any

from edeon_models.backend import ModelBackend
from edeon_models.types import Prediction, PredictionValue, ADStatus, ModelCard
from edeon_models.endpoints import Endpoint, endpoint_metadata
from edeon_engine.standardize import standardize_batch

# Import the shared modeling infrastructure
from edeon_train.shared.featurize import featurize_for_baseline, FeatureRegistry
from edeon_train.shared.ensemble import WeightedEnsemble
from edeon_train.shared.conformal import load_classification_calibration
from edeon_train.shared.ad import TrainedTanimotoAD

logger = logging.getLogger("edeon_models.classification_backend")


class TrainedClassificationTier1Backend(ModelBackend):
    """Tier-1 backend for binary classification endpoints.
    
    Supports bee_acute_oral_ld50, bee_acute_contact_ld50, fish_acute_lc50,
    algae_growth_ec50, and bird_acute_oral_ld50 — endpoints where regression
    R² < 0.5 and toxic/nontoxic classification is the preferred prediction mode.
    """
    
    def __init__(self, endpoint: Endpoint, checkpoint_dir: Path):
        self._endpoint = endpoint
        self._dir = Path(checkpoint_dir)
        self._load()

    def _load(self) -> None:
        """Loads all Tier-1 classification checkpoints from disk."""
        logger.info(f"Loading Tier-1 classification backend for {self._endpoint} from {self._dir}")
        
        # 1. Load Feature Registry
        reg_path = self._dir / "feature_registry.json"
        if not reg_path.exists():
            raise FileNotFoundError(f"Feature registry not found at {reg_path}")
        with open(reg_path, "r") as f:
            self._registry = FeatureRegistry.from_dict(json.load(f))
            
        # 2. Load Weighted Ensemble (with task_kind="classification")
        self._ensemble = WeightedEnsemble.load(str(self._dir))
        assert self._ensemble.task_kind == "classification", \
            f"Expected classification ensemble, got {self._ensemble.task_kind}"
        
        # 3. Load InductiveConformalClassifier
        cal_path = self._dir / "calibration.npz"
        if not cal_path.exists():
            raise FileNotFoundError(f"Classification calibration NPZ not found at {cal_path}")
        self._conformal = load_classification_calibration(str(cal_path))
        
        # 4. Load Applicability Domain
        ad_path = self._dir / "ad_fingerprints.npz"
        if not ad_path.exists():
            raise FileNotFoundError(f"AD fingerprints NPZ not found at {ad_path}")
        self._ad = TrainedTanimotoAD.load(str(ad_path))
        
        # 5. Load ModelCard
        card_path = self._dir / "model_card.yaml"
        if not card_path.exists():
            raise FileNotFoundError(f"ModelCard YAML not found at {card_path}")
        with open(card_path, "r") as f:
            card_data = yaml.safe_load(f)
        self._card = ModelCard.model_validate(card_data)
        
        # Check for low AUC-ROC performance (< 0.70)
        self._model_warnings = []
        if self._card.performance and self._card.performance.metrics:
            auc = self._card.performance.metrics.get("auc_roc")
            if auc is not None and auc < 0.700:
                self._model_warnings.append(
                    f"Risky model: Low generalization performance on scaffold splits (AUC-ROC = {auc:.3f} < 0.700). Use with caution."
                )
        
        # Extract endpoint units
        meta = endpoint_metadata(self._endpoint)
        self._units = meta.get("units", "mg/L")
        
        logger.info(f"Successfully loaded Tier-1 classification backend: {self.model_id()}")

    def endpoint(self) -> Endpoint:
        return self._endpoint

    def tier(self) -> int:
        return 1

    def version(self) -> str:
        return self._card.version

    def applicability_domain(self, smiles: List[str]) -> List[ADStatus]:
        """Returns the applicability domain status for a list of SMILES strings."""
        if not smiles:
            return []
            
        std_results = standardize_batch(smiles)
        clean_smiles = []
        for r in std_results:
            if r["valid"] and r["canonical"] is not None:
                clean_smiles.append(r["canonical"])
            else:
                clean_smiles.append("")
                
        ad_results = self._ad.score(clean_smiles)
        return [r[0] for r in ad_results]

    def predict(self, smiles: List[str], conditions: Optional[dict] = None) -> List[Prediction]:
        """Runs Tier-1 binary classification predictions on a batch of SMILES.
        
        Args:
            smiles: List of query SMILES strings.
            conditions: Optional query conditions.
            
        Returns:
            List of Prediction objects with:
            - value.kind = "binary", value.binary = True (toxic) or False (nontoxic)
            - provenance includes: raw_probability, calibrated_probability,
              prediction_set, ensemble_std
        """
        if not smiles:
            return []
            
        n_compounds = len(smiles)
        predictions = []
        
        # 1. SMILES Standardization
        std_results = standardize_batch(smiles)
        clean_smiles = []
        valid_indices = []
        invalid_indices = []
        
        for idx, r in enumerate(std_results):
            if r["valid"] and r["canonical"] is not None:
                clean_smiles.append(r["canonical"])
                valid_indices.append(idx)
            else:
                clean_smiles.append("")
                invalid_indices.append(idx)
                
        # Prepare probability arrays
        y_proba = np.full(n_compounds, np.nan)
        
        # 2. Run model predictions on valid structures
        if valid_indices:
            X_valid = featurize_for_baseline(clean_smiles, self._registry.descriptors_selected)
            y_proba = self._ensemble.predict_proba(clean_smiles, X_valid)
                
        # 3. Apply Conformal Prediction Sets
        prediction_sets = [set()] * n_compounds
        if self._conformal is not None and not np.all(np.isnan(y_proba)):
            # Only compute for non-NaN entries
            valid_mask = ~np.isnan(y_proba)
            if np.any(valid_mask):
                valid_proba = y_proba[valid_mask]
                valid_sets = self._conformal.predict_set(valid_proba)
                j = 0
                prediction_sets_new = []
                for i in range(n_compounds):
                    if valid_mask[i]:
                        prediction_sets_new.append(valid_sets[j])
                        j += 1
                    else:
                        prediction_sets_new.append(set())
                prediction_sets = prediction_sets_new
            
        # 4. Applicability Domain Check
        ad_results = self._ad.score(clean_smiles)
        
        # 5. Build Prediction objects
        for idx in range(n_compounds):
            smi_orig = smiles[idx]
            
            if idx in invalid_indices:
                predictions.append(Prediction(
                    smiles=smi_orig,
                    endpoint=self._endpoint.value,
                    value=PredictionValue(kind="binary", binary=None),
                    ci_lower=None,
                    ci_upper=None,
                    ad_status=ADStatus.UNKNOWN,
                    ad_score=None,
                    units=self._units,
                    model_id=self.model_id(),
                    model_version=self.version(),
                    tier=1,
                    warnings=["parse_failed"]
                ))
                continue
                
            prob = y_proba[idx]
            is_toxic = bool(prob >= 0.5)
            status, mean_dist = ad_results[idx]
            pred_set = prediction_sets[idx]
            
            # Determine conformal uncertainty level
            if len(pred_set) == 2:
                uncertainty_note = "uncertain (both classes in prediction set)"
            elif len(pred_set) == 0:
                uncertainty_note = "extreme (empty prediction set)"
            else:
                uncertainty_note = "confident"
            
            provenance = {
                "model_id": self.model_id(),
                "model_version": self.version(),
                "task_kind": "classification",
                "ensemble_weights": self._ensemble.weights,
                "ad_nn_distance": mean_dist,
                "raw_probability": float(prob),
                "prediction_set": list(pred_set),
                "conformal_alpha": self._conformal.alpha if self._conformal else None,
                "conformal_quantile": self._conformal.quantile_ if self._conformal else None,
                "uncertainty_note": uncertainty_note,
                "experimental_values": []
            }
            
            predictions.append(Prediction(
                smiles=clean_smiles[idx],
                endpoint=self._endpoint.value,
                value=PredictionValue(kind="binary", binary=is_toxic),
                ci_lower=float(prob),   # Store probability as ci_lower
                ci_upper=float(prob),   # and ci_upper for frontend display
                ci_level=0.95,
                ad_status=status,
                ad_score=mean_dist,
                units=self._units,
                model_id=self.model_id(),
                model_version=self.version(),
                tier=1,
                provenance=provenance,
                warnings=list(self._model_warnings)
            ))
            
        return predictions

    def metadata(self) -> ModelCard:
        return self._card
