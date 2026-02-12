"""
Edeon Bottleneck Analyzer — Uncertainty Propagation

Propagates prediction uncertainty through the leverage ranking:
  - MC draws from the predictive distribution per compound × endpoint
  - Recomputes the full leverage ranking per draw → distribution over ranks
  - Reports rank_stability (fraction of draws holding point-estimate rank)
  - Bootstrap CIs on leverage values and Spearman correlations

Small-n guard (§2.6):
  - n < 15 in-AD → reliability="insufficient_data", excluded from ranking
  - n < 30 → reliability="low", CI displayed prominently
"""

import numpy as np
from typing import Optional


def _sample_from_interval(
    value: float,
    interval: Optional[list[float]],
    ad_status: str,
    marginal_spread: float,
    n_samples: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Generate MC samples from the predictive distribution for one prediction.

    - In-AD with interval: sample from normal approximated from conformal/heteroscedastic interval
    - Out-of-AD: inflate to the endpoint's marginal spread (do NOT treat as reliable)
    - No interval: use marginal spread as fallback
    """
    if interval and len(interval) == 2 and ad_status in ("in", "edge"):
        lo, hi = interval
        sigma = (hi - lo) / 3.92  # 95% CI → ~2 sigma each side
        sigma = max(sigma, 1e-8)
        return rng.normal(value, sigma, size=n_samples)

    # Out-of-AD or no interval: uninformative distribution
    sigma = marginal_spread / 2.0 if marginal_spread > 0 else abs(value) * 0.5 + 0.1
    return rng.normal(value, sigma, size=n_samples)


def compute_marginal_spreads(
    compounds: list[dict],
    endpoints: list[str],
) -> dict[str, float]:
    """Compute the marginal spread (std dev) of values for each endpoint."""
    spreads = {}
    for ep in endpoints:
        values = []
        for c in compounds:
            ep_data = c.get("endpoints", {}).get(ep, {})
            v = ep_data.get("value")
            if v is not None:
                values.append(v)
        spreads[ep] = float(np.std(values)) if len(values) > 1 else 1.0
    return spreads


def mc_rank_stability(
    compounds: list[dict],
    endpoints: list[str],
    weights: dict[str, float],
    desirability_fn,
    leverage_fn,
    achievable_targets: dict[str, float],
    n_mc: int = 500,
    seed: int = 42,
) -> dict[str, dict]:
    """Run MC propagation to assess rank stability.

    Returns for each endpoint:
      - rank_stability: fraction of MC draws where endpoint holds its point-estimate rank
      - leverage_samples: array of leverage values across draws (for bootstrap CI)
    """
    rng = np.random.default_rng(seed)
    marginal_spreads = compute_marginal_spreads(compounds, endpoints)

    n_endpoints = len(endpoints)
    n_compounds = len(compounds)

    # Point-estimate ranking (for stability comparison)
    point_desirabilities = []
    for c in compounds:
        d_vec = {}
        for ep in endpoints:
            ep_data = c.get("endpoints", {}).get(ep, {})
            val = ep_data.get("value", 0.0)
            if val is None:
                val = 0.0
            d_vec[ep] = desirability_fn(val, ep)
        point_desirabilities.append(d_vec)

    point_leverage = leverage_fn(point_desirabilities, endpoints, weights, achievable_targets)
    point_ranking = sorted(endpoints, key=lambda e: point_leverage[e]["leverage"], reverse=True)
    point_rank_map = {ep: i for i, ep in enumerate(point_ranking)}

    # MC draws
    rank_holds = {ep: 0 for ep in endpoints}
    leverage_samples = {ep: [] for ep in endpoints}

    for _ in range(n_mc):
        # Sample perturbed values
        mc_desirabilities = []
        for c in compounds:
            d_vec = {}
            for ep in endpoints:
                ep_data = c.get("endpoints", {}).get(ep, {})
                val = ep_data.get("value", 0.0)
                if val is None:
                    val = 0.0
                interval = ep_data.get("interval")
                ad = ep_data.get("ad_status", "in")
                sampled = _sample_from_interval(
                    val, interval, ad, marginal_spreads.get(ep, 1.0), 1, rng
                )[0]
                d_vec[ep] = desirability_fn(sampled, ep)
            mc_desirabilities.append(d_vec)

        mc_leverage = leverage_fn(mc_desirabilities, endpoints, weights, achievable_targets)
        mc_ranking = sorted(endpoints, key=lambda e: mc_leverage[e]["leverage"], reverse=True)

        for ep in endpoints:
            leverage_samples[ep].append(mc_leverage[ep]["leverage"])
            mc_rank = mc_ranking.index(ep)
            if mc_rank == point_rank_map[ep]:
                rank_holds[ep] += 1

    result = {}
    for ep in endpoints:
        result[ep] = {
            "rank_stability": rank_holds[ep] / n_mc,
            "leverage_samples": np.array(leverage_samples[ep]),
        }

    return result


def bootstrap_ci(
    values: np.ndarray,
    n_boot: int = 1000,
    ci: float = 0.95,
    seed: int = 42,
) -> tuple[float, float]:
    """Compute percentile bootstrap CI for a statistic (mean)."""
    rng = np.random.default_rng(seed)
    n = len(values)
    if n < 2:
        m = float(np.mean(values)) if n > 0 else 0.0
        return (m, m)

    boot_means = np.empty(n_boot)
    for b in range(n_boot):
        sample = rng.choice(values, size=n, replace=True)
        boot_means[b] = np.mean(sample)

    alpha = (1.0 - ci) / 2.0
    lo = float(np.quantile(boot_means, alpha))
    hi = float(np.quantile(boot_means, 1.0 - alpha))
    return (lo, hi)


def count_in_ad(
    compounds: list[dict],
    endpoint: str,
) -> int:
    """Count compounds with in-AD or edge-AD predictions for an endpoint."""
    count = 0
    for c in compounds:
        ep_data = c.get("endpoints", {}).get(endpoint, {})
        ad = ep_data.get("ad_status", "in")
        if ad in ("in", "edge"):
            count += 1
    return count


def assess_reliability(n_in_ad: int) -> str:
    """Determine reliability based on in-AD sample size (§2.6)."""
    if n_in_ad < 15:
        return "insufficient_data"
    elif n_in_ad < 30:
        return "low"
    return "ok"


def check_ambiguity(
    top_leverage_ci: tuple[float, float],
    second_leverage_ci: tuple[float, float],
    overlap_threshold: float = 0.5,
) -> bool:
    """Check if the top-2 leverage CIs overlap enough to be ambiguous.

    Returns True if overlap exceeds threshold fraction of the smaller CI width.
    """
    lo1, hi1 = top_leverage_ci
    lo2, hi2 = second_leverage_ci

    overlap_lo = max(lo1, lo2)
    overlap_hi = min(hi1, hi2)
    overlap = max(0.0, overlap_hi - overlap_lo)

    width1 = hi1 - lo1
    width2 = hi2 - lo2
    min_width = min(width1, width2)

    if min_width <= 0:
        return True  # Degenerate CI → ambiguous

    return (overlap / min_width) > overlap_threshold
