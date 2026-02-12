"""
Activity Cliffs Detection Module
"""
import numpy as np
from rdkit import Chem, DataStructs
from rdkit.Chem import AllChem

def detect_cliffs(smiles: list[str], y: np.ndarray,
                  model_type: str,
                  similarity_threshold: float = 0.85,
                  activity_gap: float = 1.0,
                  max_pairs: int = 50) -> list[dict]:
    """
    Returns a list of cliff pairs sorted by 'severity' = (similarity * gap),
    each item:
      { 'i': int, 'j': int, 'smiles_i': str, 'smiles_j': str,
        'similarity': float, 'activity_i': float, 'activity_j': float,
        'gap': float }
    For classification, 'gap' = 1 if labels differ, 0 otherwise; `activity_gap` is ignored.
    """
    y = np.asarray(y, dtype=float)
    if len(smiles) > 20000:
        return []
        
    fps = []
    orig_indices = []
    for idx, s in enumerate(smiles):
        try:
            mol = Chem.MolFromSmiles(s)
            if mol is not None:
                fp = AllChem.GetMorganFingerprintAsBitVect(mol, 2, 2048)
                fps.append(fp)
                orig_indices.append(idx)
        except Exception:
            pass
            
    cliffs = []
    n = len(fps)
    for i in range(n):
        sims = DataStructs.BulkTanimotoSimilarity(fps[i], fps[i+1:])
        for k, sim in enumerate(sims):
            j = i + 1 + k
            if sim < similarity_threshold:
                continue
            orig_i = orig_indices[i]
            orig_j = orig_indices[j]
            if model_type == "regression":
                gap = abs(y[orig_i] - y[orig_j])
                if gap < activity_gap:
                    continue
            else:
                if y[orig_i] == y[orig_j]:
                    continue
                gap = 1.0
            cliffs.append({
                "i": orig_i,
                "j": orig_j,
                "smiles_i": smiles[orig_i],
                "smiles_j": smiles[orig_j],
                "similarity": float(sim),
                "activity_i": float(y[orig_i]),
                "activity_j": float(y[orig_j]),
                "gap": float(gap),
                "severity": float(sim * gap),
            })
            
    cliffs.sort(key=lambda c: -c["severity"])
    return cliffs[:max_pairs]
