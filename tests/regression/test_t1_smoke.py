import pytest
import yaml
import math
from pathlib import Path
import pandas as pd
from edeon_models import build_default_registry
from edeon_models.endpoints import Endpoint

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "tier1"
TOLERANCE = yaml.safe_load((Path(__file__).parent / "tier1_tolerance.yaml").read_text())


@pytest.fixture(scope="module")
def registry():
    return build_default_registry()


def fixture_files():
    if not FIXTURES_DIR.exists():
        return []
    return sorted(FIXTURES_DIR.glob("*.csv"))


@pytest.mark.parametrize("fixture_path", fixture_files(), ids=lambda p: p.stem)
def test_t1_no_drift(fixture_path, registry):
    df = pd.read_csv(fixture_path)
    endpoint_str = df["endpoint"].iloc[0]
    endpoint = Endpoint(endpoint_str)
    
    # Get preferred backend, ensuring it is indeed Tier-1
    backend = registry.get(endpoint)
    assert backend.tier() == 1, f"Expected Tier-1 backend for {endpoint_str}, but got Tier-{backend.tier()}"
    
    smiles = df["smiles"].tolist()
    predictions = backend.predict(smiles)

    tol = TOLERANCE.get(endpoint_str, {"rel_tol": 0.001, "abs_tol": 0.001})

    failures = []
    for row, pred in zip(df.itertuples(), predictions):
        expected = float(row.expected_value)
        if pred.value and pred.value.kind == "binary":
            actual = 1.0 if pred.value.binary else 0.0
        else:
            actual = pred.value.numeric
        
        # Handle NaN equality (e.g. for failed calculations or invalid structures)
        if math.isnan(expected) and (actual is None or math.isnan(actual)):
            continue
        if actual is None or math.isnan(actual) or math.isnan(expected):
            failures.append(f"{row.smiles}: expected {expected:.4g}, got {actual}")
            continue
            
        if not (abs(actual - expected) <= tol["abs_tol"] + tol["rel_tol"] * abs(expected)):
            failures.append(f"{row.smiles}: expected {expected:.4g}, got {actual:.4g}")
            
        # Verify conformal CI bounds if they are present in expected csv
        if hasattr(row, "expected_value_lower") and pd.notna(row.expected_value_lower):
            expected_low = float(row.expected_value_lower)
            actual_low = pred.ci_lower
            if actual_low is None or math.isnan(actual_low) or not (abs(actual_low - expected_low) <= tol["abs_tol"] + tol["rel_tol"] * abs(expected_low)):
                failures.append(f"{row.smiles} [CI lower]: expected {expected_low:.4g}, got {actual_low}")
                
        if hasattr(row, "expected_value_upper") and pd.notna(row.expected_value_upper):
            expected_high = float(row.expected_value_upper)
            actual_high = pred.ci_upper
            if actual_high is None or math.isnan(actual_high) or not (abs(actual_high - expected_high) <= tol["abs_tol"] + tol["rel_tol"] * abs(expected_high)):
                failures.append(f"{row.smiles} [CI upper]: expected {expected_high:.4g}, got {actual_high}")
                
        # Verify AD status matches
        if hasattr(row, "expected_ad_status") and pd.notna(row.expected_ad_status):
            expected_ad = str(row.expected_ad_status)
            actual_ad = pred.ad_status.value
            if actual_ad != expected_ad:
                failures.append(f"{row.smiles} [AD status]: expected {expected_ad}, got {actual_ad}")

    assert not failures, f"Tier-1 model drift detected for {endpoint_str}:\n" + "\n".join(failures)
