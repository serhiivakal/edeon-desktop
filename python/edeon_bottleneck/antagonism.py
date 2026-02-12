"""
Edeon Bottleneck Analyzer — Antagonism (Trade-off) Surface

Computes pairwise Spearman ρ between endpoint desirabilities to identify
antagonistic pairs (ρ < -0.3) — improving one worsens the other.

Output:
  - Full ρ matrix (for heatmap)
  - Significant antagonistic pairs flagged for TradeoffMatrix UI
"""

import numpy as np
from scipy.stats import spearmanr
from typing import Optional


def compute_tradeoff_matrix(
    compounds_desirabilities: list[dict[str, float]],
    endpoints: list[str],
    min_n: int = 10,
) -> dict:
    """Compute pairwise Spearman ρ matrix between endpoint desirabilities.

    Args:
        compounds_desirabilities: [{endpoint: desirability}] per compound
        endpoints: list of endpoint names
        min_n: minimum compounds required for correlation

    Returns:
        {
            "matrix": {ep_i: {ep_j: rho}},
            "p_values": {ep_i: {ep_j: p}},
            "antagonistic_pairs": [(ep_i, ep_j, rho, p)],
            "n": int
        }
    """
    n_compounds = len(compounds_desirabilities)
    n_endpoints = len(endpoints)

    matrix = {ep: {} for ep in endpoints}
    p_values = {ep: {} for ep in endpoints}
    antagonistic = []

    if n_compounds < min_n:
        # Not enough data for meaningful correlations
        for i, ep_i in enumerate(endpoints):
            for j, ep_j in enumerate(endpoints):
                matrix[ep_i][ep_j] = 0.0 if i != j else 1.0
                p_values[ep_i][ep_j] = 1.0
        return {
            "matrix": matrix,
            "p_values": p_values,
            "antagonistic_pairs": [],
            "n": n_compounds,
        }

    # Build data array
    data = np.zeros((n_compounds, n_endpoints))
    for c_idx, d_vec in enumerate(compounds_desirabilities):
        for e_idx, ep in enumerate(endpoints):
            data[c_idx, e_idx] = d_vec.get(ep, 0.5)

    for i, ep_i in enumerate(endpoints):
        for j, ep_j in enumerate(endpoints):
            if i == j:
                matrix[ep_i][ep_j] = 1.0
                p_values[ep_i][ep_j] = 0.0
                continue

            col_i = data[:, i]
            col_j = data[:, j]

            # Skip if constant (no variance)
            if np.std(col_i) < 1e-10 or np.std(col_j) < 1e-10:
                matrix[ep_i][ep_j] = 0.0
                p_values[ep_i][ep_j] = 1.0
                continue

            rho, p = spearmanr(col_i, col_j)
            matrix[ep_i][ep_j] = float(rho)
            p_values[ep_i][ep_j] = float(p)

            # Flag significant antagonistic pairs (ρ < -0.3, p < 0.05)
            if rho < -0.3 and p < 0.05 and i < j:
                antagonistic.append((ep_i, ep_j, float(rho), float(p)))

    # Sort by most antagonistic first
    antagonistic.sort(key=lambda x: x[2])

    return {
        "matrix": matrix,
        "p_values": p_values,
        "antagonistic_pairs": antagonistic,
        "n": n_compounds,
    }
