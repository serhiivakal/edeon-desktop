"""
Edeon Shape — ROCS-Style ComboScore Ranker Engine
ComboScore = ShapeSimilarity + EspSimilarity (range [0.0, 2.0])
"""

from typing import List, Dict, Any
from .align import prepare_3d_conformer, calculate_shape_overlap
from .electrostatics import calculate_electrostatic_similarity


def screen_3d_similarity(
    reference_smiles: str,
    candidates: List[Dict[str, Any]],
    top_k: int = 50
) -> List[Dict[str, Any]]:
    """Screen candidate SMILES against a reference ligand using 3D shape alignment + electrostatics.

    Args:
        reference_smiles: Active reference ligand SMILES.
        candidates: List of candidate dicts with 'smiles' and optional metadata.
        top_k: Number of top scoring candidates to return.

    Returns:
        List of candidate records with shape_score, esp_score, combo_score, and rank.
    """
    ref_mol = prepare_3d_conformer(reference_smiles)
    if not ref_mol:
        return []

    results = []
    for c in candidates:
        cand_smi = c.get("smiles", "")
        probe_mol = prepare_3d_conformer(cand_smi)
        if not probe_mol:
            continue

        shape_score, aligned_probe = calculate_shape_overlap(probe_mol, ref_mol)
        esp_score = calculate_electrostatic_similarity(aligned_probe or probe_mol, ref_mol)
        combo_score = shape_score + esp_score

        results.append({
            "smiles": cand_smi,
            "shape_score": round(shape_score, 4),
            "esp_score": round(esp_score, 4),
            "combo_score": round(combo_score, 4),
            "metadata": c
        })

    # Sort descending by combo_score
    results.sort(key=lambda x: x["combo_score"], reverse=True)
    return results[:top_k]
