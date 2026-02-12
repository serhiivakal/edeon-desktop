"""
Edeon Shape — JSON-RPC IPC Handlers
"""

from typing import Dict, Any
from .combo_score import screen_3d_similarity


def handle_shape_screen_3d(params: Dict[str, Any]) -> Dict[str, Any]:
    """Screen candidates using 3D shape alignment + electrostatics against reference SMILES."""
    reference_smiles = params.get("reference_smiles", "")
    candidates = params.get("candidates", [])
    top_k = int(params.get("top_k", 50))

    results = screen_3d_similarity(reference_smiles, candidates, top_k=top_k)
    return {
        "ok": True,
        "reference_smiles": reference_smiles,
        "results": results,
        "n_screened": len(candidates),
        "n_returned": len(results)
    }
