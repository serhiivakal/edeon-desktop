import os
import json
import math
import zipfile
import re
import pandas as pd
from pathlib import Path
from rdkit import Chem

from edeon_data.shared.standardize import standardize_smiles
from edeon_data.shared.activity import aggregate_records
from edeon_data.shared.io import write_parquet_with_hash, write_csv_mirror, write_curation_log
from edeon_data.schema import CuratedRecord

RAW_DIR = Path("/home/svakal/Projects/Edeon/data/raw/earthworm")

def run_curate(endpoint: str = None) -> None:
    """Standardizes and curates the Earthworm LC50 dataset from the QsarDB zip archive."""
    endpoint = "earthworm_acute_lc50"
    curated_dir = Path(f"/home/svakal/Projects/Edeon/data/curated/{endpoint}/v1.0")
    curated_dir.mkdir(parents=True, exist_ok=True)

    zip_path = RAW_DIR / "final_arch_exp.zip"
    if not zip_path.exists():
        raise FileNotFoundError("Raw Earthworm QsarDB dataset zip not found. Run acquire first.")

    print("Loading and curating Earthworm QsarDB zip archive...")
    
    processed_records = []
    curation_log = []
    atom_allowlist = {"H", "B", "C", "N", "O", "F", "Si", "P", "S", "Cl", "Se", "Br", "I"}
    
    # Read zip contents
    with zipfile.ZipFile(zip_path, "r") as z:
        # Read the properties/acute_mg_kg/values file
        if "properties/acute_mg_kg/values" not in z.namelist():
            raise FileNotFoundError("Expected 'properties/acute_mg_kg/values' inside QsarDB archive.")
            
        values_content = z.read("properties/acute_mg_kg/values").decode("utf-8")
        
        # Read compounds.xml to map IDs to Names and CAS
        cas_map = {}
        name_map = {}
        if "compounds/compounds.xml" in z.namelist():
            compounds_xml = z.read("compounds/compounds.xml").decode("utf-8")
            # Parse using regex to avoid namespace issues
            compounds = re.findall(r'<compound>.*?</compound>', compounds_xml, re.DOTALL)
            for comp in compounds:
                cid_match = re.search(r'<id>(.*?)</id>', comp)
                name_match = re.search(r'<name>(.*?)</name>', comp)
                cas_match = re.search(r'<cas>(.*?)</cas>', comp)
                if cid_match:
                    cid = cid_match.group(1).strip()
                    if name_match:
                        name_map[cid] = name_match.group(1).strip()
                    if cas_match:
                        cas_map[cid] = cas_match.group(1).strip()
        
        # Parse values and standardise
        total_raw_count = 0
        for line in values_content.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) != 2:
                continue
                
            total_raw_count += 1
            cid, val_str = parts[0].strip(), parts[1].strip()
            
            # Find SMILES file
            smiles_file = f"compounds/{cid}/daylight-smiles"
            if smiles_file not in z.namelist():
                curation_log.append({
                    "smiles_original": None,
                    "stage": "parsing",
                    "reason": f"missing_smiles_file_for_compound:{cid}"
                })
                continue
                
            smi_raw = z.read(smiles_file).decode("utf-8").strip()
            if not smi_raw:
                curation_log.append({
                    "smiles_original": None,
                    "stage": "parsing",
                    "reason": f"empty_smiles_for_compound:{cid}"
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
                
            cas = cas_map.get(cid)
            name = name_map.get(cid)
            
            processed_records.append({
                "inchikey": ikey,
                "smiles_canonical": smi_canon,
                "smiles_original": smi_raw,
                "cas": cas,
                "name": name,
                "chembl_id": None,
                "endpoint": endpoint,
                "value": value,
                "value_units": "mg/kg soil",
                "value_log": value_log,
                "value_class": None,
                "species": "Eisenia fetida",
                "species_taxonomy": "Animalia;Annelida;Clitellata;Haplotaxida;Lumbricidae;Eisenia;Eisenia fetida",
                "test_type": "OECD 207",
                "exposure_route": "soil",
                "exposure_duration_h": 336.0,
                "effect": "mortality",
                "source": "Kotli et al. 2024 (QDB.258)",
                "source_ref": "https://doi.org/10.15152/QDB.258",
                "source_record_id": cid,
                "year_reported": 2024,
                "quality_flags": flags
            })

    if not processed_records:
        raise ValueError("No Earthworm records successfully curated.")

    df_earthworm = pd.DataFrame(processed_records)

    # Group by InChIKey and aggregate duplicates
    combined_records = []
    all_ikeys = df_earthworm["inchikey"].unique()

    for ikey in all_ikeys:
        group = df_earthworm[df_earthworm["inchikey"] == ikey]
        agg_res = aggregate_records(group, mode="regression")
        first = group.iloc[0]

        combined_records.append({
            "inchikey": ikey,
            "smiles_canonical": agg_res.get("smiles_canonical", first["smiles_canonical"]),
            "smiles_original": first["smiles_original"],
            "cas": first["cas"],
            "name": first["name"],
            "chembl_id": first["chembl_id"],
            "endpoint": endpoint,
            "value": agg_res["value"],
            "value_units": "mg/kg soil",
            "value_log": agg_res["value_log"],
            "value_class": None,
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
            "aggregation_n": len(group),
            "aggregation_method": agg_res["aggregation_method"],
            "aggregation_cv": agg_res["aggregation_cv"],
            "quality_flags": agg_res["quality_flags"]
        })

    df_agg = pd.DataFrame(combined_records)

    # Validate with Pydantic Schema
    valid_records = []
    for idx, row in df_agg.iterrows():
        try:
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

    print(f"Curation complete: {len(df_valid)} unique Earthworm records saved.")

if __name__ == "__main__":
    run_curate()
