import os
import json
import pandas as pd
from pathlib import Path

from edeon_data.shared.splits import scaffold_split, random_split, time_split
from edeon_data.shared.io import write_parquet_with_hash

def run_split(endpoint: str = None) -> None:
    """Creates scaffold, random, and chronological time splits for bird acute oral LD50 dataset."""
    endpoint = "bird_acute_oral_ld50"
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
    
    # 3. Time Split (70/15/15)
    time_res = time_split(
        df_curated,
        year_col="year_reported",
        ratios=(0.7, 0.15, 0.15)
    )
    
    hashes = {}
    
    # Scaffold splits
    hashes["scaffold_train"] = write_parquet_with_hash(train_sc, scaf_dir / "train.parquet")
    hashes["scaffold_cal"] = write_parquet_with_hash(cal_sc, scaf_dir / "cal.parquet")
    hashes["scaffold_test"] = write_parquet_with_hash(test_sc, scaf_dir / "test.parquet")
    
    # Random splits
    hashes["random_train"] = write_parquet_with_hash(train_ra, rand_dir / "train.parquet")
    hashes["random_cal"] = write_parquet_with_hash(cal_ra, rand_dir / "cal.parquet")
    hashes["random_test"] = write_parquet_with_hash(test_ra, rand_dir / "test.parquet")
    
    if time_res is not None:
        train_ti, cal_ti, test_ti, meta_ti = time_res
        time_dir.mkdir(parents=True, exist_ok=True)
        hashes["time_train"] = write_parquet_with_hash(train_ti, time_dir / "train.parquet")
        hashes["time_cal"] = write_parquet_with_hash(cal_ti, time_dir / "cal.parquet")
        hashes["time_test"] = write_parquet_with_hash(test_ti, time_dir / "test.parquet")
        meta_ti["status"] = "available"
    else:
        meta_ti = {
            "train": 0,
            "cal": 0,
            "test": 0,
            "status": "not_available"
        }
        
    # Collect metadata
    meta_splits = {
        "scaffold": meta_sc,
        "random": meta_ra,
        "time": meta_ti,
        "hashes": hashes
    }
    
    with open(curated_dir / "splits_metadata.json", "w") as f:
        json.dump(meta_splits, f, indent=2)
        
    print("Splitting stage completed successfully.")

if __name__ == "__main__":
    run_split()
