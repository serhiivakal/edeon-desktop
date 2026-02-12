"""Applicability domain scoring and thresholding for Edeon Phase 2.

Implements Tanimoto k-NN applicability domain using Morgan fingerprints
and 95th/99th percentile thresholds fitted on the training split.
"""

import os
import logging
import numpy as np
from typing import List, Tuple, Optional, Any
from rdkit import Chem, DataStructs
from rdkit.Chem import rdFingerprintGenerator
from edeon_models.types import ADStatus

logger = logging.getLogger("edeon_train.ad")

class TrainedTanimotoAD:
    """Tanimoto k-NN Applicability Domain auditor.
    
    Query compounds are classified as:
    - IN if mean k-NN distance <= 95th percentile of intra-training distances.
    - BORDERLINE if 95th < distance <= 99th percentile.
    - OUT if distance > 99th percentile.
    """
    def __init__(
        self,
        train_fps: List[DataStructs.ExplicitBitVect],
        in_threshold: float,
        out_threshold: float,
        k: int = 5,
        radius: int = 2,
        nbits: int = 2048
    ):
        self.train_fps = train_fps
        self.in_threshold = in_threshold
        self.out_threshold = out_threshold
        self.k = k
        self.radius = radius
        self.nbits = nbits
        
    @classmethod
    def from_training_smiles(
        cls,
        smiles: List[str],
        k: int = 5,
        radius: int = 2,
        nbits: int = 2048
    ) -> "TrainedTanimotoAD":
        """Fits applicability domain thresholds and gathers fingerprints from training SMILES."""
        logger.info(f"Fitting Tanimoto k-NN AD on {len(smiles)} training smiles (k={k}, radius={radius}, nbits={nbits})")
        
        # Build fingerprints using MorganGenerator (preferred over deprecated AllChem)
        gen = rdFingerprintGenerator.GetMorganGenerator(radius=radius, fpSize=nbits)
        train_fps = []
        
        for s in smiles:
            try:
                mol = Chem.MolFromSmiles(s)
                if mol is not None:
                    train_fps.append(gen.GetFingerprint(mol))
            except Exception as e:
                logger.debug(f"SMILES {s} failed fingerprint generation: {e}")
                
        if len(train_fps) == 0:
            raise ValueError("No valid fingerprints could be computed from training SMILES list!")
            
        # Adjust k if training set is smaller
        effective_k = min(k, len(train_fps))
        
        # Calibrate thresholds from training set
        n = len(train_fps)
        intra_distances = []
        
        if n > 1:
            effective_k_intra = min(effective_k, n - 1)
            for i, fp in enumerate(train_fps):
                other_fps = [f for j, f in enumerate(train_fps) if j != i]
                sims = DataStructs.BulkTanimotoSimilarity(fp, other_fps)
                dists = 1.0 - np.array(sims)
                # Mean of the k nearest neighbours
                top_k = np.sort(dists)[:effective_k_intra]
                intra_distances.append(float(np.mean(top_k)))
            
            in_threshold = float(np.percentile(intra_distances, 95))
            out_threshold = float(np.percentile(intra_distances, 99))
        else:
            in_threshold = 0.5
            out_threshold = 0.8
            
        logger.info(f"AD Calibrated: in_threshold (95%) = {in_threshold:.4f}, out_threshold (99%) = {out_threshold:.4f}")
        return cls(train_fps, in_threshold, out_threshold, effective_k, radius, nbits)
        
    def score(self, smiles: List[str]) -> List[Tuple[ADStatus, Optional[float]]]:
        """Audits a list of query SMILES strings, returning their AD status and k-NN distance.
        
        Returns:
            List of (ADStatus, distance) tuples. Invalid SMILES strings return (ADStatus.UNKNOWN, None).
        """
        out = []
        gen = rdFingerprintGenerator.GetMorganGenerator(radius=self.radius, fpSize=self.nbits)
        
        for s in smiles:
            try:
                mol = Chem.MolFromSmiles(s)
                if mol is None:
                    out.append((ADStatus.UNKNOWN, None))
                    continue
                    
                fp = gen.GetFingerprint(mol)
                sims = DataStructs.BulkTanimotoSimilarity(fp, self.train_fps)
                dists = 1.0 - np.array(sims)
                
                # Sort and average the k nearest neighbours
                top_k = np.sort(dists)[:self.k]
                mean_dist = float(np.mean(top_k))
                
                if mean_dist <= self.in_threshold:
                    status = ADStatus.IN
                elif mean_dist <= self.out_threshold:
                    status = ADStatus.BORDERLINE
                else:
                    status = ADStatus.OUT
                    
                out.append((status, mean_dist))
            except Exception as e:
                logger.debug(f"Failed to score AD for SMILES {s}: {e}")
                out.append((ADStatus.UNKNOWN, None))
                
        return out

    def save(self, path: str) -> None:
        """Saves applicability domain fingerprints and thresholds to an .npz file."""
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        # Hex-serialize bit vectors for portable numpy serialization
        hex_fps = [DataStructs.BitVectToBinaryText(fp).hex() for fp in self.train_fps]
        
        np.savez(
            path,
            hex_fps=np.array(hex_fps, dtype=object),
            in_threshold=self.in_threshold,
            out_threshold=self.out_threshold,
            k=self.k,
            radius=self.radius,
            nbits=self.nbits
        )
        logger.info(f"Saved AD parameters to {path}")

    @classmethod
    def load(cls, path: str) -> "TrainedTanimotoAD":
        """Loads applicability domain auditor from an .npz file."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"AD checkpoints not found at {path}")
            
        data = np.load(path, allow_pickle=True)
        
        hex_fps = data["hex_fps"]
        train_fps = [DataStructs.CreateFromBinaryText(bytes.fromhex(h)) for h in hex_fps]
        
        return cls(
            train_fps=train_fps,
            in_threshold=float(data["in_threshold"]),
            out_threshold=float(data["out_threshold"]),
            k=int(data["k"]),
            radius=int(data["radius"]),
            nbits=int(data["nbits"])
        )
