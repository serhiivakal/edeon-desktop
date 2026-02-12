"""
Edeon Cartography — TMAP LSH MinHash & MST Chemical-Space Layout Engine
"""

from typing import List, Dict, Any, Tuple
import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem
from scipy.sparse.csgraph import minimum_spanning_tree
from scipy.spatial.distance import pdist, squareform

try:
    import tmap as tm
    _HAS_TMAP = True
except ImportError:
    _HAS_TMAP = False


def compute_tmap_layout(compounds: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute 2D TMAP layout and Minimum Spanning Tree (MST) edge list for compounds.

    Args:
        compounds: List of dicts containing 'smiles' and optional property metadata.

    Returns:
        Dict with 'nodes' (with x, y coordinates) and 'edges' (source, target pair indices).
    """
    valid = []
    fps = []

    for idx, c in enumerate(compounds):
        smi = c.get("smiles", "")
        m = Chem.MolFromSmiles(smi)
        if m:
            fp = AllChem.GetMorganFingerprintAsBitVect(m, 2, nBits=1024)
            valid.append(c)
            fps.append(fp)

    N = len(valid)
    if N == 0:
        return {"ok": False, "error": "No valid molecules provided for chemical-space cartography"}

    # Use native C++ tmap engine if installed
    if _HAS_TMAP and N > 2:
        try:
            lf = tm.LSHForest(1024, 32)
            enc_fps = [tm.VectorUchar(list(fp)) for fp in fps]
            lf.batch_add(enc_fps)
            lf.index()
            cfg = tm.LayoutConfiguration()
            cfg.node_size = 1.0
            x, y, s, t, _ = tm.layout_from_lsh_forest(lf, cfg)
            
            nodes = []
            for i in range(N):
                c = valid[i]
                nodes.append({
                    "idx": i,
                    "smiles": c["smiles"],
                    "x": round(float(x[i]), 4),
                    "y": round(float(y[i]), 4),
                    "metadata": c
                })

            edges = [{"source": int(s[k]), "target": int(t[k])} for k in range(len(s))]
            return {"ok": True, "method": "tmap_native", "nodes": nodes, "edges": edges, "n_compounds": N}
        except Exception:
            pass

    # High-precision Fallback layout: Jaccard Distance + MST + PCA/MDS layout
    arr_fps = np.zeros((N, 1024), dtype=np.uint8)
    for i in range(N):
        arr_fps[i] = list(fps[i])

    if N == 1:
        nodes = [{"idx": 0, "smiles": valid[0]["smiles"], "x": 0.0, "y": 0.0, "metadata": valid[0]}]
        return {"ok": True, "method": "fallback_single", "nodes": nodes, "edges": [], "n_compounds": 1}

    # Jaccard distance matrix
    dist_vec = pdist(arr_fps, metric="jaccard")
    dist_mat = squareform(dist_vec)

    # Compute Minimum Spanning Tree
    mst_sparse = minimum_spanning_tree(dist_mat)
    cx = mst_sparse.tocoo()

    edges = []
    for u, v in zip(cx.row, cx.col):
        edges.append({"source": int(u), "target": int(v)})

    # Simple 2D MDS/PCA projection for fallback x, y
    mean = np.mean(arr_fps, axis=0)
    centered = arr_fps - mean
    u, s, vt = np.linalg.svd(centered, full_matrices=False)
    coords_2d = u[:, :2] * s[:2]

    # Normalize coordinates to [-100, 100]
    min_c, max_c = np.min(coords_2d, axis=0), np.max(coords_2d, axis=0)
    denom = np.where(max_c - min_c == 0, 1.0, max_c - min_c)
    norm_coords = ((coords_2d - min_c) / denom) * 200.0 - 100.0

    nodes = []
    for i in range(N):
        c = valid[i]
        nodes.append({
            "idx": i,
            "smiles": c["smiles"],
            "x": round(float(norm_coords[i, 0]), 4),
            "y": round(float(norm_coords[i, 1]), 4),
            "metadata": c
        })

    return {
        "ok": True,
        "method": "tmap_fallback_mst",
        "nodes": nodes,
        "edges": edges,
        "n_compounds": N
    }
