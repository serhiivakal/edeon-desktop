import os
import json
import math
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List
from rdkit import Chem
from rdkit.Chem import Descriptors

from edeon_data.shared.standardize import standardize_smiles
from edeon_data.shared.activity import aggregate_records
from edeon_data.shared.io import write_parquet_with_hash, write_csv_mirror, write_curation_log
from edeon_data.schema import CuratedRecord

RAW_DIR = Path("/home/svakal/Projects/Edeon/data/raw/rat_ld50")

def run_curate(endpoint: str = None) -> None:
    """Standardizes and curates the rat acute oral LD50 dataset."""
    endpoint = "rat_acute_oral_ld50"
    curated_dir = Path(f"/home/svakal/Projects/Edeon/data/curated/{endpoint}/v1.0")
    curated_dir.mkdir(parents=True, exist_ok=True)
    
    sdf_path = RAW_DIR / "Supplemental_Material_1" / "TrainingSet.sdf"
    if not sdf_path.exists():
        raise FileNotFoundError(f"CATMoS TrainingSet.sdf not found at {sdf_path}. Run acquire first.")
        
    print(f"Loading molecules from {sdf_path}...")
    suppl = Chem.SDMolSupplier(str(sdf_path))
    
    curation_log = []
    processed_records = []
    
    # Default organic atom allowlist
    atom_allowlist = {"H", "B", "C", "N", "O", "F", "Si", "P", "S", "Cl", "Se", "Br", "I"}
    
    for idx, m in enumerate(suppl):
        if m is None:
            curation_log.append({
                "smiles_original": f"index_{idx}",
                "stage": "parse",
                "reason": "mol_parse_failed"
            })
            continue
            
        # Extract properties
        cas = m.GetProp("CASRN").strip() if m.HasProp("CASRN") else None
        dtxsid = m.GetProp("DTXSID").strip() if m.HasProp("DTXSID") else None
        name = m.GetProp("Name").strip() if m.HasProp("Name") else None
        
        # Get numeric raw value (LD50_mgkg)
        ld50_str = m.GetProp("LD50_mgkg").strip() if m.HasProp("LD50_mgkg") else ""
        if not ld50_str:
            curation_log.append({
                "smiles_original": cas or f"index_{idx}",
                "stage": "activity_filter",
                "reason": "missing_ld50_value"
            })
            continue
            
        try:
            ld50_val = float(ld50_str)
        except ValueError:
            curation_log.append({
                "smiles_original": cas or f"index_{idx}",
                "stage": "activity_filter",
                "reason": f"invalid_ld50_value:{ld50_str}"
            })
            continue
            
        if ld50_val <= 0:
            curation_log.append({
                "smiles_original": cas or f"index_{idx}",
                "stage": "activity_filter",
                "reason": f"non_positive_ld50_value:{ld50_val}"
            })
            continue
            
        # Get raw SMILES for standardisation
        smi_raw = None
        if m.HasProp("Original_SMILES") and m.GetProp("Original_SMILES").strip():
            smi_raw = m.GetProp("Original_SMILES").strip()
        elif m.HasProp("Canonical_QSARr") and m.GetProp("Canonical_QSARr").strip():
            smi_raw = m.GetProp("Canonical_QSARr").strip()
        else:
            try:
                smi_raw = Chem.MolToSmiles(m)
            except Exception:
                pass
                
        if not smi_raw:
            curation_log.append({
                "smiles_original": cas or f"index_{idx}",
                "stage": "parse",
                "reason": "empty_raw_smiles"
            })
            continue
            
        # GHS mapping
        ghs_str = m.GetProp("GHS_category").strip() if m.HasProp("GHS_category") else ""
        value_class = None
        if ghs_str:
            try:
                ghs_cat = int(float(ghs_str))
                if 1 <= ghs_cat <= 5:
                    value_class = f"cat{ghs_cat}"
            except ValueError:
                pass
                
        # 2. Chemical Standardisation
        smi_canon, ikey, flags = standardize_smiles(
            smi_raw,
            atom_allowlist=atom_allowlist
        )
        
        if smi_canon is None:
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
            
        # Calculate value_log using standardized molecule's exact MW
        try:
            std_mol = Chem.MolFromSmiles(smi_canon)
            mw = Descriptors.ExactMolWt(std_mol)
            ld50_mmol = ld50_val / mw
            value_log = math.log10(ld50_mmol)
        except Exception:
            value_log = math.log10(ld50_val)
            flags.append("mw_conversion_failed_log_fallback")
            
        processed_records.append({
            "inchikey": ikey,
            "smiles_canonical": smi_canon,
            "smiles_original": smi_raw,
            "cas": cas,
            "name": name,
            "chembl_id": None,
            "endpoint": endpoint,
            "value": ld50_val,
            "value_units": "mg/kg",
            "value_log": value_log,
            "value_class": value_class,
            "species": "Rattus norvegicus",
            "species_taxonomy": "Animalia;Chordata;Mammalia;Rodentia;Muridae;Rattus;Rattus norvegicus",
            "test_type": "in_vivo",
            "exposure_route": "oral",
            "exposure_duration_h": None,
            "effect": "mortality",
            "source": "NICEATM-ICE-CATMoS",
            "source_ref": "10.1289/EHP8495",
            "source_record_id": dtxsid or cas,
            "year_reported": None,
            "quality_flags": flags
        })
        
    if not processed_records:
        raise ValueError("No records successfully processed.")
        
    df_curated = pd.DataFrame(processed_records)
    
    # 4. Duplicate Aggregation grouped by InChIKey
    aggregated_rows = []
    for ikey, group in df_curated.groupby("inchikey"):
        agg_res = aggregate_records(group, mode="regression")
        first = group.iloc[0]
        
        # GHS Class aggregation (majority vote, tie-broken by lowest category number i.e. highest toxicity)
        valid_classes = group["value_class"].dropna().tolist()
        value_class = None
        if valid_classes:
            counts = pd.Series(valid_classes).value_counts()
            max_count = counts.max()
            majority = counts[counts == max_count].index.tolist()
            if len(majority) == 1:
                value_class = majority[0]
            else:
                # Tie breaker: choose lowest category index (e.g. cat1 over cat2)
                value_class = sorted(majority, key=lambda c: int(c.replace("cat", "")))[0]
                
        aggregated_rows.append({
            "inchikey": ikey,
            "smiles_canonical": agg_res.get("smiles_canonical", first["smiles_canonical"]),
            "smiles_original": first["smiles_original"],
            "cas": first["cas"],
            "name": first["name"],
            "chembl_id": first["chembl_id"],
            "endpoint": endpoint,
            "value": agg_res["value"],
            "value_units": "mg/kg",
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
        "raw_records": len(suppl),
        "after_parse": len(processed_records) + len([l for l in curation_log if l["stage"] == "parse"]),
        "after_standardisation": len(processed_records),
        "after_filter": len(processed_records),
        "after_aggregation": len(df_agg),
        "rejection_rate": (len(suppl) - len(processed_records)) / len(suppl) if len(suppl) > 0 else 0.0
    }
    
    with open(curated_dir / "curation_stats.json", "w") as f:
        json.dump(stats, f, indent=2)
        
    print(f"Curation complete: {len(df_valid)} unique records saved.")
