import os
import json
import pandas as pd
from pathlib import Path
from rdkit import Chem

from edeon_data.shared.standardize import standardize_smiles
from edeon_data.shared.io import write_parquet_with_hash, write_csv_mirror, write_curation_log
from edeon_data.schema import CuratedRecord

RAW_DIR = Path("/home/svakal/Projects/Edeon/data/raw/skin_sens")

def map_llna_to_classes(ec3):
    """Maps LLNA EC3 percentage to binary and GHS 4-class labels."""
    if ec3 is None or pd.isna(ec3):
        return None, None
        
    try:
        val = float(ec3)
    except ValueError:
        return None, None
        
    # GHS Classification:
    # Strong: EC3 < 1%
    # Moderate: 1% <= EC3 <= 10%
    # Weak: 10% < EC3 <= 100%
    # Non: EC3 > 100%
    if val < 1.0:
        ghs = "strong"
        binary = "sensitizer"
    elif val <= 10.0:
        ghs = "moderate"
        binary = "sensitizer"
    elif val <= 100.0:
        ghs = "weak"
        binary = "sensitizer"
    else:
        ghs = "non"
        binary = "non_sensitizer"
        
    return binary, ghs

def run_curate(endpoint: str = None) -> None:
    """Standardizes and curates the Skin Sensitization dataset from NICEATM LLNA and ICCVAM CCS."""
    endpoint = "skin_sensitization"
    curated_dir = Path(f"/home/svakal/Projects/Edeon/data/curated/{endpoint}/v1.0")
    curated_dir.mkdir(parents=True, exist_ok=True)

    llna_path = RAW_DIR / "niceatm_llna.csv"
    ccs_path = RAW_DIR / "iccvam_ccs.csv"
    
    if not llna_path.exists() or not ccs_path.exists():
        raise FileNotFoundError("Raw Skin Sensitization datasets not found. Run acquire first.")

    print("Loading and standardising NICEATM LLNA...")
    df_llna = pd.read_csv(llna_path)
    print("Loading and standardising ICCVAM CCS...")
    df_ccs = pd.read_csv(ccs_path)
    
    processed_records = []
    curation_log = []
    atom_allowlist = {"H", "B", "C", "N", "O", "F", "Si", "P", "S", "Cl", "Se", "Br", "I"}
    
    # Process LLNA
    for idx, row in df_llna.iterrows():
        smi_raw = str(row.get("smiles", "")).strip()
        cas = str(row.get("cas", "")) if pd.notna(row.get("cas")) else None
        name = str(row.get("name", "")) if pd.notna(row.get("name")) else None
        ec3_val = row.get("ec3_percent")
        
        if not smi_raw or smi_raw == "nan":
            curation_log.append({
                "smiles_original": None,
                "stage": "parsing",
                "reason": "missing_smiles_in_llna"
            })
            continue
            
        binary, ghs = map_llna_to_classes(ec3_val)
        if binary is None:
            curation_log.append({
                "smiles_original": smi_raw,
                "stage": "activity_filter",
                "reason": f"invalid_ec3_val:{ec3_val}"
            })
            continue
            
        # Standardize structure
        smi_canon, ikey, flags = standardize_smiles(
            smi_raw,
            atom_allowlist=atom_allowlist
        )
        
        if smi_canon is None:
            reason = flags[0] if flags else "unknown_reason"
            curation_log.append({
                "smiles_original": smi_raw,
                "stage": "standardisation",
                "reason": reason
            })
            continue
            
        processed_records.append({
            "inchikey": ikey,
            "smiles_canonical": smi_canon,
            "smiles_original": smi_raw,
            "cas": cas,
            "name": name,
            "chembl_id": None,
            "endpoint": endpoint,
            "value_units": "%",
            "source": "NICEATM LLNA",
            "source_ref": "NICEATM / NIEHS public release",
            "source_record_id": f"llna_{idx}",
            "year_reported": None,
            "raw_binary": binary,
            "raw_ghs": ghs,
            "quality_flags": flags
        })
        
    # Process CCS
    for idx, row in df_ccs.iterrows():
        smi_raw = str(row.get("smiles", "")).strip()
        cas = str(row.get("cas", "")) if pd.notna(row.get("cas")) else None
        name = str(row.get("name", "")) if pd.notna(row.get("name")) else None
        ccs_class = str(row.get("class", "")).strip().lower()
        
        if not smi_raw or smi_raw == "nan":
            curation_log.append({
                "smiles_original": None,
                "stage": "parsing",
                "reason": "missing_smiles_in_ccs"
            })
            continue
            
        if ccs_class not in ["sensitizer", "non_sensitizer"]:
            curation_log.append({
                "smiles_original": smi_raw,
                "stage": "activity_filter",
                "reason": f"invalid_ccs_class:{ccs_class}"
            })
            continue
            
        # Map CCS class
        binary = ccs_class
        ghs = "non" if ccs_class == "non_sensitizer" else "sensitizer" # unknown grade sensitizer
        
        # Standardize structure
        smi_canon, ikey, flags = standardize_smiles(
            smi_raw,
            atom_allowlist=atom_allowlist
        )
        
        if smi_canon is None:
            reason = flags[0] if flags else "unknown_reason"
            curation_log.append({
                "smiles_original": smi_raw,
                "stage": "standardisation",
                "reason": reason
            })
            continue
            
        processed_records.append({
            "inchikey": ikey,
            "smiles_canonical": smi_canon,
            "smiles_original": smi_raw,
            "cas": cas,
            "name": name,
            "chembl_id": None,
            "endpoint": endpoint,
            "value_units": "class",
            "source": "ICCVAM CCS",
            "source_ref": "ICCVAM Cosmetics Substance dataset",
            "source_record_id": f"ccs_{idx}",
            "year_reported": None,
            "raw_binary": binary,
            "raw_ghs": ghs,
            "quality_flags": flags
        })
        
    if not processed_records:
        raise ValueError("No Skin Sensitization records successfully curated.")
        
    df_raw_curated = pd.DataFrame(processed_records)
    
    # Define class order for ties (more conservative label is chosen)
    # Binary: sensitizer > non_sensitizer
    # GHS: strong > moderate > weak > sensitizer > non
    ghs_priority = {
        "strong": 4,
        "moderate": 3,
        "weak": 2,
        "sensitizer": 1,
        "non": 0
    }
    
    # Group by InChIKey to resolve duplicates and conflicts
    combined_records = []
    all_ikeys = df_raw_curated["inchikey"].unique()
    
    for ikey in all_ikeys:
        group = df_raw_curated[df_raw_curated["inchikey"] == ikey]
        
        # Conflict resolution rule: Prefer LLNA over CCS where both exist
        llna_group = group[group["source"] == "NICEATM LLNA"]
        if not llna_group.empty:
            active_group = llna_group
        else:
            active_group = group
            
        first = active_group.iloc[0]
        n_records = len(group) # count total records from all sources
        
        # Perform majority vote
        binary_classes = active_group["raw_binary"].tolist()
        ghs_classes = active_group["raw_ghs"].tolist()
        
        # 1. Resolve Binary Class
        bin_counts = pd.Series(binary_classes).value_counts()
        if len(bin_counts) > 1 and bin_counts.iloc[0] == bin_counts.iloc[1]:
            # Tie: choose more conservative (sensitizer)
            resolved_binary = "sensitizer"
            quality_flags = list(first["quality_flags"])
            if "class_conflict" not in quality_flags:
                quality_flags.append("class_conflict")
        else:
            resolved_binary = bin_counts.index[0]
            quality_flags = list(first["quality_flags"])
            if len(bin_counts) > 1:
                if "class_conflict" not in quality_flags:
                    quality_flags.append("class_conflict")
                    
        # 2. Resolve GHS Class
        ghs_counts = pd.Series(ghs_classes).value_counts()
        if len(ghs_counts) > 1 and ghs_counts.iloc[0] == ghs_counts.iloc[1]:
            # Tie: choose the one with higher priority
            candidates = ghs_counts[ghs_counts == ghs_counts.iloc[0]].index.tolist()
            resolved_ghs = max(candidates, key=lambda c: ghs_priority.get(c, 0))
            if "class_conflict" not in quality_flags:
                quality_flags.append("class_conflict")
        else:
            resolved_ghs = ghs_counts.index[0]
            if len(ghs_counts) > 1:
                if "class_conflict" not in quality_flags:
                    quality_flags.append("class_conflict")
                    
        # Check if LLNA and CCS conflicted before filtering
        all_sources = group["source"].unique()
        if len(all_sources) > 1:
            bin_all = group["raw_binary"].unique()
            if len(bin_all) > 1:
                if "class_conflict" not in quality_flags:
                    quality_flags.append("class_conflict")
                    
        # Map GHS class name to class index value (as float)
        # GHS class index:
        # non -> 0
        # weak -> 1
        # moderate -> 2
        # strong -> 3
        # sensitizer (unknown grade) -> 4
        ghs_value_map = {
            "non": 0.0,
            "weak": 1.0,
            "moderate": 2.0,
            "strong": 3.0,
            "sensitizer": 4.0
        }
        resolved_value = ghs_value_map.get(resolved_ghs, 4.0)
        
        binary_value_map = {
            "non_sensitizer": 0.0,
            "sensitizer": 1.0
        }
        
        combined_records.append({
            "inchikey": ikey,
            "smiles_canonical": first["smiles_canonical"],
            "smiles_original": first["smiles_original"],
            "cas": first["cas"],
            "name": first["name"],
            "chembl_id": first["chembl_id"],
            "endpoint": endpoint,
            # Standard columns hold the 4-class GHS labels (or 5-class containing CCS sensitizer)
            "value": resolved_value,
            "value_units": first["value_units"],
            "value_log": None,
            "value_class": resolved_ghs,
            "species": "mouse" if "LLNA" in first["source"] else "human/guinea_pig",
            "species_taxonomy": None,
            "test_type": "LLNA" if "LLNA" in first["source"] else "CCS",
            "exposure_route": "topical",
            "exposure_duration_h": None,
            "effect": "skin_sensitization",
            "source": first["source"],
            "source_ref": first["source_ref"],
            "source_record_id": first["source_record_id"],
            "year_reported": None,
            "aggregation_n": n_records,
            "aggregation_method": "majority_vote" if n_records > 1 else "single",
            "aggregation_cv": None,
            "quality_flags": quality_flags,
            # Extra fields for both binary and GHS
            "value_class_binary": resolved_binary,
            "value_binary": binary_value_map.get(resolved_binary, 1.0),
            "value_class_ghs": resolved_ghs,
            "value_ghs": resolved_value
        })

    # Validate with Pydantic Schema
    valid_records = []
    for row in combined_records:
        try:
            # Validate against CuratedRecord (GHS columns are extra and will be ignored by Pydantic)
            rec = CuratedRecord(**row)
            # Re-attach extra columns to output dict
            dumped = rec.model_dump()
            dumped["value_class_binary"] = row["value_class_binary"]
            dumped["value_binary"] = row["value_binary"]
            dumped["value_class_ghs"] = row["value_class_ghs"]
            dumped["value_ghs"] = row["value_ghs"]
            valid_records.append(dumped)
        except Exception as e:
            curation_log.append({
                "smiles_original": row["smiles_original"],
                "stage": "schema_validation",
                "reason": str(e)
            })

    df_valid = pd.DataFrame(valid_records)

    # Save curated outputs
    pq_path = curated_dir / "curated.parquet"
    csv_path = curated_dir / "curated.csv"

    write_parquet_with_hash(df_valid, pq_path)
    write_csv_mirror(df_valid, csv_path)
    write_curation_log(curation_log, curated_dir / "curation_log.json")

    # Save stats
    stats = {
        "raw_records": len(df_llna) + len(df_ccs),
        "after_parse": len(df_raw_curated),
        "after_standardisation": len(df_raw_curated),
        "after_filter": len(df_raw_curated),
        "after_aggregation": len(df_valid),
        "rejection_rate": ((len(df_llna) + len(df_ccs)) - len(df_raw_curated)) / (len(df_llna) + len(df_ccs)) if (len(df_llna) + len(df_ccs)) > 0 else 0.0
    }

    with open(curated_dir / "curation_stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    print(f"Curation complete: {len(df_valid)} Skin Sensitization records saved.")

if __name__ == "__main__":
    run_curate()
