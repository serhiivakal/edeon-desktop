"""Heteroscedastic mean-variance Tier-1 reference QSAR model backend.

Loads MLP and Chemprop MVE checkpoints for Soil DT50 reference model,
combines predictions using mixture-of-Gaussians, calibrates variance using
the fitted post-hoc VarianceScaler, and outputs predictions with 95% credible intervals.
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

# Import shared modeling infrastructure
from edeon_train.shared.featurize import featurize_for_baseline, FeatureRegistry
from edeon_train.shared.ad import TrainedTanimotoAD
from edeon_train.shared.heteroscedastic import predict_heteroscedastic_ensemble
from edeon_train.shared.chemprop_wrapper import predict_chemprop_mve_ensemble

logger = logging.getLogger("edeon_models.heteroscedastic_backend")

class HeteroscedasticTier1Backend(ModelBackend):
    """Tier-1 reference model backend for heteroscedastic mean-variance predictions."""
    
    def __init__(self, endpoint: Endpoint, checkpoint_dir: Path):
        self._endpoint = endpoint
        self._dir = Path(checkpoint_dir)
        self._load()

    def _load(self) -> None:
        """Loads all checkpoints and parameters from disk."""
        logger.info(f"Loading Heteroscedastic Tier-1 backend for {self._endpoint} from {self._dir}")
        
        # 1. Load Feature Registry
        reg_path = self._dir / "feature_registry.json"
        if not reg_path.exists():
            raise FileNotFoundError(f"Feature registry not found at {reg_path}")
        with open(reg_path, "r") as f:
            self._registry = FeatureRegistry.from_dict(json.load(f))
            
        # 2. Load Variance Scaler Calibration factor
        cal_path = self._dir / "nll_calibration.npz"
        if not cal_path.exists():
            raise FileNotFoundError(f"Variance calibration NPZ not found at {cal_path}")
        cal_data = np.load(cal_path)
        self._scale = float(cal_data["scale"])
        
        # 3. Load MLP HPO config to get structure details
        hmlp_config_path = self._dir / "hmlp_hpo_config.yaml"
        if hmlp_config_path.exists():
            with open(hmlp_config_path, "r") as f:
                self._hmlp_cfg = yaml.safe_load(f)
        else:
            self._hmlp_cfg = {"hidden_dim": 512, "depth": 3}
            
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
        self._units = meta.get("units", "days")
        
        logger.info(f"Successfully loaded Heteroscedastic Tier-1 backend: {self.model_id()}")

    def endpoint(self) -> Endpoint:
        return self._endpoint

    def tier(self) -> int:
        return 1

    def version(self) -> str:
        return self._card.version

    def applicability_domain(self, smiles: List[str]) -> List[ADStatus]:
        """Returns applicability domain status for a list of SMILES."""
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
        """Runs Tier-1 heteroscedastic hazard predictions on a batch of SMILES.
        
        Combines 5-seed MLP and 5-seed Chemprop MVE models.
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
                
        # Initialize prediction arrays
        y_pred_log = np.full(n_compounds, np.nan)
        y_low_log = np.full(n_compounds, np.nan)
        y_high_log = np.full(n_compounds, np.nan)
        
        vars_aleatoric = np.full(n_compounds, np.nan)
        vars_epistemic = np.full(n_compounds, np.nan)
        vars_total = np.full(n_compounds, np.nan)
        
        # 2. Run model predictions on valid structures
        if valid_indices:
            # Featurize baseline features without extra features
            X_valid = featurize_for_baseline(clean_smiles, self._registry.descriptors_selected)
            feature_dim = X_valid.shape[1]
            
            # Predict Heteroscedastic MLP ensemble
            mu_mlp, var_mlp, var_mlp_epistemic, var_mlp_aleatoric = predict_heteroscedastic_ensemble(
                X_valid, self._dir / "hmlp", feature_dim, self._hmlp_cfg
            )
            
            # Predict Chemprop MVE ensemble
            mu_mve, var_mve, var_mve_epistemic, var_mve_aleatoric = predict_chemprop_mve_ensemble(
                clean_smiles, str(self._dir / "chemprop_mve")
            )
            
            # Mixture of Gaussians combination
            y_pred_log = 0.5 * (mu_mlp + mu_mve)
            var_aleatoric = 0.5 * (var_mlp_aleatoric + var_mve_aleatoric)
            var_epistemic = 0.5 * (var_mlp_epistemic + var_mve_epistemic) + 0.25 * (mu_mlp - mu_mve)**2
            var_combined = var_aleatoric + var_epistemic
            
            # Apply variance scaling
            var_calibrated = var_combined * self._scale
            sigma_calibrated = np.sqrt(var_calibrated)
            
            # 95% Credible Interval (conformal-style)
            # z = 1.96 (or norm.ppf(0.975))
            z = 1.9599639845400542
            y_low_log = y_pred_log - z * sigma_calibrated
            y_high_log = y_pred_log + z * sigma_calibrated
            
            vars_aleatoric = var_aleatoric
            vars_epistemic = var_epistemic
            vars_total = var_calibrated
            
        # 3. Applicability Domain Check
        ad_results = self._ad.score(clean_smiles)
        
        # 4. Build Prediction objects with back-transformation (10^val)
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
            
            # Back-transform from log10 to native units (days)
            pred_native = 10.0 ** pred_log
            low_native = 10.0 ** low_log
            high_native = 10.0 ** high_log
            
            status, mean_dist = ad_results[idx]
            
            # Build detailed provenance dictionary for heteroscedastic model
            provenance = {
                "model_id": self.model_id(),
                "model_version": self.version(),
                "ad_nn_distance": mean_dist,
                "conformal_method": "heteroscedastic_mixture",
                "conformal_quantile": 1.96,
                "scale": self._scale,
                "prediction_log": float(pred_log),
                "ci_lower_log": float(low_log),
                "ci_upper_log": float(high_log),
                "variance_aleatoric": float(vars_aleatoric[idx]),
                "variance_epistemic": float(vars_epistemic[idx]),
                "variance_total": float(vars_total[idx]),
                "experimental_values": []
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
