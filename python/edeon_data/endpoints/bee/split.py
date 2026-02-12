import os
import json
import pandas as pd
from pathlib import Path
from typing import Tuple, Dict

from edeon_data.shared.splits import scaffold_split, random_split, check_leakage
from edeon_data.shared.io import write_parquet_with_hash

RAW_DIR = Path("/home/svakal/Projects/Edeon/data/raw/bee")

def run_split(endpoint: str) -> None:
    """Creates scaffold, random, and canonical provided time splits for honey bee datasets."""
    assert endpoint in ["bee_acute_oral_ld50", "bee_acute_contact_ld50"]
    
    curated_dir = Path(f"/home/svakal/Projects/Edeon/data/curated/{endpoint}/v1.0")
    curated_path = curated_dir / "curated.parquet"
    if not curated_path.exists():
        raise FileNotFoundError(f"Curated Parquet not found at {curated_path}. Run curate first.")
        
    df_curated = pd.read_parquet(curated_path)
    
    # Create split output directories
    scaf_dir = curated_dir / "splits" / "scaffold"
    rand_dir = curated_dir / "splits" / "random"
    time_dir = curated_dir / "splits" / "time"
    
    scaf_dir.mkdir(parents=True, exist_ok=True)
    rand_dir.mkdir(parents=True, exist_ok=True)
    time_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Scaffold Split (70/15/15)
    train_sc, cal_sc, test_sc, meta_sc = scaffold_split(
        df_curated,
        smiles_col="smiles_canonical",
        ratios=(0.7, 0.15, 0.15),
        seed=42
    )
    
    # 2. Random Split (70/15/15)
    train_ra, cal_ra, test_ra, meta_ra = random_split(
        df_curated,
        value_col="value_log",
        classification=False,
        ratios=(0.7, 0.15, 0.15),
        seed=42
    )
    
    # 3. Time Split (provided by ApisTox)
    # We load time_train.csv and time_test.csv to match canonical splits
    train_csv_path = RAW_DIR / "time_train.csv"
    test_csv_path = RAW_DIR / "time_test.csv"
    
    if not train_csv_path.exists() or not test_csv_path.exists():
        raise FileNotFoundError("ApisTox provided time train/test CSVs not found in raw folder.")
        
    df_apistox_train = pd.read_csv(train_csv_path)
    df_apistox_test = pd.read_csv(test_csv_path)
    
    # We match using CAS or SMILES in df_curated
    train_cids = set(df_apistox_train["CID"].dropna())
    test_cids = set(df_apistox_test["CID"].dropna())
    
    # Check that there's no intersection between raw splits
    intersection = train_cids & test_cids
    if intersection:
        print(f"Warning: Intersection between provided train/test CIDs: {len(intersection)}")
        
    # Match df_curated rows
    # source_record_id was mapped to string representation of CID
    def check_is_test(row):
        try:
            cid = float(row["source_record_id"]) if row["source_record_id"] else None
            if cid in test_cids:
                return True
        except Exception:
            pass
        return False
        
    df_curated["_is_test"] = df_curated.apply(check_is_test, axis=1)
    
    df_test_t = df_curated[df_curated["_is_test"]].drop(columns=["_is_test"]).reset_index(drop=True)
    df_train_temp = df_curated[~df_curated["_is_test"]].drop(columns=["_is_test"]).copy()
    
    # Partition the df_train_temp (80% of total) into train (70% of total) and cal (10% of total) chronologically!
    # Let's sort by year_reported
    df_train_temp = df_train_temp.sort_values(by="year_reported").reset_index(drop=True)
    
    total_valid = len(df_curated)
    # Target cal is 15% of the total dataset, train is the rest of the non-test records
    cal_target = int(0.15 * total_valid)
    
    # Because of chronological splitting:
    # First (len - cal_target) go to train, the latest cal_target go to cal!
    split_idx = len(df_train_temp) - cal_target
    
    df_train_t = df_train_temp.iloc[:split_idx].reset_index(drop=True)
    df_cal_t = df_train_temp.iloc[split_idx:].reset_index(drop=True)
    
    check_leakage(df_train_t, df_cal_t, df_test_t)
    
    # Calculate years metadata
    train_years = df_train_t["year_reported"].dropna().tolist()
    cal_years = df_cal_t["year_reported"].dropna().tolist()
    test_years = df_test_t["year_reported"].dropna().tolist()
    
    meta_ti = {
        "train": len(df_train_t),
        "cal": len(df_cal_t),
        "test": len(df_test_t),
        "train_year_max": int(max(train_years)) if train_years else None,
        "cal_year_range": [int(min(cal_years)), int(max(cal_years))] if cal_years else None,
        "test_year_range": [int(min(test_years)), int(max(test_years))] if test_years else None
    }
    
    # Save Parquet files for splits and collect their SHA-256 hashes
    hashes = {}
    
    # Scaffold splits
    hashes["scaffold_train"] = write_parquet_with_hash(train_sc, scaf_dir / "train.parquet")
    hashes["scaffold_cal"] = write_parquet_with_hash(cal_sc, scaf_dir / "cal.parquet")
    hashes["scaffold_test"] = write_parquet_with_hash(test_sc, scaf_dir / "test.parquet")
    
    # Random splits
    hashes["random_train"] = write_parquet_with_hash(train_ra, rand_dir / "train.parquet")
    hashes["random_cal"] = write_parquet_with_hash(cal_ra, rand_dir / "cal.parquet")
    hashes["random_test"] = write_parquet_with_hash(test_ra, rand_dir / "test.parquet")
    
    # Time splits
    hashes["time_train"] = write_parquet_with_hash(df_train_t, time_dir / "train.parquet")
    hashes["time_cal"] = write_parquet_with_hash(df_cal_t, time_dir / "cal.parquet")
    hashes["time_test"] = write_parquet_with_hash(df_test_t, time_dir / "test.parquet")
    
    # Save splits meta for card compilation
    meta_splits = {
        "scaffold": meta_sc,
        "random": meta_ra,
        "time": meta_ti,
        "hashes": hashes
    }
    
    with open(curated_dir / "splits_metadata.json", "w") as f:
        json.dump(meta_splits, f, indent=2)
