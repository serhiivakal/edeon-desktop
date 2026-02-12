import pytest
import pandas as pd
from edeon_data.shared.splits import bemis_murcko_scaffold, scaffold_split, scaffold_split_by_group, random_split, time_split, check_leakage

def test_bemis_murcko_scaffold():
    # Ethanol should have no Bemis-Murcko scaffold (empty string)
    assert bemis_murcko_scaffold("CCO") == ""
    
    # Benzene should have benzene as scaffold
    assert bemis_murcko_scaffold("c1ccccc1") == "c1ccccc1"
    
    # Toluene should have benzene as scaffold
    assert bemis_murcko_scaffold("Cc1ccccc1") == "c1ccccc1"

def test_scaffold_split():
    # Construct a dummy dataset
    data = {
        "smiles_canonical": [
            "c1ccccc1", "Cc1ccccc1", "CCc1ccccc1",  # Scaffold: c1ccccc1 (3)
            "C1CCCCC1", "CC1CCCCC1",                 # Scaffold: C1CCCCC1 (2)
            "c1cncnc1",                              # Scaffold: c1cncnc1 (1)
            "CCO", "CCC",                            # No scaffold (2)
        ],
        "inchikey": [f"KEY_{i}" for i in range(8)]
    }
    df = pd.DataFrame(data)
    
    train, cal, test, meta = scaffold_split(df, smiles_col="smiles_canonical", ratios=(0.5, 0.25, 0.25))
    
    assert len(train) > 0
    assert len(cal) > 0
    assert len(test) > 0
    
    # Check no leakage
    check_leakage(train, cal, test)
    
    assert meta["train"] == len(train)
    assert meta["cal"] == len(cal)
    assert meta["test"] == len(test)
    assert "test_to_train_nn_tanimoto_mean" in meta

def test_random_split():
    data = {
        "inchikey": [f"KEY_{i}" for i in range(100)],
        "value_log": [i * 0.1 for i in range(100)]
    }
    df = pd.DataFrame(data)
    
    train, cal, test, meta = random_split(df, value_col="value_log", ratios=(0.7, 0.15, 0.15))
    
    assert len(train) == 70
    assert len(cal) == 15
    assert len(test) == 15
    
    check_leakage(train, cal, test)

def test_time_split():
    data = {
        "inchikey": [f"KEY_{i}" for i in range(10)],
        "year_reported": [2010, 2010, 2011, 2011, 2012, 2012, 2013, 2013, 2014, 2014]
    }
    df = pd.DataFrame(data)
    
    train, cal, test, meta = time_split(df, year_col="year_reported", ratios=(0.6, 0.2, 0.2))
    assert train is not None
    
    assert len(train) >= 6
    assert len(cal) >= 2
    assert len(test) >= 2
    
    check_leakage(train, cal, test)

def test_time_split_sparse():
    data = {
        "inchikey": [f"KEY_{i}" for i in range(10)],
        "year_reported": [2010, 2011, None, None, None, None, None, None, None, None]
    }
    df = pd.DataFrame(data)
    
    assert time_split(df, year_col="year_reported") is None


def test_scaffold_split_by_group():
    # Construct a dummy dataset representing multiple records per compound (group)
    data = {
        "smiles_canonical": [
            "c1ccccc1", "c1ccccc1", "Cc1ccccc1",  # Scaffold: c1ccccc1
            "C1CCCCC1", "C1CCCCC1", "CC1CCCCC1",  # Scaffold: C1CCCCC1
            "c1cncnc1", "c1cncnc1",                 # Scaffold: c1cncnc1
            "CCO", "CCO", "CCC"                    # No scaffold
        ],
        "inchikey": [
            "KEY_0", "KEY_0", "KEY_1",
            "KEY_2", "KEY_2", "KEY_3",
            "KEY_4", "KEY_4",
            "KEY_5", "KEY_5", "KEY_6"
        ]
    }
    df = pd.DataFrame(data)
    
    train, cal, test, meta = scaffold_split_by_group(df, group_col="inchikey", ratios=(0.5, 0.25, 0.25))
    
    # Assert splits are non-empty
    assert len(train) > 0
    assert len(cal) > 0
    assert len(test) > 0
    
    # Check no leakage at compound level (inchikey)
    check_leakage(train, cal, test, key_col="inchikey")
    
    # Verify that no inchikey is split across folds
    train_keys = set(train["inchikey"])
    cal_keys = set(cal["inchikey"])
    test_keys = set(test["inchikey"])
    
    assert train_keys.isdisjoint(cal_keys)
    assert train_keys.isdisjoint(test_keys)
    assert cal_keys.isdisjoint(test_keys)
    
    # Total row counts should match
    assert len(train) + len(cal) + len(test) == len(df)
