import os
import json
import pandas as pd
from pathlib import Path

from edeon_data.shared.splits import scaffold_split, random_split, time_split, check_leakage
from edeon_data.shared.io import write_parquet_with_hash

def run_split(endpoint: str = None) -> None:
    """Creates scaffold, random, and chronological time splits for Soil DT50, preventing compound-level leakage."""
    endpoint = "soil_dt50"
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
    # The default scaffold_split groups by Bemis-Murcko scaffold. Since all records of the same compound
    # have the same smiles_canonical, they will share a scaffold and thus be assigned to the same partition.
    # Therefore, no compound-level leakage can occur in scaffold_split.
    train_sc, cal_sc, test_sc, meta_sc = scaffold_split(
        df_curated,
        smiles_col="smiles_canonical",
        ratios=(0.7, 0.15, 0.15),
        seed=42
    )
    
    # 2. Random Split (70/15/15)
    # We must split unique compounds to prevent row-level leakage of compound records.
    # We select the first record for each unique inchikey to perform the split, then map back.
    df_unique = df_curated.drop_duplicates(subset=["inchikey"]).copy()
    train_ra_uni, cal_ra_uni, test_ra_uni, _ = random_split(
        df_unique,
        value_col="value_log",
        classification=False,
        ratios=(0.7, 0.15, 0.15),
        seed=42
    )
    
    train_ra = df_curated[df_curated["inchikey"].isin(train_ra_uni["inchikey"])].reset_index(drop=True)
    cal_ra = df_curated[df_curated["inchikey"].isin(cal_ra_uni["inchikey"])].reset_index(drop=True)
    test_ra = df_curated[df_curated["inchikey"].isin(test_ra_uni["inchikey"])].reset_index(drop=True)
    
    check_leakage(train_ra, cal_ra, test_ra)
    meta_ra = {
        "train": len(train_ra),
        "cal": len(cal_ra),
        "test": len(test_ra),
        "seed": 42
    }
    
    # 3. Time Split (70/15/15)
    # Find the earliest year_reported for each unique compound, split them, and map back.
    non_null_years = df_curated["year_reported"].dropna()
    has_enough_years = len(non_null_years) >= 0.5 * len(df_curated)
    
    time_res = None
    if has_enough_years:
        # Group by inchikey and get the min year_reported (earliest study)
        df_earliest_year = df_curated.groupby("inchikey")["year_reported"].min().reset_index()
        # Merge back other columns for the standard split code to use
        df_unique_year = df_unique.drop(columns=["year_reported"]).merge(df_earliest_year, on="inchikey")
        
        time_res_uni = time_split(
            df_unique_year,
            year_col="year_reported",
            ratios=(0.7, 0.15, 0.15)
        )
        
        if time_res_uni is not None:
            train_ti_uni, cal_ti_uni, test_ti_uni, meta_ti_uni = time_res_uni
            
            train_ti = df_curated[df_curated["inchikey"].isin(train_ti_uni["inchikey"])].reset_index(drop=True)
            cal_ti = df_curated[df_curated["inchikey"].isin(cal_ti_uni["inchikey"])].reset_index(drop=True)
            test_ti = df_curated[df_curated["inchikey"].isin(test_ti_uni["inchikey"])].reset_index(drop=True)
            
            check_leakage(train_ti, cal_ti, test_ti)
            
            time_res = (train_ti, cal_ti, test_ti, {
                "train": len(train_ti),
                "cal": len(cal_ti),
                "test": len(test_ti),
                "train_year_max": meta_ti_uni.get("train_year_max"),
                "cal_year_range": meta_ti_uni.get("cal_year_range"),
                "test_year_range": meta_ti_uni.get("test_year_range"),
                "status": "available"
            })

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
        
    print("Splitting stage completed successfully for Soil DT50.")

if __name__ == "__main__":
    run_split()
