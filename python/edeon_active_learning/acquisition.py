"""
Edeon Active Learning — Acquisition Functions Module
EI (Expected Improvement), UCB (Upper Confidence Bound), Thompson Sampling
"""

import numpy as np
from scipy.stats import norm


def compute_expected_improvement(means: np.ndarray, stds: np.ndarray, f_best: float, xi: float = 0.01) -> np.ndarray:
    """Compute Expected Improvement (EI) acquisition score."""
    ei = np.zeros_like(means)
    valid = stds > 1e-9
    if not np.any(valid):
        return ei

    improvement = means[valid] - f_best - xi
    Z = improvement / stds[valid]
    ei[valid] = improvement * norm.cdf(Z) + stds[valid] * norm.pdf(Z)
    return ei


def compute_ucb(means: np.ndarray, stds: np.ndarray, beta: float = 2.0) -> np.ndarray:
    """Compute Upper Confidence Bound (UCB) acquisition score."""
    return means + beta * stds


def compute_thompson_sampling(means: np.ndarray, stds: np.ndarray, random_seed: int = 42) -> np.ndarray:
    """Compute Thompson Sampling acquisition score."""
    rng = np.random.RandomState(random_seed)
    return rng.normal(means, stds)
