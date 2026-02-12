import pytest
import os
from pathlib import Path
import pandas as pd
from edeon_data.endpoints.bee.acquire import run_acquire
from edeon_data.endpoints.bee.curate import run_curate
from edeon_data.endpoints.bee.split import run_split
from edeon_data.endpoints.bee.card import run_card
from edeon_data.endpoints.fish import (
    run_curate as fish_curate,
    run_split as fish_split,
    run_card as fish_card
)
from edeon_data.endpoints.daphnia import run_all as daphnia_all
from edeon_data.endpoints.algae import run_all as algae_all
from edeon_data.endpoints.bird import run_all as bird_all
from edeon_data.endpoints.koc import run_all as koc_all
from edeon_data.endpoints.bcf import run_all as bcf_all
from edeon_data.endpoints.earthworm import run_all as earthworm_all
from edeon_data.endpoints.dt50 import run_all as dt50_all
from edeon_data.endpoints.skin_sens import run_all as skin_sens_all
from edeon_data.endpoints.rat_ld50 import run_all as rat_all

def test_bee_pipeline_e2e():
    # 1. Acquire raw data
    run_acquire("bee_acute_oral_ld50")
    raw_dir = Path("/home/svakal/Projects/Edeon/data/raw/bee")
    assert raw_dir.exists()
    assert (raw_dir / "dataset_final.csv").exists()
    
    # 2. Curate oral
    run_curate("bee_acute_oral_ld50")
    curated_dir = Path("/home/svakal/Projects/Edeon/data/curated/bee_acute_oral_ld50/v1.0")
    assert curated_dir.exists()
    assert (curated_dir / "curated.parquet").exists()
    
    # 3. Split oral
    run_split("bee_acute_oral_ld50")
    splits_dir = curated_dir / "splits"
    assert splits_dir.exists()
    assert (splits_dir / "time" / "train.parquet").exists()
    assert (splits_dir / "scaffold" / "cal.parquet").exists()
    
    # 4. Data card and manifest oral
    run_card("bee_acute_oral_ld50")
    assert (curated_dir / "data_card.yaml").exists()
    assert (curated_dir / "manifest.json").exists()

    # 5. Curate contact
    run_curate("bee_acute_contact_ld50")
    curated_dir_contact = Path("/home/svakal/Projects/Edeon/data/curated/bee_acute_contact_ld50/v1.0")
    assert curated_dir_contact.exists()
    assert (curated_dir_contact / "curated.parquet").exists()
    
    # 6. Split contact
    run_split("bee_acute_contact_ld50")
    splits_dir_contact = curated_dir_contact / "splits"
    assert splits_dir_contact.exists()
    assert (splits_dir_contact / "time" / "train.parquet").exists()
    assert (splits_dir_contact / "scaffold" / "cal.parquet").exists()
    
    # 7. Data card and manifest contact
    run_card("bee_acute_contact_ld50")
    assert (curated_dir_contact / "data_card.yaml").exists()
    assert (curated_dir_contact / "manifest.json").exists()


def test_fish_pipeline_e2e():
    # 1. Curate
    fish_curate()
    curated_dir = Path("/home/svakal/Projects/Edeon/data/curated/fish_acute_lc50/v1.0")
    assert curated_dir.exists()
    assert (curated_dir / "curated.parquet").exists()
    
    # 2. Split
    fish_split()
    splits_dir = curated_dir / "splits"
    assert splits_dir.exists()
    assert (splits_dir / "time" / "train.parquet").exists()
    assert (splits_dir / "scaffold" / "cal.parquet").exists()
    
    # 3. Data card and manifest
    fish_card()
    assert (curated_dir / "data_card.yaml").exists()
    assert (curated_dir / "manifest.json").exists()

def test_daphnia_pipeline_e2e():
    # 1. Run all stages
    daphnia_all()
    curated_dir = Path("/home/svakal/Projects/Edeon/data/curated/daphnia_acute_ec50/v1.0")
    assert curated_dir.exists()
    assert (curated_dir / "curated.parquet").exists()
    
    # 2. Verify splits
    splits_dir = curated_dir / "splits"
    assert splits_dir.exists()
    assert (splits_dir / "time" / "train.parquet").exists()
    assert (splits_dir / "scaffold" / "cal.parquet").exists()
    
    # 3. Verify data card and manifest
    assert (curated_dir / "data_card.yaml").exists()
    assert (curated_dir / "manifest.json").exists()

def test_algae_pipeline_e2e():
    # 1. Run all stages
    algae_all()
    curated_dir = Path("/home/svakal/Projects/Edeon/data/curated/algae_growth_ec50/v1.0")
    assert curated_dir.exists()
    assert (curated_dir / "curated.parquet").exists()
    
    # 2. Verify splits
    splits_dir = curated_dir / "splits"
    assert splits_dir.exists()
    assert (splits_dir / "time" / "train.parquet").exists()
    assert (splits_dir / "scaffold" / "cal.parquet").exists()
    
    # 3. Verify data card and manifest
    assert (curated_dir / "data_card.yaml").exists()
    assert (curated_dir / "manifest.json").exists()

def test_bird_pipeline_e2e():
    # 1. Run all stages
    bird_all()
    curated_dir = Path("/home/svakal/Projects/Edeon/data/curated/bird_acute_oral_ld50/v1.0")
    assert curated_dir.exists()
    assert (curated_dir / "curated.parquet").exists()
    
    # 2. Verify splits
    splits_dir = curated_dir / "splits"
    assert splits_dir.exists()
    assert (splits_dir / "time" / "train.parquet").exists()
    assert (splits_dir / "scaffold" / "cal.parquet").exists()
    
    # 3. Verify data card and manifest
    assert (curated_dir / "data_card.yaml").exists()
    assert (curated_dir / "manifest.json").exists()

def test_koc_pipeline_e2e():
    # 1. Run all stages
    koc_all()
    curated_dir = Path("/home/svakal/Projects/Edeon/data/curated/soil_koc/v1.0")
    assert curated_dir.exists()
    assert (curated_dir / "curated.parquet").exists()
    
    # 2. Verify splits
    splits_dir = curated_dir / "splits"
    assert splits_dir.exists()
    # Soil Koc has no time-split since years are not reported in the raw SDF files
    assert (splits_dir / "scaffold" / "train.parquet").exists()
    assert (splits_dir / "random" / "train.parquet").exists()
    
    # 3. Verify data card and manifest
    assert (curated_dir / "data_card.yaml").exists()
    assert (curated_dir / "manifest.json").exists()


def test_bcf_pipeline_e2e():
    # 1. Run all stages
    bcf_all()
    curated_dir = Path("/home/svakal/Projects/Edeon/data/curated/bcf/v1.0")
    assert curated_dir.exists()
    assert (curated_dir / "curated.parquet").exists()
    
    # 2. Verify splits
    splits_dir = curated_dir / "splits"
    assert splits_dir.exists()
    # BCF has no time-split since years are not reported in the raw SDF files
    assert (splits_dir / "scaffold" / "train.parquet").exists()
    assert (splits_dir / "random" / "train.parquet").exists()
    
    # 3. Verify data card and manifest
    assert (curated_dir / "data_card.yaml").exists()
    assert (curated_dir / "manifest.json").exists()


def test_earthworm_pipeline_e2e():
    # 1. Run all stages
    earthworm_all()
    curated_dir = Path("/home/svakal/Projects/Edeon/data/curated/earthworm_acute_lc50/v1.0")
    assert curated_dir.exists()
    assert (curated_dir / "curated.parquet").exists()
    
    # 2. Verify splits
    splits_dir = curated_dir / "splits"
    assert splits_dir.exists()
    assert (splits_dir / "scaffold" / "train.parquet").exists()
    assert (splits_dir / "random" / "train.parquet").exists()
    
    # 3. Verify data card and manifest
    assert (curated_dir / "data_card.yaml").exists()
    assert (curated_dir / "manifest.json").exists()


def test_dt50_pipeline_e2e():
    # 1. Run all stages
    dt50_all()
    curated_dir = Path("/home/svakal/Projects/Edeon/data/curated/soil_dt50/v1.0")
    assert curated_dir.exists()
    assert (curated_dir / "curated.parquet").exists()
    
    # 2. Verify splits and make sure no compound-level leakage
    splits_dir = curated_dir / "splits"
    assert splits_dir.exists()
    assert (splits_dir / "scaffold" / "train.parquet").exists()
    assert (splits_dir / "random" / "train.parquet").exists()
    
    # Verify no leakage
    for split_type in ["scaffold", "random", "time"]:
        tr_p = splits_dir / split_type / "train.parquet"
        cal_p = splits_dir / split_type / "cal.parquet"
        te_p = splits_dir / split_type / "test.parquet"
        if tr_p.exists() and cal_p.exists() and te_p.exists():
            tr = pd.read_parquet(tr_p)
            cal = pd.read_parquet(cal_p)
            te = pd.read_parquet(te_p)
            # Check overlap
            overlap = set(tr["inchikey"]) & set(cal["inchikey"])
            assert len(overlap) == 0, f"Leakage between train and cal in {split_type}"
            overlap = set(tr["inchikey"]) & set(te["inchikey"])
            assert len(overlap) == 0, f"Leakage between train and test in {split_type}"
            overlap = set(cal["inchikey"]) & set(te["inchikey"])
            assert len(overlap) == 0, f"Leakage between cal and test in {split_type}"
            
    # 3. Verify data card and manifest
    assert (curated_dir / "data_card.yaml").exists()
    assert (curated_dir / "manifest.json").exists()


def test_skin_sens_pipeline_e2e():
    # 1. Run all stages
    skin_sens_all()
    curated_dir = Path("/home/svakal/Projects/Edeon/data/curated/skin_sensitization/v1.0")
    assert curated_dir.exists()
    assert (curated_dir / "curated.parquet").exists()
    
    # 2. Verify splits
    splits_dir = curated_dir / "splits"
    assert splits_dir.exists()
    assert (splits_dir / "scaffold" / "train.parquet").exists()
    assert (splits_dir / "random" / "train.parquet").exists()
    
    # 3. Verify data card and manifest
    assert (curated_dir / "data_card.yaml").exists()
    assert (curated_dir / "manifest.json").exists()


def test_rat_pipeline_e2e():
    # 1. Run all stages
    rat_all()
    curated_dir = Path("/home/svakal/Projects/Edeon/data/curated/rat_acute_oral_ld50/v1.0")
    assert curated_dir.exists()
    assert (curated_dir / "curated.parquet").exists()
    
    # 2. Verify splits
    splits_dir = curated_dir / "splits"
    assert splits_dir.exists()
    assert (splits_dir / "scaffold" / "train.parquet").exists()
    assert (splits_dir / "random" / "train.parquet").exists()
    
    # 3. Verify data card and manifest
    assert (curated_dir / "data_card.yaml").exists()
    assert (curated_dir / "manifest.json").exists()



def test_release_pipeline_e2e():
    from edeon_data.shared.release import run_release_pipeline
    run_release_pipeline()
    
    curated_dir = Path("/home/svakal/Projects/Edeon/data/curated")
    dist_dir = Path("/home/svakal/Projects/Edeon/dist")
    docs_dir = Path("/home/svakal/Projects/Edeon/docs")
    
    assert (curated_dir / "_cross_endpoint_overlap.csv").exists()
    assert (docs_dir / "CURATION_SUMMARY.md").exists()
    assert (curated_dir / "MANIFEST.json").exists()
    assert (dist_dir / "edeon-curated-datasets-v1.0.zip").exists()
    assert (dist_dir / "README.md").exists()


