"""Trained Tier-1 reference QSAR model backend.

Loads model checkpoints produced by the edeon_train orchestrator and executes
high-fidelity, UQ-calibrated, applicability-domain-audited hazard predictions.
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

# Import the shared modeling infrastructure directly
from edeon_train.shared.featurize import featurize_for_baseline, FeatureRegistry
from edeon_train.shared.ensemble import WeightedEnsemble
from edeon_train.shared.conformal import load_calibration
from edeon_train.shared.ad import TrainedTanimotoAD
from edeon_train.shared.chemprop_wrapper import predict_chemprop_ensemble

logger = logging.getLogger("edeon_models.tier1_backend")

class TrainedTier1Backend(ModelBackend):
    """Generic Tier-1 model backend loading checkpoints trained by edeon_train."""
    
    def __init__(self, endpoint: Endpoint, checkpoint_dir: Path):
        self._endpoint = endpoint
        self._dir = Path(checkpoint_dir)
        self._load()

    def _load(self) -> None:
        """Loads all Tier-1 release pack checkpoints from disk."""
        logger.info(f"Loading Tier-1 backend checkpoints for {self._endpoint} from {self._dir}")
        
        # 1. Load Feature Registry
        reg_path = self._dir / "feature_registry.json"
        if not reg_path.exists():
            raise FileNotFoundError(f"Feature registry not found at {reg_path}")
        with open(reg_path, "r") as f:
            self._registry = FeatureRegistry.from_dict(json.load(f))
            
        # 2. Load Weighted Ensemble
        self._ensemble = WeightedEnsemble.load(str(self._dir))
        
        # 3. Load Conformal Calibrators
        cal_path = self._dir / "calibration.npz"
        if not cal_path.exists():
            raise FileNotFoundError(f"Conformal calibration NPZ not found at {cal_path}")
        self._split_cal, self._var_cal = load_calibration(str(cal_path))
        
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
        
        # Extract endpoint units
        meta = endpoint_metadata(self._endpoint)
        self._units = meta.get("units", "mg/L")
        
        logger.info(f"Successfully loaded Tier-1 backend: {self.model_id()}")

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
            
        # Standardize SMILES
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
        """Runs Tier-1 high-fidelity hazard predictions on a batch of SMILES.
        
        Args:
            smiles: List of query SMILES strings.
            conditions: Optional query conditions.
            
        Returns:
            List of Pydantic Prediction objects with calibrated CIs, AD, and provenance logs.
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
                
        # Prepare baseline features and predictions arrays
        y_pred_log = np.full(n_compounds, np.nan)
        y_low_log = np.full(n_compounds, np.nan)
        y_high_log = np.full(n_compounds, np.nan)
        chem_std = np.zeros(n_compounds)
        
        # 2. Run model predictions on valid structures
        if valid_indices:
            if self._endpoint == Endpoint.SOIL_KOC:
                # Compute ionizable_flags dynamically
                from rdkit import Chem
                acid_patterns = [
                    Chem.MolFromSmarts("[CX3](=O)[OX2H1]"),  # Carboxylic acid
                    Chem.MolFromSmarts("[OX2H1]-c"),         # Phenol
                    Chem.MolFromSmarts("[SX4](=O)(=O)[NX3H1]") # Sulfonamide
                ]
                base_pattern = Chem.MolFromSmarts("[NX3;H2,H1,H0;!$(N[C,S,P]=O)]") # Aliphatic amine
                
                ionizable_flags = []
                for s in clean_smiles:
                    is_ion = 0
                    if s:
                        try:
                            mol = Chem.MolFromSmiles(s)
                            if mol is not None:
                                is_acid = any(mol.HasSubstructMatch(pat) for pat in acid_patterns)
                                is_base = mol.HasSubstructMatch(base_pattern)
                                if is_acid or is_base:
                                    is_ion = 1
                        except Exception:
                            pass
                    ionizable_flags.append(is_ion)
                
                # Featurize baseline features with ionizable flags
                X_valid = featurize_for_baseline(clean_smiles, self._registry.descriptors_selected, ionizable_flags=ionizable_flags)
                x_d_list = [np.array([float(val)]) for val in ionizable_flags]
            else:
                # Featurize baseline features without extra features
                X_valid = featurize_for_baseline(clean_smiles, self._registry.descriptors_selected)
                x_d_list = None
            
            # Weighted Ensemble predict
            y_pred_log = self._ensemble.predict(clean_smiles, X_valid, x_d=x_d_list)
            
            # Predict Chemprop ensemble uncertainty for relative conformal CI scaling
            if "chemprop" in self._ensemble.weights and self._ensemble.weights["chemprop"] > 0:
                _, chem_std = predict_chemprop_ensemble(clean_smiles, str(self._dir / "chemprop"), x_d=x_d_list)
                
        # 3. Apply Conformal Intervals
        use_variance_scaled = "chemprop" in self._ensemble.weights and self._ensemble.weights["chemprop"] > 0
        if use_variance_scaled:
            y_low_log, y_high_log = self._var_cal.interval(y_pred_log, chem_std)
            conformal_method = "ensemble_variance_scaled"
            conformal_quantile = self._var_cal.quantile_
        else:
            y_low_log, y_high_log = self._split_cal.interval(y_pred_log)
            conformal_method = "split_conformal"
            conformal_quantile = self._split_cal.quantile_
            
        # 4. Applicability Domain Check
        ad_results = self._ad.score(clean_smiles)
        
        # 5. Build Prediction objects with back-transformation (10^val)
        for idx in range(n_compounds):
            smi_orig = smiles[idx]
            
            if idx in invalid_indices:
                predictions.append(Prediction(
                    smiles=smi_orig,
                    endpoint=self._endpoint.value,
                    value=PredictionValue(kind="numeric", numeric=None),
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
                
            pred_log = y_pred_log[idx]
            low_log = y_low_log[idx]
            high_log = y_high_log[idx]
            
            # Back-transform from log10 to native units
            pred_native = 10.0 ** pred_log
            low_native = 10.0 ** low_log
            high_native = 10.0 ** high_log
            
            status, mean_dist = ad_results[idx]
            
            # Build detailed provenance dictionary
            provenance = {
                "model_id": self.model_id(),
                "model_version": self.version(),
                "ensemble_weights": self._ensemble.weights,
                "ad_nn_distance": mean_dist,
                "conformal_method": conformal_method,
                "conformal_quantile": conformal_quantile,
                "split_alpha": self._split_cal.alpha,
                "prediction_log": pred_log,
                "ci_lower_log": low_log,
                "ci_upper_log": high_log,
                "chemprop_std": chem_std[idx] if use_variance_scaled else None,
                "experimental_values": []  # Empty placeholder to be enriched by Group D overlay
            }
            
            predictions.append(Prediction(
                smiles=clean_smiles[idx],
                endpoint=self._endpoint.value,
                value=PredictionValue(kind="numeric", numeric=float(pred_native)),
                ci_lower=float(low_native),
                ci_upper=float(high_native),
                ci_level=0.95,
                ad_status=status,
                ad_score=mean_dist,
                units=self._units,
                model_id=self.model_id(),
                model_version=self.version(),
                tier=1,
                provenance=provenance,
                warnings=[]
            ))
            
        return predictions

    def metadata(self) -> ModelCard:
        return self._card
