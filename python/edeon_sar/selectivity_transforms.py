"""
Edeon SAR — Selectivity Window-Widening Transform Ranker
"""

from typing import List, Dict, Any
from .mmp_engine import index_matched_pairs


def suggest_selectivity_transforms(compounds: List[Dict[str, Any]], top_k: int = 20) -> List[Dict[str, Any]]:
    """Rank MMP transformations by selectivity window-widening delta.

    Args:
        compounds: List of compounds with smiles, potency, off_target fields.
        top_k: Top K transforms to return.

    Returns:
        List of ranked transform summaries with count, mean delta_selectivity, confidence.
    """
    pairs = index_matched_pairs(compounds)
    if not pairs:
        return []

    transform_map: Dict[str, List[Dict[str, Any]]] = {}
    for p in pairs:
        key = p["transform"]
        if key not in transform_map:
            transform_map[key] = []
        transform_map[key].append(p)

    ranked = []
    for tr, records in transform_map.items():
        n_pairs = len(records)
        mean_sel = sum(r["delta_selectivity"] for r in records) / n_pairs
        mean_pot = sum(r["delta_potency"] for r in records) / n_pairs
        mean_tox = sum(r["delta_off_target"] for r in records) / n_pairs

        r1, r2 = records[0]["r1"], records[0]["r2"]
        ranked.append({
            "transform": tr,
            "r1": r1,
            "r2": r2,
            "count": n_pairs,
            "mean_delta_selectivity": round(mean_sel, 4),
            "mean_delta_potency": round(mean_pot, 4),
            "mean_delta_off_target": round(mean_tox, 4),
            "confidence": "high" if n_pairs >= 3 else "medium" if n_pairs >= 2 else "low"
        })

    # Sort descending by mean_delta_selectivity
    ranked.sort(key=lambda x: x["mean_delta_selectivity"], reverse=True)
    return ranked[:top_k]
