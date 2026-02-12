from typing import Optional
import numpy as np
from rdkit import Chem, DataStructs
from rdkit.Chem import AllChem
from ..types import ADStatus
from .base import ADStrategy

class TanimotoKNN_AD(ADStrategy):
    """Applicability domain via Tanimoto distance to k nearest training neighbours.

    A query is IN if its mean distance to k nearest training neighbours is
    below the in_threshold (default 95th percentile of intra-training-set
    distances). BORDERLINE if between in_threshold and out_threshold (default
    99th percentile). OUT otherwise.
    """

    def __init__(
        self,
        training_smiles: list[str],
        k: int = 5,
        in_threshold: Optional[float] = None,
        out_threshold: Optional[float] = None,
        fp_radius: int = 2,
        fp_bits: int = 2048,
    ):
        self.k = k
        self.fp_radius = fp_radius
        self.fp_bits = fp_bits
        self._train_fps = [self._fp(s) for s in training_smiles]
        self._train_fps = [f for f in self._train_fps if f is not None]
        
        # Guard against training set size being less than k
        if len(self._train_fps) == 0:
            raise ValueError("Training set contains no valid structures for fingerprint generation.")
        
        self.k = min(self.k, len(self._train_fps))
        
        # Calibrate thresholds from training set if not provided
        if in_threshold is None or out_threshold is None:
            distances = self._calibrate()
            self.in_threshold = in_threshold or float(np.percentile(distances, 95))
            self.out_threshold = out_threshold or float(np.percentile(distances, 99))
        else:
            self.in_threshold = in_threshold
            self.out_threshold = out_threshold

    def _fp(self, smiles: str):
        try:
            if not smiles or smiles.strip() == "":
                return None
            mol = Chem.MolFromSmiles(smiles)
            if mol is None or mol.GetNumAtoms() == 0:
                return None
            return AllChem.GetMorganFingerprintAsBitVect(mol, self.fp_radius, self.fp_bits)
        except Exception:
            return None

    def _calibrate(self) -> np.ndarray:
        """Compute mean k-NN distance for each training compound (excluding itself)."""
        n = len(self._train_fps)
        result = []
        
        # If n <= 1, intra-distance is not meaningful, return 0.0 distance
        if n <= 1:
            return np.array([0.0])
            
        effective_k = min(self.k, n - 1)
        for i, fp in enumerate(self._train_fps):
            # Exclude the current fingerprint to compute intra-distance
            other_fps = [f for j, f in enumerate(self._train_fps) if j != i]
            sims = DataStructs.BulkTanimotoSimilarity(fp, other_fps)
            dists = 1.0 - np.array(sims)
            top_k = np.sort(dists)[:effective_k]
            result.append(float(np.mean(top_k)))
        return np.array(result)

    def score(self, smiles: list[str]) -> list[tuple[ADStatus, Optional[float]]]:
        out = []
        for s in smiles:
            fp = self._fp(s)
            if fp is None:
                out.append((ADStatus.UNKNOWN, None))
                continue
            sims = DataStructs.BulkTanimotoSimilarity(fp, self._train_fps)
            dists = 1.0 - np.array(sims)
            top_k = np.sort(dists)[:self.k]
            mean_dist = float(np.mean(top_k))
            if mean_dist <= self.in_threshold:
                status = ADStatus.IN
            elif mean_dist <= self.out_threshold:
                status = ADStatus.BORDERLINE
            else:
                status = ADStatus.OUT
            out.append((status, mean_dist))
        return out
