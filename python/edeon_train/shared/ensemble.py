"""Weighted ensemble combination module for Edeon Phase 2.

Combines baseline Random Forest, XGBoost, and Chemprop ensemble predictions
using weights derived from inverse cross-validation error.

For regression: weights from inverse CV RMSE.
For classification: weights from inverse CV log-loss (or direct balanced accuracy).
"""

import os
import logging
import yaml
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from sklearn.base import BaseEstimator
from edeon_train.shared.baselines import load_baseline_checkpoint
from edeon_train.shared.chemprop_wrapper import predict_chemprop_ensemble

logger = logging.getLogger("edeon_train.ensemble")

class WeightedEnsemble:
    """Ensemble model that combines RF, XGBoost, and Chemprop predictions.
    
    For regression: weights by inverse CV RMSE, predict() returns values.
    For classification: weights by CV balanced accuracy, predict() returns probabilities.
    """
    def __init__(
        self,
        weights: Dict[str, float],
        rf_model: Optional[BaseEstimator] = None,
        xgb_model: Optional[BaseEstimator] = None,
        chemprop_dir: Optional[str] = None,
        task_kind: str = "regression"
    ):
        self.weights = weights
        self.rf_model = rf_model
        self.xgb_model = xgb_model
        self.chemprop_dir = chemprop_dir
        self.task_kind = task_kind
        
        # Normalize weights to sum to 1.0
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in self.weights.items()}
        else:
            self.weights = {}
            
        logger.info(f"WeightedEnsemble ({task_kind}) initialized with normalized weights: {self.weights}")

    @classmethod
    def from_cv_metrics(
        cls,
        cv_scores: Dict[str, float],
        task_kind: str = "regression"
    ) -> "WeightedEnsemble":
        """Calculates normalized weights from cross-validation scores.
        
        For regression: uses inverse RMSE weighting.
        For classification: uses balanced accuracy directly as weight.
        """
        raw_weights = {}
        
        if task_kind == "classification":
            # For classification, cv_scores are balanced accuracy (higher = better)
            best_baseline_ba = max(
                cv_scores.get("rf", 0.0) or 0.0,
                cv_scores.get("xgb", 0.0) or 0.0
            )
            for name, ba in cv_scores.items():
                if ba is None or np.isnan(ba):
                    continue
                # Drop Chemprop if it's significantly worse (< 0.5 * best baseline)
                if name == "chemprop" and best_baseline_ba > 0 and ba < 0.5 * best_baseline_ba:
                    logger.warning(
                        f"Chemprop BA ({ba:.4f}) is less than half the best baseline BA "
                        f"({best_baseline_ba:.4f}). Dropping from ensemble."
                    )
                    continue
                # Use balanced accuracy as weight (higher = better)
                raw_weights[name] = max(ba - 0.5, 0.001)  # subtract chance level
        else:
            # Regression: inverse RMSE weighting
            baselines = [cv_scores.get("rf", float("inf")), cv_scores.get("xgb", float("inf"))]
            best_baseline_rmse = min(baselines)
            
            for name, rmse in cv_scores.items():
                if rmse is None or np.isnan(rmse) or rmse == float("inf"):
                    continue
                if name == "chemprop" and best_baseline_rmse < float("inf") and rmse > 2.0 * best_baseline_rmse:
                    logger.warning(
                        f"Chemprop CV RMSE ({rmse:.4f}) is more than 2x the best baseline RMSE "
                        f"({best_baseline_rmse:.4f}). Dropping Chemprop from the deployed ensemble."
                    )
                    continue
                raw_weights[name] = 1.0 / max(rmse, 1e-6)
            
        return cls(weights=raw_weights, task_kind=task_kind)

    def predict(self, smiles: List[str], features: np.ndarray, x_d: Optional[List[np.ndarray]] = None) -> np.ndarray:
        """Computes weighted average prediction across all active members.
        
        For regression, returns point estimates.
        For classification, returns weighted-mean probabilities for class 1 (toxic).
        
        Returns:
            np.ndarray of shape (n_compounds).
        """
        n_compounds = len(smiles)
        if n_compounds == 0:
            return np.zeros(0)
            
        accumulated_preds = np.zeros(n_compounds)
        active_weight_sum = 0.0
        
        # 1. Random Forest prediction
        if "rf" in self.weights and self.weights["rf"] > 0:
            if self.rf_model is None:
                raise ValueError("Random Forest weight > 0 but model is not loaded!")
            rf_preds = np.full(n_compounds, np.nan)
            valid_mask = ~np.isnan(features).any(axis=1)
            if np.any(valid_mask):
                if self.task_kind == "classification" and hasattr(self.rf_model, 'predict_proba'):
                    rf_preds[valid_mask] = self.rf_model.predict_proba(features[valid_mask])[:, 1]
                else:
                    rf_preds[valid_mask] = self.rf_model.predict(features[valid_mask])
            accumulated_preds = np.nansum([accumulated_preds, self.weights["rf"] * rf_preds], axis=0)
            active_weight_sum += self.weights["rf"]
            
        # 2. XGBoost prediction
        if "xgb" in self.weights and self.weights["xgb"] > 0:
            if self.xgb_model is None:
                raise ValueError("XGBoost weight > 0 but model is not loaded!")
            xgb_preds = np.full(n_compounds, np.nan)
            valid_mask = ~np.isnan(features).any(axis=1)
            if np.any(valid_mask):
                if self.task_kind == "classification" and hasattr(self.xgb_model, 'predict_proba'):
                    xgb_preds[valid_mask] = self.xgb_model.predict_proba(features[valid_mask])[:, 1]
                else:
                    xgb_preds[valid_mask] = self.xgb_model.predict(features[valid_mask])
            accumulated_preds = np.nansum([accumulated_preds, self.weights["xgb"] * xgb_preds], axis=0)
            active_weight_sum += self.weights["xgb"]
            
        # 3. Chemprop prediction
        if "chemprop" in self.weights and self.weights["chemprop"] > 0:
            if self.chemprop_dir is None:
                raise ValueError("Chemprop weight > 0 but checkpoint directory is not configured!")
            chem_preds, _ = predict_chemprop_ensemble(
                smiles, self.chemprop_dir,
                task_kind=self.task_kind,
                x_d=x_d
            )
            accumulated_preds = np.nansum([accumulated_preds, self.weights["chemprop"] * chem_preds], axis=0)
            active_weight_sum += self.weights["chemprop"]
            
        # Standardize parse failures as NaNs
        # (A compound is invalid if both Morgan/Descriptor features and Chemprop predicted NaNs)
        invalid_mask = np.isnan(features).any(axis=1)
        accumulated_preds[invalid_mask] = np.nan
        
        return accumulated_preds

    def predict_proba(self, smiles: List[str], features: np.ndarray, x_d: Optional[List[np.ndarray]] = None) -> np.ndarray:
        """Returns ensemble probability for class 1 (toxic). Only for classification."""
        if self.task_kind != "classification":
            raise RuntimeError("predict_proba is only available for classification ensembles")
        return self.predict(smiles, features, x_d=x_d)

    def save(self, path: str) -> None:
        """Saves weights dictionary and task_kind to an ensemble_weights.yaml file."""
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        save_dict = {"task_kind": self.task_kind, **self.weights}
        with open(path, "w") as f:
            yaml.dump(save_dict, f, default_flow_style=False)
        logger.info(f"Saved ensemble weights ({self.task_kind}) to {path}")

    @classmethod
    def load(cls, checkpoint_dir: str) -> "WeightedEnsemble":
        """Loads and reconstructs the ensemble model from a checkpoint directory."""
        weights_path = os.path.join(checkpoint_dir, "ensemble_weights.yaml")
        if not os.path.exists(weights_path):
            raise FileNotFoundError(f"Ensemble weights yaml not found at {weights_path}")
            
        with open(weights_path, "r") as f:
            data = yaml.safe_load(f)
        
        # Extract task_kind from saved data, default to regression for backwards compat
        task_kind = data.pop("task_kind", "regression")
        weights = data
            
        rf_model = None
        if weights.get("rf", 0.0) > 0:
            rf_model, _ = load_baseline_checkpoint(os.path.join(checkpoint_dir, "baselines"), "rf")
            
        xgb_model = None
        if weights.get("xgb", 0.0) > 0:
            xgb_model, _ = load_baseline_checkpoint(os.path.join(checkpoint_dir, "baselines"), "xgb")
            
        chemprop_dir = None
        if weights.get("chemprop", 0.0) > 0:
            chemprop_dir = os.path.join(checkpoint_dir, "chemprop")
            
        return cls(
            weights=weights,
            rf_model=rf_model,
            xgb_model=xgb_model,
            chemprop_dir=chemprop_dir,
            task_kind=task_kind
        )
