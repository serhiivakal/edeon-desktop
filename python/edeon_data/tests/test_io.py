import pytest
import tempfile
import json
import yaml
from pathlib import Path
import pandas as pd
from edeon_data.shared.io import write_parquet_with_hash, write_csv_mirror, write_data_card, write_curation_log, write_manifest, enforce_parquet_types
from edeon_data.schema import (
    DataCard,
    SourceMetadata,
    StandardisationMetadata,
    ActivityMetadata,
    CurationSummary,
    SplitsMetadata,
    ScaffoldSplitMetadata,
    RandomSplitMetadata
)

def test_enforce_parquet_types():
    data = {
        "inchikey": ["KEY_1"],
        "smiles_canonical": ["CCO"],
        "value": [10.5],
        "year_reported": [2020],
        "quality_flags": [["flag1", "flag2"]],
        "endpoint": ["bee_acute_oral_ld50"],
        "source": ["ApisTox"],
        "value_units": ["ug/bee"]
    }
    df = pd.DataFrame(data)
    df_clean = enforce_parquet_types(df)
    
    # Assert column types
    assert df_clean["inchikey"].dtype == "object"
    assert df_clean["value"].dtype == "float64"
    assert df_clean["year_reported"].dtype == "Int32"
    assert isinstance(df_clean["quality_flags"].iloc[0], list)
    assert df_clean["quality_flags"].iloc[0] == ["flag1", "flag2"]
    
    # Assert missing columns are padded as None
    assert "cas" in df_clean.columns
    assert df_clean["cas"].iloc[0] is None

def test_write_and_manifest():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        data = {
            "inchikey": ["KEY_1", "KEY_2"],
            "smiles_canonical": ["CCO", "CCC"],
            "value": [10.5, 20.0],
            "endpoint": ["bee_acute_oral_ld50"] * 2,
            "source": ["ApisTox"] * 2,
            "value_units": ["ug/bee"] * 2,
            "quality_flags": [["f1"], ["f2"]]
        }
        df = pd.DataFrame(data)
        
        parquet_path = tmp_path / "curated.parquet"
        csv_path = tmp_path / "curated.csv"
        
        # Write
        sha_pq = write_parquet_with_hash(df, parquet_path)
        write_csv_mirror(df, csv_path)
        
        assert parquet_path.exists()
        assert csv_path.exists()
        assert sha_pq != ""
        
        # Check re-read of parquet
        df_pq = pd.read_parquet(parquet_path)
        assert len(df_pq) == 2
        assert df_pq["inchikey"].iloc[0] == "KEY_1"
        assert list(df_pq["quality_flags"].iloc[0]) == ["f1"]
        
        # Test DataCard write
        card = DataCard(
            dataset_id="edeon-test",
            endpoint="bee_acute_oral_ld50",
            version="1.0.0",
            created="2026-05-30",
            sources=[
                SourceMetadata(
                    name="ApisTox",
                    citation="Adamczyk 2025",
                    raw_records=100
                )
            ],
            standardisation=StandardisationMetadata(
                version="1.2.4",
                atom_allowlist=["H", "C", "O"],
                mw_range=[50, 1500]
            ),
            activity=ActivityMetadata(
                units_canonical="ug/bee",
                log_transform="log10"
            ),
            curation_summary=CurationSummary(
                raw_records=100,
                after_parse=90,
                after_standardisation=85,
                after_filter=80,
                after_aggregation=80,
                rejection_rate=0.2
            ),
            splits=SplitsMetadata(
                scaffold=ScaffoldSplitMetadata(train=60, cal=10, test=10),
                random=RandomSplitMetadata(train=60, cal=10, test=10)
            ),
            intended_use="testing"
        )
        
        card_path = tmp_path / "data_card.yaml"
        write_data_card(card, card_path)
        assert card_path.exists()
        
        # Test manifest write
        write_manifest(tmp_path)
        manifest_path = tmp_path / "manifest.json"
        assert manifest_path.exists()
        
        with open(manifest_path) as f:
            manifest = json.load(f)
            
        assert manifest["generator"] == "edeon-data-pipeline"
        assert "curated.parquet" in manifest["files"]
        assert "curated.csv" in manifest["files"]
        assert "data_card.yaml" in manifest["files"]
        assert manifest["files"]["curated.parquet"]["sha256"] == sha_pq
