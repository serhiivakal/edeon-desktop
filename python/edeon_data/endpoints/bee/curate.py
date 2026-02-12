import os
import json
import math
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List

from edeon_data.shared.standardize import standardize_smiles
from edeon_data.shared.activity import aggregate_records
from edeon_data.shared.io import write_parquet_with_hash, write_csv_mirror, write_curation_log
from edeon_data.schema import CuratedRecord

RAW_DIR = Path("/home/svakal/Projects/Edeon/data/raw/bee")

def load_and_process_ecotox_lookup() -> Dict[tuple, float]:
    """
    Loads raw ecotox.csv and builds a median continuous toxicity lookup table
    keyed by (CAS, toxicity_type) mapped to ug/bee.
    """
    path = RAW_DIR / "ecotox.csv"
    if not path.exists():
        return {}
        
    df = pd.read_csv(path, sep="|")
    df.columns = [c.strip().replace('"', '') for c in df.columns]
    
    # Clean NR
    df = df[df["Observed Response Mean"] != "NR"]
    df["Observed Response Mean"] = df["Observed Response Mean"].astype(str).str.replace("/", "")
    df["Observed Response Mean"] = pd.to_numeric(df["Observed Response Mean"], errors="coerce")
    df = df[df["Observed Response Mean"].notna() & (df["Observed Response Mean"] > 0)]
    
    # Unit conversion helper
    def convert_to_ug_bee(row):
        unit = str(row["Observed Response Units"]).strip()
        val = row["Observed Response Mean"]
        if unit in ["AI ug/org", "AI ug/org/d", "ug/bee", "ug/org", "ug/org/d"]:
            return val
        elif unit in ["AI ng/org", "AI ng/org/d", "ng/org"]:
            return val / 1000.0
        elif unit in ["AI mg/org", "mg/bee", "mg/org"]:
            return val * 1000.0
        elif unit == "pg/org":
            return val / 1000000.0
        return None

    df["value_ug"] = df.apply(convert_to_ug_bee, axis=1)
    df = df[df["value_ug"].notna()]
    
    # Standardize CAS
    def std_cas(cas):
        cas_str = str(cas).strip().replace("-", "").replace(" ", "")
        if cas_str.isdigit():
            return f"{cas_str[:-3]}-{cas_str[-3:-1]}-{cas_str[-1]}"
        return cas
    df["CAS_std"] = df["CAS Number"].apply(std_cas)
    
    # Map Exposure Type to Toxicity Type
    def get_toxicity_type(exp):
        exp = str(exp).strip()
        if exp in ["Diet, unspecified", "Drinking water", "Food"]:
            return "Oral"
        elif exp in ["Dermal", "Direct application", "Topical, general"]:
            return "Contact"
        return "Other"
    df["tox_type"] = df["Exposure Type"].apply(get_toxicity_type)
    
    # Group by (CAS, tox_type) and take the median
    medians = df.groupby(["CAS_std", "tox_type"])["value_ug"].median().to_dict()
    return medians


def run_curate(endpoint: str) -> None:
    """Processes, cleans, standardises, and normalises honey bee dataset records."""
    assert endpoint in ["bee_acute_oral_ld50", "bee_acute_contact_ld50"]
    
    # Mappings
    tox_type_filter = "Oral" if endpoint == "bee_acute_oral_ld50" else "Contact"
    curated_dir = Path(f"/home/svakal/Projects/Edeon/data/curated/{endpoint}/v1.0")
    curated_dir.mkdir(parents=True, exist_ok=True)
    
    # Load dataset_final.csv
    final_path = RAW_DIR / "dataset_final.csv"
    if not final_path.exists():
        raise FileNotFoundError(f"ApisTox dataset_final.csv not found at {final_path}. Run acquire first.")
        
    df_final = pd.read_csv(final_path)
    
    # Filter to endpoint type
    df_sub = df_final[df_final["toxicity_type"] == tox_type_filter].copy()
    
    # Load ECOTOX lookup medians for continuous mapping
    ecotox_lookup = load_and_process_ecotox_lookup()
    
    curation_log = []
    processed_records = []
    
    # Atom allowlist: include Copper (Cu) as per Task B1 specs
    atom_allowlist = {"H", "B", "C", "N", "O", "F", "Si", "P", "S", "Cl", "Se", "Br", "I", "Cu"}
    
    for idx, row in df_sub.iterrows():
        smi_raw = row["SMILES"]
        cas = row["CAS"]
        label = int(row["label"])
        ppdb_level = int(row["ppdb_level"]) if pd.notna(row["ppdb_level"]) else -1
        
        # 1. Look up continuous value
        value = ecotox_lookup.get((cas, tox_type_filter))
        if value is None:
            # Impute from binned categories
            if ppdb_level == 2:
                value = 0.5
            elif ppdb_level == 1:
                value = 5.0 if label == 1 else 50.0
            elif ppdb_level == 0:
                value = 500.0
            else:
                value = 5.0 if label == 1 else 50.0
                
        # 2. Chemical Standardisation
        smi_canon, ikey, flags = standardize_smiles(
            smi_raw,
            atom_allowlist=atom_allowlist
        )
        
        if smi_canon is None:
            # Log rejection
            reason = flags[0] if flags else "unknown_reason"
            stage = "parse"
            if "chembl" in reason:
                stage = "chembl_pipeline"
            elif "disallowed_atoms" in reason:
                stage = "atom_filter"
            elif "mw_out_of_range" in reason:
                stage = "size_filter"
                
            curation_log.append({
                "smiles_original": smi_raw,
                "stage": stage,
                "reason": reason
            })
            continue
            
        # 3. Create Curated Record fields
        value_log = math.log10(value) if value > 0 else -6.0
        value_class = "toxic" if label == 1 else "nontoxic"
        
        processed_records.append({
            "inchikey": ikey,
            "smiles_canonical": smi_canon,
            "smiles_original": smi_raw,
            "cas": cas,
            "name": row["name"] if pd.notna(row["name"]) else None,
            "chembl_id": None,
            "endpoint": endpoint,
            "value": value,
            "value_units": "ug/bee",
            "value_log": value_log,
            "value_class": value_class,
            "species": "Apis mellifera",
            "species_taxonomy": "Animalia;Arthropoda;Insecta;Hymenoptera;Apidae;Apis;Apis mellifera",
            "test_type": None,
            "exposure_route": "oral" if endpoint == "bee_acute_oral_ld50" else "contact",
            "exposure_duration_h": 48.0, # default ECOTOX / standard testing duration
            "effect": "mortality",
            "source": f"ApisTox-{row['source']}",
            "source_ref": "10.1038/s41597-024-04232-w",
            "source_record_id": str(row["CID"]) if pd.notna(row["CID"]) else None,
            "year_reported": int(row["year"]) if pd.notna(row["year"]) else None,
            "quality_flags": flags
        })
        
    if not processed_records:
        raise ValueError(f"No records successfully processed for endpoint {endpoint}.")
        
    df_curated = pd.DataFrame(processed_records)
    
    # 4. Duplicate Aggregation grouped by InChIKey
    aggregated_rows = []
    for ikey, group in df_curated.groupby("inchikey"):
        agg_res = aggregate_records(group, mode="regression")
        
        # Get first row's static details
        first = group.iloc[0]
        
        # Pull the majority or first value_class
        value_class = group["value_class"].value_counts().index[0]
        
        aggregated_rows.append({
            "inchikey": ikey,
            "smiles_canonical": agg_res.get("smiles_canonical", first["smiles_canonical"]),
            "smiles_original": first["smiles_original"],
            "cas": first["cas"],
            "name": first["name"],
            "chembl_id": first["chembl_id"],
            "endpoint": endpoint,
            "value": agg_res["value"],
            "value_units": "ug/bee",
            "value_log": agg_res["value_log"],
            "value_class": value_class,
            "species": first["species"],
            "species_taxonomy": first["species_taxonomy"],
            "test_type": first["test_type"],
            "exposure_route": first["exposure_route"],
            "exposure_duration_h": first["exposure_duration_h"],
            "effect": first["effect"],
            "source": first["source"],
            "source_ref": first["source_ref"],
            "source_record_id": first["source_record_id"],
            "year_reported": first["year_reported"],
            "aggregation_n": agg_res["aggregation_n"],
            "aggregation_method": agg_res["aggregation_method"],
            "aggregation_cv": agg_res["aggregation_cv"],
            "quality_flags": agg_res["quality_flags"]
        })
        
    df_agg = pd.DataFrame(aggregated_rows)
    
    # Validate with Pydantic
    valid_records = []
    for idx, row in df_agg.iterrows():
        try:
            # Pydantic conversion and validation
            rec = CuratedRecord(**row.to_dict())
            valid_records.append(rec.model_dump())
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
    
    # Save statistics for pipeline tracking
    stats = {
        "raw_records": len(df_sub),
        "after_parse": len(processed_records) + len([l for l in curation_log if l["stage"] == "parse"]),
        "after_standardisation": len(processed_records),
        "after_filter": len(processed_records),
        "after_aggregation": len(df_agg),
        "rejection_rate": (len(df_sub) - len(processed_records)) / len(df_sub) if len(df_sub) > 0 else 0.0
    }
    
    stats_path = curated_dir / "curation_stats.json"
    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2)
