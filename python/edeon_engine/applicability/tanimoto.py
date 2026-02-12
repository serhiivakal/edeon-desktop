from dataclasses import dataclass
import numpy as np
from rdkit import Chem
from rdkit import DataStructs
from rdkit.Chem import AllChem, Mol

@dataclass
class TanimotoADReference:
    fingerprints: list  # list[ExplicitBitVect] for training set
    k: int              # neighbours used (default 5)
    threshold: float    # mean k-NN distance cutoff (95th percentile of training intra-distances)
    radius: int
    n_bits: int

def build_tanimoto_reference(smiles: list[str], k: int = 5,
                             radius: int = 2, n_bits: int = 2048,
                             percentile: float = 95.0) -> TanimotoADReference:
    fps = []
    for s in smiles:
        mol = Chem.MolFromSmiles(s)
        if mol is None:
            continue
        fps.append(AllChem.GetMorganFingerprintAsBitVect(mol, radius, n_bits))
    
    n = len(fps)
    if n == 0:
        return TanimotoADReference([], k, 1.0, radius, n_bits)
        
    intra = []
    for i in range(n):
        other_fps = fps[:i] + fps[i+1:]
        if not other_fps:
            intra.append(0.0)
            continue
        sims = DataStructs.BulkTanimotoSimilarity(fps[i], other_fps)
        k_eff = min(k, len(other_fps))
        dists = sorted(1.0 - np.asarray(sims))[:k_eff]
        intra.append(float(np.mean(dists)))
        
    threshold = float(np.percentile(intra, percentile)) if intra else 0.5
    return TanimotoADReference(fps, k, threshold, radius, n_bits)

def score_tanimoto(ref: TanimotoADReference, query_smiles: list[str], borderline_factor: float = 1.25) -> dict:
    """Returns per-query: mean_knn_distance, status: 'in'|'borderline'|'out'|'invalid', nearest_neighbours."""
    out = {"mean_knn_distance": [], "status": [], "nearest_neighbours": []}
    
    if not ref.fingerprints:
        for _ in query_smiles:
            out["mean_knn_distance"].append(None)
            out["status"].append("invalid")
            out["nearest_neighbours"].append([])
        return out

    for s in query_smiles:
        m = Chem.MolFromSmiles(s)
        if m is None:
            out["mean_knn_distance"].append(None)
            out["status"].append("invalid")
            out["nearest_neighbours"].append([])
            continue
            
        qfp = AllChem.GetMorganFingerprintAsBitVect(m, ref.radius, ref.n_bits)
        sims = np.asarray(DataStructs.BulkTanimotoSimilarity(qfp, ref.fingerprints))
        dists = 1.0 - sims
        
        k_eff = min(ref.k, len(ref.fingerprints))
        if k_eff == 0:
            out["mean_knn_distance"].append(0.0)
            out["nearest_neighbours"].append([])
            out["status"].append("in")
            continue
            
        nn_idx = np.argsort(dists)[:k_eff]
        mean_d = float(dists[nn_idx].mean())
        out["mean_knn_distance"].append(mean_d)
        out["nearest_neighbours"].append(nn_idx.tolist())
        
        if mean_d <= ref.threshold:
            status = "in"
        elif mean_d <= ref.threshold * borderline_factor:
            status = "borderline"
        else:
            status = "out"
        out["status"].append(status)
        
    return out
