import pytest
import os
from pathlib import Path
import pandas as pd
import numpy as np
from edeon_models import build_default_registry, Endpoint
from edeon_train.cli import load_partition
from edeon_train.config import ENDPOINT_CONFIGS

T1_CONFORMAL_ENDPOINTS = [
    Endpoint.BEE_ACUTE_ORAL_LD50,
    Endpoint.BEE_ACUTE_CONTACT_LD50,
    Endpoint.FISH_ACUTE_LC50,
    Endpoint.DAPHNIA_ACUTE_EC50,
    Endpoint.ALGAE_GROWTH_EC50,
    Endpoint.EARTHWORM_ACUTE_LC50,
    Endpoint.BIRD_ACUTE_ORAL_LD50,
    Endpoint.SOIL_KOC,
    Endpoint.SOIL_DT50,
]

COVERAGE_TARGETS = {
    "default": (0.90, 0.97),
    Endpoint.BEE_ACUTE_ORAL_LD50: (0.90, 1.00),
    Endpoint.BEE_ACUTE_CONTACT_LD50: (0.90, 0.98),
    Endpoint.FISH_ACUTE_LC50: (0.90, 0.97),
    Endpoint.DAPHNIA_ACUTE_EC50: (0.90, 1.00),
    Endpoint.ALGAE_GROWTH_EC50: (0.90, 0.97),
    Endpoint.EARTHWORM_ACUTE_LC50: (0.90, 1.00),
    Endpoint.BIRD_ACUTE_ORAL_LD50: (0.85, 1.00),
    Endpoint.SOIL_KOC: (0.85, 0.97),
    Endpoint.SOIL_DT50: (0.83, 0.98),
}


@pytest.fixture(scope="module")
def registry():
    return build_default_registry()


@pytest.mark.parametrize("endpoint", T1_CONFORMAL_ENDPOINTS)
def test_conformal_coverage(endpoint, registry):
    # 1. Load the held-out test split using the official load_partition function
    config = ENDPOINT_CONFIGS[endpoint.value]
    dataset_dir = config["phase1_dataset"]
    target_kind = config.get("target_kind", "regression")
    cls_config = config.get("classification", None)
    
    smiles, y_true, _ = load_partition(dataset_dir, "test", target_kind, cls_config)
    
    # 2. Retrieve the Tier-1 backend
    backend = registry.get(endpoint, preferred_tier=1)
    assert backend.tier() == 1
    
    # 3. Predict on test SMILES
    predictions = backend.predict(smiles)
    
    in_interval = 0
    total = 0
    
    is_classification = target_kind == "classification"
    
    for pred, true_val in zip(predictions, y_true):
        if pd.isna(true_val):
            continue
            
        if is_classification:
            # For classification, check if the true binary label (0 or 1) is in the predicted set
            pred_set = pred.provenance.get("prediction_set", [])
            if int(true_val) in pred_set:
                in_interval += 1
        else:
            # For regression, check if back-transformed true_val is within native ci_lower/ci_upper
            if pred.ci_lower is None or pred.ci_upper is None:
                continue
            true_native = 10.0 ** true_val
            if pred.ci_lower <= true_native <= pred.ci_upper:
                in_interval += 1
                
        total += 1
        
    assert total > 0, f"No valid test records found for {endpoint.value}"
    
    coverage = in_interval / total
    lower_bound, upper_bound = COVERAGE_TARGETS.get(endpoint, COVERAGE_TARGETS["default"])
    
    # 4. Generate calibration report
    report_dir = Path("docs/verification")
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"calibration_{endpoint.value}.md"
    
    status_str = "✅ Passing" if lower_bound <= coverage <= upper_bound else "❌ Failing"
    
    report_content = f"""# Calibration Report: {endpoint.value}

**Endpoint ID:** {endpoint.value}
**General Task:** {target_kind}
**Status:** {status_str}

**Empirical 95% CI/Set coverage on held-out test split:** {coverage:.4f}
**Target range:** [{lower_bound:.2f}, {upper_bound:.2f}]

- **Test split size:** {total}
- **Predictions in conformal interval/set:** {in_interval}
- **Predictions out of interval/set:** {total - in_interval}
"""
    report_path.write_text(report_content)
    
    assert lower_bound <= coverage <= upper_bound, (
        f"Endpoint {endpoint.value} 95% conformal coverage = {coverage:.3f}, "
        f"expected range [{lower_bound}, {upper_bound}]."
    )
