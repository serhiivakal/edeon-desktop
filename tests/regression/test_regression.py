import pytest
import yaml
import math
from pathlib import Path
import pandas as pd
from edeon_models import build_default_registry
from edeon_models.endpoints import Endpoint

FIXTURES_DIR = Path(__file__).parent / "fixtures"
TOLERANCE = yaml.safe_load((Path(__file__).parent / "tolerance.yaml").read_text())


@pytest.fixture(scope="module")
def registry():
    return build_default_registry()


def fixture_files():
    return sorted(FIXTURES_DIR.glob("*.csv"))


@pytest.mark.parametrize("fixture_path", fixture_files(), ids=lambda p: p.stem)
def test_no_drift(fixture_path, registry):
    df = pd.read_csv(fixture_path)
    endpoint_str = df["endpoint"].iloc[0]
    endpoint = Endpoint(endpoint_str)
    backend = registry.get(endpoint, preferred_tier=2)  # Always test T2 in Phase 0
    smiles = df["smiles"].tolist()
    predictions = backend.predict(smiles)

    tol = TOLERANCE.get(endpoint_str, {"rel_tol": 0.05, "abs_tol": 0.001})
    is_categorical = endpoint_str in TOLERANCE.get("categorical_endpoints", [])

    failures = []
    for row, pred in zip(df.itertuples(), predictions):
        if is_categorical:
            # Handle possible nan values in categorical strings (read as float by pandas)
            expected_str = str(row.expected_value) if not pd.isna(row.expected_value) else "Unknown"
            actual_str = str(pred.value.categorical) if pred.value.categorical is not None else "Unknown"
            if actual_str != expected_str:
                failures.append(f"{row.smiles}: expected {expected_str}, got {actual_str}")
        else:
            expected = float(row.expected_value)
            actual = pred.value.numeric
            
            # Handle NaN equality (e.g. for coordination complexes or failed calculations)
            if math.isnan(expected) and (actual is None or math.isnan(actual)):
                continue
            if actual is None or math.isnan(actual) or math.isnan(expected):
                failures.append(f"{row.smiles}: expected {expected:.4g}, got {actual}")
                continue
                
            if not (abs(actual - expected) <= tol["abs_tol"] + tol["rel_tol"] * abs(expected)):
                failures.append(f"{row.smiles}: expected {expected:.4g}, got {actual:.4g}")

    assert not failures, f"Drift detected for {endpoint_str}:\n" + "\n".join(failures)
