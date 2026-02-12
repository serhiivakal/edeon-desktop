"""Conformal calibration module for Edeon Phase 2.

Implements standard split-conformal regression and ensemble-variance-scaled
conformal regression for producing mathematically guaranteed 95% confidence intervals.
"""

import logging
import numpy as np
from typing import Tuple, Optional

logger = logging.getLogger("edeon_train.conformal")

class SplitConformalRegressor:
    """Standard split conformal prediction for regression.
    
    Computes a uniform, absolute-residual conformal band.
    """
    def __init__(self, alpha: float = 0.05):
        self.alpha = alpha
        self.quantile_: Optional[float] = None
        self.cal_residuals_: Optional[np.ndarray] = None

    def calibrate(self, y_pred_cal: np.ndarray, y_true_cal: np.ndarray) -> None:
        """Fits the conformal quantile on calibration/validation data."""
        residuals = np.abs(y_pred_cal - y_true_cal)
        n = len(residuals)
        
        # Conformal correction: ceil((n + 1) * (1 - alpha)) / n
        q_level = np.ceil((n + 1) * (1 - self.alpha)) / n
        q_level = min(q_level, 1.0)
        
        self.quantile_ = float(np.quantile(residuals, q_level))
        self.cal_residuals_ = residuals
        logger.info(f"SplitConformalRegressor calibrated. Quantile: {self.quantile_:.4f} at alpha={self.alpha}")

    def interval(self, y_pred: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Computes prediction intervals for new predictions."""
        if self.quantile_ is None:
            raise RuntimeError("Must calibrate before predicting intervals")
        return y_pred - self.quantile_, y_pred + self.quantile_

    def empirical_coverage(self, y_pred_held: np.ndarray, y_true_held: np.ndarray) -> float:
        """Calculates the empirical coverage on a held-out set."""
        lo, hi = self.interval(y_pred_held)
        in_interval = (y_true_held >= lo) & (y_true_held <= hi)
        return float(in_interval.mean())
        
    def mean_width(self, y_pred: np.ndarray) -> float:
        """Calculates the mean prediction interval width."""
        lo, hi = self.interval(y_pred)
        return float(np.mean(hi - lo))

class EnsembleVarianceCalibrator:
    """Ensemble-variance-scaled split conformal prediction for regression.
    
    Scales the conformal residuals by the ensemble's predicted standard deviation
    to generate dynamic, input-dependent prediction intervals: CI = y_pred +/- q * max(y_std, epsilon).
    """
    def __init__(self, alpha: float = 0.05, epsilon: float = 1e-5):
        self.alpha = alpha
        self.epsilon = epsilon
        self.quantile_: Optional[float] = None
        self.cal_residuals_: Optional[np.ndarray] = None

    def calibrate(self, y_pred_cal: np.ndarray, y_true_cal: np.ndarray, y_std_cal: np.ndarray) -> None:
        """Fits the scaling factor quantile on calibration data using ensemble stds."""
        scaled_residuals = np.abs(y_pred_cal - y_true_cal) / np.maximum(y_std_cal, self.epsilon)
        n = len(scaled_residuals)
        
        # Conformal correction
        q_level = np.ceil((n + 1) * (1 - self.alpha)) / n
        q_level = min(q_level, 1.0)
        
        self.quantile_ = float(np.quantile(scaled_residuals, q_level))
        self.cal_residuals_ = scaled_residuals
        logger.info(f"EnsembleVarianceCalibrator calibrated. Quantile: {self.quantile_:.4f} at alpha={self.alpha}")

    def interval(self, y_pred: np.ndarray, y_std: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Computes prediction intervals for new predictions."""
        if self.quantile_ is None:
            raise RuntimeError("Must calibrate before predicting intervals")
        half_width = self.quantile_ * np.maximum(y_std, self.epsilon)
        return y_pred - half_width, y_pred + half_width

    def empirical_coverage(self, y_pred_held: np.ndarray, y_true_held: np.ndarray, y_std_held: np.ndarray) -> float:
        """Calculates the empirical coverage on a held-out set."""
        lo, hi = self.interval(y_pred_held, y_std_held)
        in_interval = (y_true_held >= lo) & (y_true_held <= hi)
        return float(in_interval.mean())
        
    def mean_width(self, y_pred: np.ndarray, y_std: np.ndarray) -> float:
        """Calculates the mean prediction interval width."""
        lo, hi = self.interval(y_pred, y_std)
        return float(np.mean(hi - lo))

class InductiveConformalClassifier:
    """Inductive conformal classifier for binary classification.
    
    Uses nonconformity scores based on 1 - p(true_class) from a calibrated model.
    Produces prediction sets at a given significance level alpha.
    
    At significance level alpha=0.05, the prediction set is guaranteed to contain
    the true label at least 95% of the time (marginal coverage guarantee).
    """
    def __init__(self, alpha: float = 0.05):
        self.alpha = alpha
        self.quantile_: Optional[float] = None
        self.cal_scores_: Optional[np.ndarray] = None
    
    def calibrate(self, cal_proba: np.ndarray, cal_labels: np.ndarray) -> None:
        """Fits the conformal threshold on calibration data.
        
        Args:
            cal_proba: Predicted probabilities for class 1 (toxic), shape (n,).
            cal_labels: True binary labels (0 or 1), shape (n,).
        """
        # Nonconformity score: 1 - p(true class)
        p_true = np.where(cal_labels == 1, cal_proba, 1.0 - cal_proba)
        scores = 1.0 - p_true
        
        n = len(scores)
        # Conformal correction: ceil((n+1) * (1-alpha)) / n
        q_level = np.ceil((n + 1) * (1 - self.alpha)) / n
        q_level = min(q_level, 1.0)
        
        self.quantile_ = float(np.quantile(scores, q_level))
        self.cal_scores_ = scores
        logger.info(
            f"InductiveConformalClassifier calibrated. "
            f"Threshold: {self.quantile_:.4f} at alpha={self.alpha}"
        )
    
    def predict_set(self, proba: np.ndarray) -> list:
        """Returns prediction sets for each input.
        
        Args:
            proba: Predicted probabilities for class 1 (toxic), shape (n,).
            
        Returns:
            List of sets, each containing the predicted labels (0, 1, or both).
            A set with both {0, 1} means the model is uncertain.
            An empty set (rare) means neither label is conformal.
        """
        if self.quantile_ is None:
            raise RuntimeError("Must calibrate before predicting sets")
        
        sets = []
        for p in proba:
            pred_set = set()
            # Include class 1 if score for label=1 <= quantile
            if (1.0 - p) <= self.quantile_:
                pred_set.add(1)
            # Include class 0 if score for label=0 <= quantile
            if p <= self.quantile_:
                pred_set.add(0)
            sets.append(pred_set)
        return sets
    
    def empirical_coverage(self, proba: np.ndarray, labels: np.ndarray) -> float:
        """Calculates the empirical coverage on a held-out set."""
        sets = self.predict_set(proba)
        covered = sum(1 for s, y in zip(sets, labels) if int(y) in s)
        return covered / len(labels) if len(labels) > 0 else 0.0
    
    def mean_set_size(self, proba: np.ndarray) -> float:
        """Calculates the mean prediction set size (1.0 = crisp, 2.0 = uncertain)."""
        sets = self.predict_set(proba)
        return float(np.mean([len(s) for s in sets]))


def save_calibration(
    split_cal: SplitConformalRegressor,
    var_cal: EnsembleVarianceCalibrator,
    path: str,
    cls_cal: Optional['InductiveConformalClassifier'] = None
) -> None:
    """Saves conformal calibrators to a single .npz file.
    
    Supports both regression (split + variance) and classification calibrators.
    """
    save_dict = {
        "split_quantile": split_cal.quantile_ if split_cal.quantile_ is not None else np.nan,
        "split_alpha": split_cal.alpha,
        "var_quantile": var_cal.quantile_ if var_cal.quantile_ is not None else np.nan,
        "var_alpha": var_cal.alpha,
        "var_epsilon": var_cal.epsilon
    }
    
    if cls_cal is not None:
        save_dict["cls_quantile"] = cls_cal.quantile_ if cls_cal.quantile_ is not None else np.nan
        save_dict["cls_alpha"] = cls_cal.alpha
        save_dict["has_cls"] = 1.0
    else:
        save_dict["has_cls"] = 0.0
    
    np.savez(path, **save_dict)
    logger.info(f"Saved conformal calibration parameters to {path}")

def load_calibration(path: str) -> Tuple[SplitConformalRegressor, EnsembleVarianceCalibrator]:
    """Loads and instantiates regression conformal calibrators from a .npz file."""
    data = np.load(path)
    
    split_cal = SplitConformalRegressor(alpha=float(data["split_alpha"]))
    split_q = float(data["split_quantile"])
    split_cal.quantile_ = split_q if not np.isnan(split_q) else None
    
    var_cal = EnsembleVarianceCalibrator(
        alpha=float(data["var_alpha"]),
        epsilon=float(data.get("var_epsilon", 1e-5))
    )
    var_q = float(data["var_quantile"])
    var_cal.quantile_ = var_q if not np.isnan(var_q) else None
    
    logger.info(f"Loaded conformal calibration parameters from {path}")
    return split_cal, var_cal

def load_classification_calibration(path: str) -> Optional['InductiveConformalClassifier']:
    """Loads an InductiveConformalClassifier from an .npz file, if present."""
    data = np.load(path)
    
    if float(data.get("has_cls", 0.0)) < 0.5:
        return None
    
    cls_cal = InductiveConformalClassifier(alpha=float(data["cls_alpha"]))
    cls_q = float(data["cls_quantile"])
    cls_cal.quantile_ = cls_q if not np.isnan(cls_q) else None
    
    logger.info(f"Loaded classification conformal calibration from {path}")
    return cls_cal

def save_classification_calibration(
    cls_cal: 'InductiveConformalClassifier',
    path: str
) -> None:
    """Saves an InductiveConformalClassifier to a standalone .npz file."""
    np.savez(
        path,
        cls_quantile=cls_cal.quantile_ if cls_cal.quantile_ is not None else np.nan,
        cls_alpha=cls_cal.alpha,
        has_cls=1.0,
        # Include dummy regression fields for compatibility with load_calibration
        split_quantile=np.nan,
        split_alpha=0.05,
        var_quantile=np.nan,
        var_alpha=0.05,
        var_epsilon=1e-5
    )
    logger.info(f"Saved classification conformal calibration to {path}")
