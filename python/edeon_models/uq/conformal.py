import numpy as np
from typing import Optional
from .base import UQStrategy

class ConformalUQ(UQStrategy):
    """Split conformal prediction strategy on a held-out calibration set."""

    def __init__(self, alpha: float = 0.05):
        self.alpha = alpha  # 0.05 → 95% CI
        self.quantile: Optional[float] = None

    def calibrate(self, predictions: np.ndarray, observations: np.ndarray) -> None:
        residuals = np.abs(np.array(predictions) - np.array(observations))
        n = len(residuals)
        if n == 0:
            raise ValueError("Calibration dataset cannot be empty.")
            
        # Adjusted quantile for finite-sample coverage guarantee
        q_level = np.ceil((n + 1) * (1 - self.alpha)) / n
        q_level = min(1.0, max(0.0, q_level))  # Clip to valid quantile bounds [0.0, 1.0]
        
        self.quantile = float(np.quantile(residuals, q_level))

    def interval(self, point_estimate: float, smiles: Optional[str] = None) -> tuple[float, float]:
        if self.quantile is None:
            raise RuntimeError("Must call calibrate() before interval()")
        return (point_estimate - self.quantile, point_estimate + self.quantile)
