import os
import json
import math
import pandas as pd
from pathlib import Path
from rdkit import Chem
from rdkit.Chem import Descriptors

from edeon_data.shared.standardize import standardize_smiles
from edeon_data.shared.activity import aggregate_records
from edeon_data.shared.io import write_parquet_with_hash, write_csv_mirror, write_curation_log
from edeon_data.schema import CuratedRecord

RAW_DIR = Path("/home/svakal/Projects/Edeon/data/raw/koc")
OPERA_DIR = RAW_DIR / "opera"

def run_curate(endpoint: str = None) -> None:
    """Standardizes and curates the Soil Koc dataset from OPERA SDF files."""
    endpoint = "soil_koc"
    curated_dir = Path(f"/home/svakal/Projects/Edeon/data/curated/{endpoint}/v1.0")
    curated_dir.mkdir(parents=True, exist_ok=True)

    tr_path = OPERA_DIR / "TR_KOC_545.sdf"
    tst_path = OPERA_DIR / "TST_KOC_184.sdf"

    if not tr_path.exists() or not tst_path.exists():
        raise FileNotFoundError(f"Raw OPERA KOC SDF files not found. Run acquire first.")

    print("Loading and curating OPERA KOC SDF files...")
    suppliers = [
        ("OPERA Training", Chem.SDMolSupplier(str(tr_path))),
        ("OPERA Test", Chem.SDMolSupplier(str(tst_path)))
    ]

    processed_records = []
    curation_log = []
    atom_allowlist = {"H", "B", "C", "N", "O", "F", "Si", "P", "S", "Cl", "Se", "Br", "I"}
    std_cache = {}

    # Define SMARTS patterns for acid/base checking
    acid_patterns = [
        Chem.MolFromSmarts("[CX3](=O)[OX2H1]"),  # Carboxylic acid
        Chem.MolFromSmarts("[OX2H1]-c"),         # Phenol
        Chem.MolFromSmarts("[SX4](=O)(=O)[NX3H1]") # Sulfonamide
    ]
    base_pattern = Chem.MolFromSmarts("[NX3;H2,H1,H0;!$(N[C,S,P]=O)]") # Aliphatic amine

    total_raw_count = 0

    for set_name, suppl in suppliers:
        for idx, mol in enumerate(suppl):
            total_raw_count += 1
            if mol is None:
                continue

            # Extract properties
            cas = mol.GetProp("CAS") if mol.HasProp("CAS") else mol.GetProp("source_casrn") if mol.HasProp("source_casrn") else None
            name = mol.GetProp("preferred_name") if mol.HasProp("preferred_name") else mol.GetProp("NAME") if mol.HasProp("NAME") else None
            smi_raw = mol.GetProp("SMILES") if mol.HasProp("SMILES") else None
            log_koc_str = mol.GetProp("LogKOC") if mol.HasProp("LogKOC") else None

            if not smi_raw or not log_koc_str:
                continue

            try:
                value_log = float(log_koc_str)
                value = 10 ** value_log
            except ValueError:
                curation_log.append({
                    "smiles_original": smi_raw,
                    "stage": "activity_filter",
                    "reason": f"invalid_log_koc:{log_koc_str}"
                })
                continue

            # Standardise structure
            if smi_raw not in std_cache:
                std_cache[smi_raw] = standardize_smiles(
                    smi_raw,
                    atom_allowlist=atom_allowlist
                )
            smi_canon, ikey, cached_flags = std_cache[smi_raw]
            flags = list(cached_flags) if cached_flags is not None else []

            if smi_canon is None:
                reason = flags[0] if flags else "unknown_reason"
                curation_log.append({
                    "smiles_original": smi_raw,
                    "stage": "standardisation",
                    "reason": reason
                })
                continue

            # Detect ionizability using SMARTS heuristics on the standardized mol
            std_mol = Chem.MolFromSmiles(smi_canon)
            if std_mol:
                is_acid = any(std_mol.HasSubstructMatch(pat) for pat in acid_patterns)
                is_base = std_mol.HasSubstructMatch(base_pattern)
                if is_acid:
                    flags.append("ionizable_acid")
                if is_base:
                    flags.append("ionizable_base")

            processed_records.append({
                "inchikey": ikey,
                "smiles_canonical": smi_canon,
                "smiles_original": smi_raw,
                "cas": cas,
                "name": name,
                "chembl_id": None,
                "endpoint": endpoint,
                "value": value,
                "value_units": "L/kg",
                "value_log": value_log,
                "value_class": None,
                "species": None,
                "species_taxonomy": None,
                "test_type": "in_silico_curated",
                "exposure_route": None,
                "exposure_duration_h": None,
                "effect": "partitioning",
                "source": "NIEHS OPERA",
                "source_ref": "https://github.com/NIEHS/OPERA",
                "source_record_id": mol.GetProp("dsstox_substance_id") if mol.HasProp("dsstox_substance_id") else str(idx),
                "year_reported": None,
                "quality_flags": flags
            })

    if not processed_records:
        raise ValueError("No Soil Koc records successfully curated.")

    df_opera = pd.DataFrame(processed_records)

    # Group by InChIKey and aggregate
    combined_records = []
    all_ikeys = df_opera["inchikey"].unique()

    for ikey in all_ikeys:
        group = df_opera[df_opera["inchikey"] == ikey]
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
            "value_units": "L/kg",
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

    print(f"Curation complete: {len(df_valid)} unique Soil Koc records saved.")

if __name__ == "__main__":
    run_curate()
