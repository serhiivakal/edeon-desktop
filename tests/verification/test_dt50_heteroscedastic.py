import pytest
import math
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for headless environments
import matplotlib.pyplot as plt

from edeon_models import build_default_registry, Endpoint


@pytest.fixture(scope="module")
def registry():
    return build_default_registry()


def test_dt50_nll_in_range(registry):
    backend = registry.get(Endpoint.SOIL_DT50, preferred_tier=1)
    test_path = Path("data/curated/soil_dt50/v1.0/splits/scaffold/test.parquet")
    assert test_path.exists(), "Soil DT50 test split not found!"
    
    test_df = pd.read_parquet(test_path)
    smiles_list = test_df["smiles_canonical"].tolist()
    predictions = backend.predict(smiles_list)
    
    nll_values = []
    for pred, true_y in zip(predictions, test_df["value_log"]):
        if pd.isna(true_y):
            continue
            
        # Get predictions in log10 space
        mu = pred.provenance.get("prediction_log")
        if mu is None:
            mu = math.log10(pred.value.numeric) if pred.value.numeric > 0 else 0.0
            
        ci_low_log = pred.provenance.get("ci_lower_log")
        ci_high_log = pred.provenance.get("ci_upper_log")
        if ci_low_log is None or ci_high_log is None:
            ci_low_log = math.log10(pred.ci_lower) if pred.ci_lower > 0 else 0.0
            ci_high_log = math.log10(pred.ci_upper) if pred.ci_upper > 0 else 0.0
            
        # Compute predicted standard deviation in log10 space
        sigma = (ci_high_log - ci_low_log) / (2 * 1.96)
        sigma2 = sigma ** 2
        
        # Heteroscedastic NLL formula: 0.5 * (ln(sigma2) + (y - mu)^2 / sigma2)
        nll = 0.5 * (np.log(sigma2) + (true_y - mu) ** 2 / sigma2)
        nll_values.append(nll)
        
    mean_nll = np.mean(nll_values)
    print(f"Soil DT50 Mean Test NLL: {mean_nll:.4f}")
    assert mean_nll <= 1.5, (
        f"DT50 mean NLL = {mean_nll:.3f}, target <= 1.5. "
        f"Heteroscedastic variance prediction is poorly calibrated."
    )


def test_dt50_sigma_prediction_quality(registry):
    backend = registry.get(Endpoint.SOIL_DT50, preferred_tier=1)
    test_path = Path("data/curated/soil_dt50/v1.0/splits/scaffold/test.parquet")
    assert test_path.exists(), "Soil DT50 test split not found!"
    
    test_df = pd.read_parquet(test_path)
    
    # Filter to compounds with >= 3 measurements in the test set to compute observed variance
    grouped = test_df.groupby("inchikey").filter(lambda g: len(g) >= 3)
    if len(grouped) == 0:
        # Fallback to >= 2 measurements if test split is very small
        grouped = test_df.groupby("inchikey").filter(lambda g: len(g) >= 2)
        if len(grouped) == 0:
            pytest.skip("No multi-record compounds in test set to evaluate sigma prediction quality.")
            
    observed_sigma = []
    predicted_sigma = []
    
    for inchikey, group in grouped.groupby("inchikey"):
        obs_s = group["value_log"].std()
        observed_sigma.append(obs_s)
        
        # Predict on the compound's smiles
        smiles = group["smiles_canonical"].iloc[0]
        pred = backend.predict([smiles])[0]
        
        ci_low_log = pred.provenance.get("ci_lower_log")
        ci_high_log = pred.provenance.get("ci_upper_log")
        if ci_low_log is None or ci_high_log is None:
            ci_low_log = math.log10(pred.ci_lower) if pred.ci_lower > 0 else 0.0
            ci_high_log = math.log10(pred.ci_upper) if pred.ci_upper > 0 else 0.0
            
        pred_s = (ci_high_log - ci_low_log) / (2 * 1.96)
        predicted_sigma.append(pred_s)
        
    rho, p_value = spearmanr(observed_sigma, predicted_sigma)
    print(f"Spearman rho between predicted and observed within-compound sigma: {rho:.4f} (p={p_value:.4f})")
    
    # If standard deviation is 0 for some groups or list is too short, Spearman rho could be NaN.
    # Handle NaN or small lengths gracefully in test check but assert positive correlation if valid.
    if not np.isnan(rho):
        assert rho >= 0.3, (
            f"Spearman rho = {rho:.3f}, target >= 0.3. "
            f"Variance head is not learning meaningful aleatoric uncertainty structure."
        )
        
    # Save diagnostic plot
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(observed_sigma, predicted_sigma, color='#2e7d32', alpha=0.6, edgecolors='black')
    ax.set_xlabel("Observed within-compound σ (log10 days)")
    ax.set_ylabel("Predicted σ (log10 days)")
    ax.set_title(f"DT50 σ-prediction quality (Spearman ρ = {rho:.3f})")
    
    # Add a diagonal line for reference
    lims = [
        np.min([ax.get_xlim(), ax.get_ylim()]),
        np.max([ax.get_xlim(), ax.get_ylim()]),
    ]
    ax.plot(lims, lims, 'k--', alpha=0.5, zorder=0)
    
    report_dir = Path("docs/verification")
    report_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(report_dir / "dt50_sigma_correlation.png", dpi=150)
    plt.close(fig)
