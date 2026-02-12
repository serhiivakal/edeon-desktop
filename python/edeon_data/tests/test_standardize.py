import pytest
import pandas as pd
from edeon_data.shared.standardize import standardize_smiles, standardize_dataframe

def test_standardize_smiles_valid():
    # Ethanol (MW 46.07) - wait, MW limit is 50.0 by default, so it should be rejected due to MW.
    # Let's test with glucose (MW 180.16)
    smi = "C(C1C(C(C(C(O1)O)O)O)O)O"
    canon, ikey, flags = standardize_smiles(smi)
    assert canon is not None
    assert ikey is not None
    assert flags == []

def test_standardize_smiles_salt_stripping():
    # Sodium acetate: CC(=O)[O-].[Na+] -> parent is CC(=O)O (acetic acid, MW 60.05)
    smi = "CC(=O)[O-].[Na+]"
    canon, ikey, flags = standardize_smiles(smi)
    assert canon == "CC(=O)O"
    assert ikey is not None

def test_standardize_smiles_invalid():
    smi = "C1CC"  # Invalid SMILES
    canon, ikey, flags = standardize_smiles(smi)
    assert canon is None
    assert ikey is None
    assert "parse_failed" in flags[0]

def test_standardize_smiles_disallowed_atoms():
    # Contains Xenon (Xe)
    smi = "CC[Xe]"
    canon, ikey, flags = standardize_smiles(smi)
    assert canon is None
    assert ikey is None
    assert "disallowed_atoms" in flags[0]

def test_standardize_smiles_mw_limits():
    # Methane (MW 16) is too small (< 50)
    smi = "C"
    canon, ikey, flags = standardize_smiles(smi)
    assert canon is None
    assert ikey is None
    assert "mw_out_of_range" in flags[0]

def test_standardize_dataframe():
    data = {
        "smiles": [
            "C(C1C(C(C(C(O1)O)O)O)O)O",  # Glucose (valid)
            "CC(=O)[O-].[Na+]",           # Sodium acetate (valid, stripped)
            "C1CC",                      # Invalid
            "CC[Xe]",                    # Disallowed atom
            "C",                         # MW < 50
        ],
        "id": [1, 2, 3, 4, 5]
    }
    df = pd.DataFrame(data)
    curated, rejections = standardize_dataframe(df, smiles_col="smiles")
    
    assert len(curated) == 2
    assert len(rejections) == 3
    
    # Check columns
    assert "smiles_canonical" in curated.columns
    assert "inchikey" in curated.columns
    assert "quality_flags" in curated.columns
    
    assert "smiles_original" in rejections.columns
    assert "stage" in rejections.columns
    assert "reason" in rejections.columns
    
    # Check specific rejections
    rejections_ids = rejections["id"].tolist()
    assert 3 in rejections_ids  # parse_failed
    assert 4 in rejections_ids  # disallowed_atoms
    assert 5 in rejections_ids  # mw_out_of_range
