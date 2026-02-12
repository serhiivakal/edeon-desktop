"""
Edeon Engine — Uncertainty Quantification (UQ) and Applicability Domain (AD)

Provides split-conformal prediction intervals for regression, Venn-Abers
probability calibration for classification, and Tanimoto k-NN applicability
domain checks.
"""

import numpy as np
from typing import Optional, Union, Dict, Any, List

try:
    from sklearn.isotonic import IsotonicRegression
    from sklearn.ensemble import RandomForestRegressor
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit import DataStructs


class ConformalRegressor:
    """
    Inductive Split Conformal prediction wrapper for regression.
    Supports constant-width and adaptive (normalized) prediction intervals.
    """

    def __init__(self, coverage: float = 0.90):
        self.coverage = coverage
        self.alpha = 1.0 - coverage
        self.quantile: Optional[float] = None
        self.use_adaptive = False
        self.difficulty_model: Optional[Any] = None

    def fit(self, X_train: np.ndarray, y_train: np.ndarray,
            X_calib: np.ndarray, y_calib: np.ndarray,
            base_model: Any, use_adaptive: bool = True) -> "ConformalRegressor":
        """
        Calibrate the conformal regressor on a held-out calibration set.
        """
        self.use_adaptive = use_adaptive
        y_calib_pred = base_model.predict(X_calib)
        abs_residuals = np.abs(np.array(y_calib) - np.array(y_calib_pred))
        n_cal = len(abs_residuals)

        if n_cal == 0:
            raise ValueError("Calibration set cannot be empty.")

        if use_adaptive and HAS_SKLEARN:
            # Fit difficulty model on training absolute residuals
            y_train_pred = base_model.predict(X_train)
            train_abs_residuals = np.abs(np.array(y_train) - np.array(y_train_pred))
            
            diff_model = RandomForestRegressor(n_estimators=50, max_depth=5, random_state=42)
            diff_model.fit(X_train, train_abs_residuals)
            self.difficulty_model = diff_model

            # Calculate calibration set difficulties
            sigmas = diff_model.predict(X_calib)
            sigmas = np.maximum(sigmas, 1e-4)  # Avoid zero division
            
            nonconformity_scores = abs_residuals / sigmas
        else:
            self.use_adaptive = False
            nonconformity_scores = abs_residuals

        # Quantile calculation with finite sample correction
        q_level = np.ceil((n_cal + 1) * (1 - self.alpha)) / n_cal
        q_level = min(1.0, max(0.0, q_level))
        self.quantile = float(np.quantile(nonconformity_scores, q_level))

        return self

    def predict_intervals(self, X_test: np.ndarray, y_pred: np.ndarray) -> List[tuple[float, float]]:
        """
        Compute prediction intervals for a test set.
        Returns list of (lower, upper) bounds.
        """
        if self.quantile is None:
            raise RuntimeError("ConformalRegressor has not been fitted/calibrated.")

        if self.use_adaptive and self.difficulty_model is not None:
            sigmas = self.difficulty_model.predict(X_test)
            sigmas = np.maximum(sigmas, 1e-4)
            widths = self.quantile * sigmas
        else:
            widths = np.full(len(X_test), self.quantile)

        intervals = []
        for yp, w in zip(y_pred, widths):
            intervals.append((float(yp - w), float(yp + w)))
        return intervals


class VennAbersCalibrator:
    """
    Inductive Venn-Abers calibrator for binary classification.
    Calibrates probabilities and provides bounds [p0, p1].
    """

    def __init__(self):
        self.cal_scores: np.ndarray = np.array([])
        self.cal_labels: np.ndarray = np.array([])

    def fit(self, cal_scores: Union[List[float], np.ndarray],
            cal_labels: Union[List[int], np.ndarray]) -> "VennAbersCalibrator":
        """
        Set the calibration scores and labels.
        """
        self.cal_scores = np.asarray(cal_scores)
        self.cal_labels = np.asarray(cal_labels)
        return self

    def predict_calibrated(self, test_scores: Union[List[float], np.ndarray]) -> tuple[List[float], List[tuple[float, float]]]:
        """
        Calibrate test scores.
        Returns:
          calibrated_probs: List[float]
          intervals: List[tuple[float, float]] of (p0, p1) bounds
        """
        if not HAS_SKLEARN:
            # Fallback if scikit-learn is not present
            return list(test_scores), [(float(s), float(s)) for s in test_scores]

        calibrated_probs = []
        intervals = []

        for ts in test_scores:
            # 1. Hypothesis y = 0
            scores_0 = np.append(self.cal_scores, ts)
            labels_0 = np.append(self.cal_labels, 0)
            ir_0 = IsotonicRegression(out_of_bounds="clip")
            ir_0.fit(scores_0, labels_0)
            p0 = float(ir_0.predict([ts])[0])

            # 2. Hypothesis y = 1
            scores_1 = np.append(self.cal_scores, ts)
            labels_1 = np.append(self.cal_labels, 1)
            ir_1 = IsotonicRegression(out_of_bounds="clip")
            ir_1.fit(scores_1, labels_1)
            p1 = float(ir_1.predict([ts])[0])

            denom = 1.0 - p0 + p1
            p_cal = p1 / denom if denom > 0 else (p0 + p1) / 2.0
            
            # Bound and clip to [0, 1] range
            p_cal = max(0.0, min(1.0, p_cal))
            p0 = max(0.0, min(1.0, p0))
            p1 = max(0.0, min(1.0, p1))

            calibrated_probs.append(p_cal)
            intervals.append((p0, p1))

        return calibrated_probs, intervals


def conformalize_regression(model: Any, X_train: np.ndarray, y_train: np.ndarray,
                           X_calib: np.ndarray, y_calib: np.ndarray,
                           coverage: float = 0.90, use_adaptive: bool = True) -> ConformalRegressor:
    """
    Helper to initialize and fit a ConformalRegressor.
    """
    regressor = ConformalRegressor(coverage=coverage)
    regressor.fit(X_train, y_train, X_calib, y_calib, model, use_adaptive=use_adaptive)
    return regressor


def get_tanimoto_ad_envelope(query_smiles: list[str], train_smiles: list[str], k: int = 5, percentile: float = 95.0) -> list[dict]:
    """
    Computes Tanimoto AD check bounds directly using rdkit.
    """
    from edeon_engine.applicability.tanimoto import build_tanimoto_reference, score_tanimoto
    ref = build_tanimoto_reference(train_smiles, k=k, percentile=percentile)
    scores = score_tanimoto(ref, query_smiles)
    
    envelopes = []
    n = len(query_smiles)
    for i in range(n):
        status = scores["status"][i]
        # Map back to standard front-end statuses
        ad_status = "in_domain" if status == "in" else "borderline" if status == "borderline" else "out_of_domain" if status == "out" else "unknown"
        
        dist = scores["mean_knn_distance"][i]
        sim = 1.0 - dist if dist is not None else None
        
        envelopes.append({
            "ad_status": ad_status,
            "ad_score": round(sim, 3) if sim is not None else None
        })
    return envelopes
