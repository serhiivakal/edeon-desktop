import pytest
import pandas as pd
import numpy as np
from edeon_data.shared.activity import to_canonical_units, log_transform, aggregate_records

def test_to_canonical_units_liquid():
    # 10 mg/L Acetone (MW 58.08) -> Molar
    # Value = 10 / (1000 * 58.08) = 1.721763e-4
    molar_val = to_canonical_units(10.0, "mg/L", "molar", mw=58.08)
    assert pytest.approx(molar_val, rel=1e-5) == 1.721763e-4
    
    # 1.721763e-4 Molar Acetone -> mg/L
    mg_l_val = to_canonical_units(molar_val, "molar", "mg/L", mw=58.08)
    assert pytest.approx(mg_l_val, rel=1e-5) == 10.0

    # ug/L to mg/L
    assert to_canonical_units(1500.0, "ug/L", "mg/L") == 1.5
    
    # ppm to mg/L
    assert to_canonical_units(5.0, "ppm", "mg/L") == 5.0

def test_to_canonical_units_mass():
    assert to_canonical_units(2.5, "g/kg", "mg/kg") == 2500.0
    assert to_canonical_units(500.0, "ug/kg", "mg/kg") == 0.5

def test_to_canonical_units_bee():
    assert to_canonical_units(1.2, "ug/bee", "ng/bee") == 1200.0
    assert to_canonical_units(3.0, "mg/bee", "ug/bee") == 3000.0

def test_log_transform():
    assert log_transform(100.0, target="log10") == 2.0
    assert log_transform(100.0, target="-log10") == -2.0
    
    # 10 mg/L Acetone (MW 58.08) -> -log10_molar
    # molar is ~1.721763e-4. log10(molar) is ~ -3.764. -log10 is ~3.764
    assert pytest.approx(log_transform(10.0, mw=58.08, target="-log10_molar"), rel=1e-3) == 3.764

def test_aggregate_records_regression():
    # Replicates for the same compound
    data = {
        "value": [10.0, 20.0, 15.0],
        "value_log": [1.0, 1.301, 1.176],
        "quality_flags": [["some_flag"], ["some_flag", "other_flag"], []]
    }
    df = pd.DataFrame(data)
    agg = aggregate_records(df, mode="regression")
    
    # Value should be geometric mean of [10.0, 20.0, 15.0]
    expected_geom = np.exp(np.mean(np.log([10.0, 20.0, 15.0])))
    assert pytest.approx(agg["value"]) == expected_geom
    
    # value_log should be arithmetic mean of value_logs
    assert pytest.approx(agg["value_log"]) == np.mean([1.0, 1.301, 1.176])
    
    assert agg["aggregation_n"] == 3
    assert agg["aggregation_method"] == "geomean"
    assert agg["aggregation_cv"] is not None
    assert "some_flag" in agg["quality_flags"]
    assert "other_flag" in agg["quality_flags"]

def test_aggregate_records_classification():
    data = {
        "value_class": ["toxic", "nontoxic", "toxic"],
        "quality_flags": [[], ["flag1"], ["flag2"]]
    }
    df = pd.DataFrame(data)
    agg = aggregate_records(df, mode="classification")
    
    assert agg["value_class"] == "toxic"
    assert agg["aggregation_n"] == 3
    assert agg["aggregation_method"] == "majority_vote"
    assert "flag1" in agg["quality_flags"]
    assert "flag2" in agg["quality_flags"]

def test_aggregate_records_classification_tie():
    data = {
        "value_class": ["nontoxic", "toxic"],
        "quality_flags": [[]] * 2
    }
    df = pd.DataFrame(data)
    agg = aggregate_records(df, mode="classification")
    
    # Should pick "toxic" due to tie-breaker high concern rule
    assert agg["value_class"] == "toxic"
    assert "class_conflict" in agg["quality_flags"]
