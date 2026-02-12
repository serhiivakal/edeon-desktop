import numpy as np
from typing import Optional
from scipy.optimize import brentq
from scipy.stats import norm

class VarianceScaler:
    """Post-hoc σ² scaling for empirical coverage targeting.
    
    Scales predicted σ² by a constant fit on a held-out calibration set
    to ensure the empirical coverage hits the target (e.g., 95%).
    """
    def __init__(self):
        self.scale_: Optional[float] = None

    def calibrate(self, mu_cal: np.ndarray, sigma2_cal: np.ndarray,
                  y_cal: np.ndarray, target_coverage: float = 0.95) -> None:
        """Find the σ²-scale factor such that empirical coverage hits target."""
        def coverage_deficit(scale: float) -> float:
            sigma_scaled = np.sqrt(sigma2_cal * scale)
            z = norm.ppf(0.5 + target_coverage / 2)
            lo, hi = mu_cal - z * sigma_scaled, mu_cal + z * sigma_scaled
            return float(((y_cal >= lo) & (y_cal <= hi)).mean() - target_coverage)

        # Scale factor lives in [0.01, 100] for stability
        try:
            self.scale_ = float(brentq(coverage_deficit, 0.01, 100.0))
        except ValueError:
            # If even the unscaled is over/under coverage, fall back to 1.0
            self.scale_ = 1.0

    def apply(self, sigma2: np.ndarray) -> np.ndarray:
        if self.scale_ is None:
            raise RuntimeError("Must calibrate before applying variance scaling")
        return sigma2 * self.scale_

def empirical_coverage(mu: np.ndarray, sigma: np.ndarray, y_true: np.ndarray, level: float = 0.95) -> float:
    """Computes empirical coverage of prediction intervals."""
    z = norm.ppf(0.5 + level / 2)
    lo, hi = mu - z * sigma, mu + z * sigma
    return float(((y_true >= lo) & (y_true <= hi)).mean())

def nll_score(mu: np.ndarray, sigma2: np.ndarray, y_true: np.ndarray) -> float:
    """Computes Gaussian Negative Log-Likelihood score."""
    return float(0.5 * (np.log(sigma2) + (y_true - mu)**2 / sigma2).mean())

def calibration_curve(mu: np.ndarray, sigma: np.ndarray, y_true: np.ndarray, n_bins: int = 10) -> dict:
    """Computes a calibration curve of predicted vs observed coverage."""
    # Group predictions by their predicted uncertainty (sigma)
    indices = np.argsort(sigma)
    bin_size = len(mu) // n_bins
    
    bin_predicted_sigma = []
    bin_empirical_coverage = []
    
    for i in range(n_bins):
        start = i * bin_size
        end = (i + 1) * bin_size if i < n_bins - 1 else len(mu)
        bin_idx = indices[start:end]
        
        bin_predicted_sigma.append(float(np.mean(sigma[bin_idx])))
        # Check 95% coverage in this bin
        bin_empirical_coverage.append(empirical_coverage(mu[bin_idx], sigma[bin_idx], y_true[bin_idx], level=0.95))
        
    return {
        "bin_predicted_sigma": bin_predicted_sigma,
        "bin_empirical_coverage": bin_empirical_coverage
    }
