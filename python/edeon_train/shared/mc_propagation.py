import numpy as np
from typing import Dict, Any, Callable

def gus_monte_carlo(mu_K: float, sigma_K: float, mu_D: float, sigma_D: float,
                    n_samples: int = 10000, rng: np.random.Generator = None) -> Dict[str, Any]:
    """Sample GUS distribution and return summary statistics.
    
    Assumes Koc and DT50 are independent.
    """
    rng = rng or np.random.default_rng(seed=42)
    K_samples = rng.normal(mu_K, sigma_K, size=n_samples)
    D_samples = rng.normal(mu_D, sigma_D, size=n_samples)
    
    gus_samples = D_samples * (4.0 - K_samples)
    
    return {
        "median": float(np.median(gus_samples)),
        "mean": float(np.mean(gus_samples)),
        "ci_lower": float(np.quantile(gus_samples, 0.025)),
        "ci_upper": float(np.quantile(gus_samples, 0.975)),
        "p05": float(np.quantile(gus_samples, 0.05)),
        "p95": float(np.quantile(gus_samples, 0.95)),
        "leaching_class_distribution": _classify(gus_samples),
    }

def _classify(gus_samples: np.ndarray) -> Dict[str, float]:
    """Returns probability of falling in each Gustafson leaching class."""
    return {
        "non_leacher": float((gus_samples < 1.8).mean()),
        "transition": float(((gus_samples >= 1.8) & (gus_samples <= 2.8)).mean()),
        "leacher": float((gus_samples > 2.8).mean()),
    }

def propagate_composite(mu_components: np.ndarray, sigma_components: np.ndarray,
                        formula: Callable[..., np.ndarray], n_samples: int = 10000,
                        seed: int = 42) -> np.ndarray:
    """General utility to propagate component uncertainty through a formula using Monte Carlo."""
    rng = np.random.default_rng(seed)
    samples = []
    for mu, sigma in zip(mu_components, sigma_components):
        samples.append(rng.normal(mu, sigma, size=n_samples))
    return formula(*samples)
