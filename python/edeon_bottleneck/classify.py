"""
Edeon Bottleneck Analyzer — Bottleneck Classification

Classifies each endpoint's bottleneck as:
  - chemical: real structure-property limitation (in-AD, high leverage, tight CI)
  - epistemic: uncertainty-dominated — measurement or model needed (out-of-AD, wide CI)
  - distractor: high headroom but near-zero leverage (already near-optimized or low weight)

Maps classification to recommended_action (§2.4):
  - chemical → "redesign_structure"
  - epistemic → "measure_endpoint" or "improve_model"
  - distractor → "no_action" or "deprioritize_weight"
"""

from typing import Optional


def classify_bottleneck(
    endpoint: str,
    leverage: float,
    headroom: float,
    mean_desirability: float,
    reliability: str,
    rank_stability: float,
    leverage_ci: tuple[float, float],
    n_in_ad: int,
    fraction_out_of_ad: float = 0.0,
) -> dict:
    """Classify a single endpoint's bottleneck kind and recommended action.

    Args:
        endpoint: endpoint name
        leverage: counterfactual leverage value
        headroom: achievable_target - mean_desirability
        mean_desirability: current mean d_i
        reliability: "ok" | "low" | "insufficient_data"
        rank_stability: fraction of MC draws holding rank
        leverage_ci: (lo, hi) bootstrap CI on leverage
        n_in_ad: count of in-AD compounds for this endpoint
        fraction_out_of_ad: fraction of compounds out-of-AD

    Returns:
        dict with kind, recommended_action, reason, details
    """
    ci_width = leverage_ci[1] - leverage_ci[0]

    # Rule 1: Insufficient data → always epistemic
    if reliability == "insufficient_data":
        return {
            "kind": "epistemic",
            "recommended_action": "measure_endpoint",
            "reason": f"Only {n_in_ad} in-AD compounds — insufficient for reliable ranking",
            "details": {
                "n_in_ad": n_in_ad,
                "reliability": reliability,
            },
        }

    # Rule 2: Mostly out-of-AD → epistemic (model uncertainty dominates)
    if fraction_out_of_ad > 0.5:
        return {
            "kind": "epistemic",
            "recommended_action": "improve_model",
            "reason": f"{fraction_out_of_ad:.0%} of compounds out-of-AD for {endpoint}",
            "details": {
                "fraction_out_of_ad": fraction_out_of_ad,
                "n_in_ad": n_in_ad,
                "reliability": reliability,
            },
        }

    # Rule 3: Low rank stability with wide CI → epistemic
    if rank_stability < 0.5 and ci_width > leverage * 2.0 and leverage > 0:
        return {
            "kind": "epistemic",
            "recommended_action": "measure_endpoint",
            "reason": f"Rank unstable ({rank_stability:.0%}) with wide CI, likely noise-driven",
            "details": {
                "rank_stability": rank_stability,
                "ci_width": ci_width,
                "reliability": reliability,
            },
        }

    # Rule 4: Near-zero leverage despite headroom → distractor
    if leverage < 0.005 and headroom > 0.1:
        return {
            "kind": "distractor",
            "recommended_action": "deprioritize_weight",
            "reason": f"Low leverage ({leverage:.4f}) despite headroom ({headroom:.3f}) — weight may be too low or correlated with stronger endpoint",
            "details": {
                "leverage": leverage,
                "headroom": headroom,
            },
        }

    # Rule 5: Near-zero leverage and near-zero headroom → already optimized
    if leverage < 0.005 and headroom <= 0.1:
        return {
            "kind": "distractor",
            "recommended_action": "no_action",
            "reason": f"Already near-optimal (d={mean_desirability:.3f}, headroom={headroom:.3f})",
            "details": {
                "mean_desirability": mean_desirability,
                "headroom": headroom,
            },
        }

    # Default: chemical bottleneck
    if reliability == "low":
        action = "redesign_structure"
        qualifier = " (low reliability — consider additional measurement)"
    else:
        action = "redesign_structure"
        qualifier = ""

    return {
        "kind": "chemical",
        "recommended_action": action,
        "reason": f"Chemical constraint: leverage={leverage:.4f}, headroom={headroom:.3f}{qualifier}",
        "details": {
            "leverage": leverage,
            "headroom": headroom,
            "mean_desirability": mean_desirability,
            "rank_stability": rank_stability,
            "reliability": reliability,
        },
    }
