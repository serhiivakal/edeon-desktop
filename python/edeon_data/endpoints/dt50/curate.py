import os
import json
import math
import pandas as pd
from pathlib import Path
from rdkit import Chem

from edeon_data.shared.standardize import standardize_smiles
from edeon_data.shared.io import write_parquet_with_hash, write_csv_mirror, write_curation_log
from edeon_data.schema import CuratedRecord

RAW_DIR = Path("/home/svakal/Projects/Edeon/data/raw/dt50")

def run_curate(endpoint: str = None) -> None:
    """Standardizes and curates the Soil DT50 dataset, preserving all individual study records."""
    endpoint = "soil_dt50"
    curated_dir = Path(f"/home/svakal/Projects/Edeon/data/curated/{endpoint}/v1.0")
    curated_dir.mkdir(parents=True, exist_ok=True)

    csv_path = RAW_DIR / "envipath" / "soil_package.csv"
    if not csv_path.exists():
        raise FileNotFoundError("Raw Soil DT50 EAWAG-SOIL dataset CSV not found. Run acquire first.")

    print("Loading and curating Soil DT50 EAWAG-SOIL dataset...")
    
    df_raw = pd.read_csv(csv_path)
    total_raw_count = len(df_raw)
    
    processed_records = []
    curation_log = []
    atom_allowlist = {"H", "B", "C", "N", "O", "F", "Si", "P", "S", "Cl", "Se", "Br", "I"}
    
    for idx, row in df_raw.iterrows():
        smi_raw = str(row.get("smiles", "")).strip()
        study_id = str(row.get("study_id", "")).strip()
        val_str = str(row.get("dt50_value", "")).strip()
        name = str(row.get("name", "")) if pd.notna(row.get("name")) else None
        cas = str(row.get("cas", "")) if pd.notna(row.get("cas")) else None
        
        try:
            year_reported = int(row.get("year_reported")) if pd.notna(row.get("year_reported")) else None
        except (ValueError, TypeError):
            year_reported = None
            
        if not smi_raw or smi_raw == "nan":
            curation_log.append({
                "smiles_original": None,
                "stage": "parsing",
                "reason": f"missing_smiles_for_study:{study_id}"
            })
            continue
            
        try:
            value = float(val_str)
            if value <= 0:
                curation_log.append({
                    "smiles_original": smi_raw,
                    "stage": "activity_filter",
                    "reason": f"non_positive_value:{value}"
                })
                continue
            value_log = math.log10(value)
        except ValueError:
            curation_log.append({
                "smiles_original": smi_raw,
                "stage": "activity_filter",
                "reason": f"invalid_value_str:{val_str}"
            })
            continue
            
        # Standardize chemical structure
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
            "value": value,
            "value_units": "days",
            "value_log": value_log,
            "value_class": None,
            "species": "soil",
            "species_taxonomy": None,
            "test_type": None,
            "exposure_route": "soil",
            "exposure_duration_h": None,
            "effect": "degradation",
            "source": "EAWAG-SOIL via enviPath",
            "source_ref": "https://envipath.org",
            "source_record_id": study_id,
            "year_reported": year_reported,
            "quality_flags": flags
        })

    if not processed_records:
        raise ValueError("No Soil DT50 records successfully curated.")

    df_dt50 = pd.DataFrame(processed_records)

    # Compute compound-level statistics (n and CV) but preserve each record as its own row
    curated_records = []
    all_ikeys = df_dt50["inchikey"].unique()

    for ikey in all_ikeys:
        group = df_dt50[df_dt50["inchikey"] == ikey]
        n_records = len(group)
        
        # Calculate CV (Coefficient of Variation) of values for this compound
        if n_records > 1:
            values = group["value"].tolist()
            mean_val = sum(values) / n_records
            if mean_val > 0:
                variance = sum((x - mean_val) ** 2 for x in values) / (n_records - 1)
                std_dev = math.sqrt(variance)
                cv = std_dev / mean_val
            else:
                cv = 0.0
        else:
            cv = 0.0
            
        for _, row in group.iterrows():
            flags = list(row["quality_flags"])
            if n_records > 10 and cv > 1.0:
                if "extreme_variance" not in flags:
                    flags.append("extreme_variance")
            elif cv > 0.5:
                if "high_cv" not in flags:
                    flags.append("high_cv")
                    
            record_dict = row.to_dict()
            record_dict["aggregation_n"] = n_records
            record_dict["aggregation_method"] = "single"
            record_dict["aggregation_cv"] = float(cv) if cv > 0 else None
            record_dict["quality_flags"] = flags
            
            # Keep study_id column in the output dict for downstream modeling
            record_dict["study_id"] = row["source_record_id"]
            
            curated_records.append(record_dict)

    # Validate with Pydantic Schema
    valid_records = []
    for row in curated_records:
        try:
            # Pydantic validation (ignores extra key 'study_id')
            rec = CuratedRecord(**row)
            # Make sure 'study_id' is preserved in the dumped dict we save to parquet/csv
            dumped = rec.model_dump()
            dumped["study_id"] = row["study_id"]
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
        "raw_records": total_raw_count,
        "after_parse": len(processed_records),
        "after_standardisation": len(processed_records),
        "after_filter": len(processed_records),
        "after_aggregation": len(df_valid),
        "rejection_rate": (total_raw_count - len(processed_records)) / total_raw_count if total_raw_count > 0 else 0.0
    }

    with open(curated_dir / "curation_stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    print(f"Curation complete: {len(df_valid)} Soil DT50 records saved.")

if __name__ == "__main__":
    run_curate()
