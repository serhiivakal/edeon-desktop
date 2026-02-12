from abc import ABC, abstractmethod
from typing import Optional
import numpy as np

class UQStrategy(ABC):
    """Abstract base class for all uncertainty quantification (UQ) strategies."""

    @abstractmethod
    def calibrate(self, predictions: np.ndarray, observations: np.ndarray) -> None:
        """Calibrate the UQ strategy using a calibration dataset of predictions and observations."""

    @abstractmethod
    def interval(self, point_estimate: float, smiles: Optional[str] = None) -> tuple[float, float]:
        """Compute the confidence/prediction interval (lower, upper) for a point estimate."""
