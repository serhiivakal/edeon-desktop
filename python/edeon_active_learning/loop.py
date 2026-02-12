"""
Edeon Active Learning — Active Learning Loop Orchestrator
"""

from typing import List, Dict, Any
import numpy as np
from .surrogate_gp import fit_gp_surrogate
from .acquisition import compute_expected_improvement, compute_ucb, compute_thompson_sampling


def suggest_active_learning_batch(
    labeled_pool: List[Dict[str, Any]],
    candidate_pool: List[Dict[str, Any]],
    acquisition: str = "ei",
    batch_size: int = 10,
    endpoint: str = "potency"
) -> Dict[str, Any]:
    """Suggest next batch of candidates for synthesis/screening using Gaussian Process BO.

    Args:
        labeled_pool: List of {"smiles": str, "potency": float, ...}
        candidate_pool: List of {"smiles": str, ...}
        acquisition: "ei" | "ucb" | "ts"
        batch_size: Number of top batch compounds to return
        endpoint: Target endpoint key

    Returns:
        Dict with 'suggested_batch', 'model_metrics', and 'acquisition_method'.
    """
    train_smiles = [c["smiles"] for c in labeled_pool if "smiles" in c and endpoint in c and c[endpoint] is not None]
    train_y = [float(c[endpoint]) for c in labeled_pool if "smiles" in c and endpoint in c and c[endpoint] is not None]

    if not train_smiles or not candidate_pool:
        return {"ok": False, "error": "Insufficient labeled training compounds or empty candidate pool"}

    cand_smiles = [c["smiles"] for c in candidate_pool if "smiles" in c]
    if not cand_smiles:
        return {"ok": False, "error": "No valid candidate SMILES found in candidate pool"}

    means, stds, r2 = fit_gp_surrogate(train_smiles, train_y, cand_smiles)
    f_best = float(np.max(train_y))

    acq_type = acquisition.lower()
    if acq_type == "ucb":
        acq_scores = compute_ucb(means, stds)
    elif acq_type == "ts":
        acq_scores = compute_thompson_sampling(means, stds)
    else:
        acq_type = "ei"
        acq_scores = compute_expected_improvement(means, stds, f_best=f_best)

    # Rank candidates descending by acquisition score
    ranked_indices = np.argsort(-acq_scores)[:batch_size]

    suggested_batch = []
    for rank_idx, idx in enumerate(ranked_indices):
        cand = candidate_pool[idx]
        suggested_batch.append({
            "rank": rank_idx + 1,
            "smiles": cand["smiles"],
            "predicted_mean": round(float(means[idx]), 4),
            "predicted_std": round(float(stds[idx]), 4),
            "acquisition_score": round(float(acq_scores[idx]), 4),
            "metadata": cand
        })

    return {
        "ok": True,
        "acquisition_method": acq_type.upper(),
        "suggested_batch": suggested_batch,
        "model_metrics": {
            "r2_score": round(r2, 4),
            "f_best": round(f_best, 4),
            "n_train": len(train_smiles),
            "n_candidates": len(cand_smiles)
        }
    }
