import numpy as np
from typing import Optional
from .base import UQStrategy

class EnsembleVarianceUQ(UQStrategy):
    """Ensemble variance UQ strategy computing mean ± z * std from N ensemble members."""

    def __init__(self, z: float = 1.96):
        self.z = z
        self.default_std: float = 0.0
        self._smiles_std: dict[str, float] = {}

    def set_ensemble_std(self, smiles: str, std: float) -> None:
        """Map standard deviation for a given compound SMILES."""
        self._smiles_std[smiles] = std

    def calibrate(self, predictions_ensemble: np.ndarray, observations: np.ndarray) -> None:
        """Calibrate default variance by finding average standard deviation of training predictions."""
        preds = np.array(predictions_ensemble)
        if preds.ndim <= 1:
            # Fallback if 1D array is provided (meaning single point estimates)
            self.default_std = 0.0
            return
            
        # Standard deviation computed across column dimension (the N ensemble members)
        train_stds = np.std(preds, axis=1)
        self.default_std = float(np.mean(train_stds))

    def interval(self, point_estimate: float, smiles: Optional[str] = None) -> tuple[float, float]:
        std = self.default_std
        if smiles is not None and smiles in self._smiles_std:
            std = self._smiles_std[smiles]
            
        return (point_estimate - self.z * std, point_estimate + self.z * std)
