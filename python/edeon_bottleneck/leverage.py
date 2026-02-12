"""
Edeon Bottleneck Analyzer — Leverage by Counterfactual Substitution

Aggregation-function-agnostic: works for arithmetic MPO, geometric MPO,
or regulatory scorecard without re-derivation. No closed-form gradient;
numerically lifts each endpoint to its achievable target and measures
the aggregate improvement.

Three achievability estimators:
  - spread: q90 of desirability over in-AD compounds
  - mmp: d_i after applying best single MMP transform delta (if H2 index available)
  - expert: user-supplied target from the desirability profile
"""

import numpy as np
from typing import Optional


def _weighted_mean_aggregate(d_vector: dict[str, float], weights: dict[str, float]) -> float:
    """Weighted arithmetic mean aggregate S(c).

    Calls the existing MPO/scorecard pattern: weighted sum of desirabilities.
    This is the default aggregation function.
    """
    total = 0.0
    for ep, d in d_vector.items():
        w = weights.get(ep, 0.0)
        total += w * d
    return total


def compute_achievable_targets(
    compounds_desirabilities: list[dict[str, float]],
    compounds_ad_status: list[dict[str, str]],
    endpoints: list[str],
    method: str = "spread",
    expert_targets: Optional[dict[str, float]] = None,
    mmp_deltas: Optional[dict[str, float]] = None,
) -> dict[str, float]:
    """Estimate achievable desirability target d_i* for each endpoint.

    Args:
        compounds_desirabilities: list of {endpoint: desirability} per compound
        compounds_ad_status: list of {endpoint: "in"|"edge"|"out"} per compound
        endpoints: list of endpoint names
        method: "spread" | "mmp" | "expert"
        expert_targets: user-supplied {endpoint: target_desirability}
        mmp_deltas: {endpoint: best_transform_delta} from MMP index

    Returns:
        {endpoint: achievable_desirability_target}
    """
    targets = {}

    for ep in endpoints:
        if method == "expert" and expert_targets and ep in expert_targets:
            targets[ep] = float(expert_targets[ep])
            continue

        # Collect in-AD desirabilities for this endpoint
        in_ad_values = []
        for i, d_vec in enumerate(compounds_desirabilities):
            ad = compounds_ad_status[i].get(ep, "in") if i < len(compounds_ad_status) else "in"
            if ad in ("in", "edge") and ep in d_vec:
                in_ad_values.append(d_vec[ep])

        if not in_ad_values:
            # No in-AD data — set target to neutral
            targets[ep] = 0.5
            continue

        if method == "mmp" and mmp_deltas and ep in mmp_deltas:
            # MMP: median desirability + best transform delta, capped at 1.0
            median_d = float(np.median(in_ad_values))
            targets[ep] = min(1.0, median_d + mmp_deltas[ep])
        else:
            # Spread (default): q90 of in-AD desirabilities
            targets[ep] = float(np.quantile(in_ad_values, 0.9))

    return targets


def compute_leverage(
    compounds_desirabilities: list[dict[str, float]],
    endpoints: list[str],
    weights: dict[str, float],
    achievable_targets: dict[str, float],
    aggregate_fn=None,
) -> dict[str, dict]:
    """Compute leverage by counterfactual substitution for each endpoint.

    For each endpoint i, recompute the aggregate with d_i lifted to max(d_i(c), d_i*),
    everything else held. Leverage = mean improvement over compounds.

    Args:
        compounds_desirabilities: [{endpoint: desirability}] per compound
        endpoints: list of endpoint names to evaluate
        weights: normalized endpoint weights
        achievable_targets: {endpoint: d_i*}
        aggregate_fn: optional custom aggregation function(d_vector, weights) -> float

    Returns:
        {endpoint: {"leverage": float, "headroom": float, "mean_desirability": float}}
    """
    if aggregate_fn is None:
        aggregate_fn = _weighted_mean_aggregate

    n = len(compounds_desirabilities)
    if n == 0:
        return {ep: {"leverage": 0.0, "headroom": 0.0, "mean_desirability": 0.5}
                for ep in endpoints}

    # Compute baseline aggregates
    baselines = []
    for d_vec in compounds_desirabilities:
        baselines.append(aggregate_fn(d_vec, weights))

    result = {}
    for ep in endpoints:
        target = achievable_targets.get(ep, 0.5)
        deltas = []
        ds = []

        for i, d_vec in enumerate(compounds_desirabilities):
            d_i = d_vec.get(ep, 0.5)
            ds.append(d_i)

            # Counterfactual: lift endpoint to max(current, target)
            lifted = dict(d_vec)
            lifted[ep] = max(d_i, target)
            new_agg = aggregate_fn(lifted, weights)
            deltas.append(new_agg - baselines[i])

        mean_d = float(np.mean(ds)) if ds else 0.5
        headroom = target - mean_d
        leverage = float(np.mean(deltas)) if deltas else 0.0

        result[ep] = {
            "leverage": leverage,
            "headroom": headroom,
            "mean_desirability": mean_d,
        }

    return result


def rank_by_leverage(leverage_results: dict[str, dict]) -> list[tuple[str, dict]]:
    """Sort endpoints by leverage descending."""
    items = list(leverage_results.items())
    items.sort(key=lambda x: x[1]["leverage"], reverse=True)
    return items
