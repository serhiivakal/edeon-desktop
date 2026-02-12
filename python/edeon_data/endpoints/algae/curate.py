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

RAW_DIR = Path("/home/svakal/Projects/Edeon/data/raw/algae")
FISH_RAW_DIR = Path("/home/svakal/Projects/Edeon/data/raw/fish")
ECOTOX_DIR = FISH_RAW_DIR / "ecotox_ascii_03_12_2026"

def clean_cas(cas) -> str:
    """Cleans raw CAS numbers to standard hyphenated format (e.g. C78342 -> 78-34-2)."""
    if pd.isna(cas):
        return None
    c_str = str(cas).strip().replace(" ", "")
    c_digits = "".join([x for x in c_str if x.isdigit()])
    if len(c_digits) > 4:
        return f"{c_digits[:-3]}-{c_digits[-3:-1]}-{c_digits[-1]}"
    return c_str

def run_curate(endpoint: str = None) -> None:
    """Standardizes and curates the Algae Growth EC50 dataset."""
    endpoint = "algae_growth_ec50"
    curated_dir = Path(f"/home/svakal/Projects/Edeon/data/curated/{endpoint}/v1.0")
    curated_dir.mkdir(parents=True, exist_ok=True)

    mapping_file = RAW_DIR / "cas_to_smiles.json"
    if not mapping_file.exists():
        # Fall back to fish cache if local algae cache doesn't exist
        fish_mapping = FISH_RAW_DIR / "cas_to_smiles.json"
        if fish_mapping.exists():
            mapping_file = fish_mapping
        else:
            raise FileNotFoundError(f"CAS-to-SMILES mapping file not found. Run acquire first.")

    with open(mapping_file, "r") as f:
        cas_to_smiles = json.load(f)

    print("Loading ECOTOX data tables for Algae...")
    # 1. Species map
    species_df = pd.read_csv(ECOTOX_DIR / "validation/species.txt", sep="|", low_memory=False)
    species_nums = {58471, 58477, 479, 17449}
    species_filtered = species_df[species_df["species_number"].isin(species_nums)]
    species_map = species_filtered.set_index("species_number")["latin_name"].to_dict()
    species_tax_map = species_filtered.set_index("species_number").apply(
        lambda r: f"{r['kingdom']};{r['phylum_division']};{r['subphylum_div']};{r['superclass']};{r['class']};{r['tax_order']};{r['family']};{r['genus']};{r['latin_name']}",
        axis=1
    ).to_dict()

    # 2. Match tests
    tests_iter = pd.read_csv(
        ECOTOX_DIR / "tests.txt",
        sep="|",
        usecols=["test_id", "test_cas", "species_number", "exposure_type", "published_date"],
        chunksize=100000,
        low_memory=False
    )
    df_tests = pd.concat([chunk[chunk["species_number"].isin(species_nums)] for chunk in tests_iter])

    non_aquatic_exposures = {
        "FD", "IP", "GV", "OR", "FD/", "IP/", "IJ", "IV", "IG/", "DT/", "IJ/", "IM", "DT", 
        "IB", "GV/", "IM/", "DM", "IVT", "ICL", "OM", "UN", "SD", "ID", "GI", "IC", "GE"
    }
    df_tests = df_tests[~df_tests["exposure_type"].isin(non_aquatic_exposures)]
    test_to_cas = df_tests.set_index("test_id")["test_cas"].to_dict()
    test_to_species = df_tests.set_index("test_id")["species_number"].to_dict()
    
    # Map test_id -> year reported
    def parse_year(dt_str):
        if pd.isna(dt_str):
            return None
        parts = str(dt_str).strip().split("/")
        if len(parts) >= 3:
            try:
                return int(parts[-1])
            except ValueError:
                pass
        return None
    test_to_year = df_tests.set_index("test_id")["published_date"].apply(parse_year).to_dict()

    # 3. Match results
    results_iter = pd.read_csv(
        ECOTOX_DIR / "results.txt",
        sep="|",
        usecols=[
            "result_id", "test_id", "obs_duration_mean", "obs_duration_unit", 
            "endpoint", "effect", "conc1_mean", "conc1_unit"
        ],
        chunksize=100000,
        low_memory=False
    )

    matched_results = []
    for chunk in results_iter:
        chunk = chunk[chunk["test_id"].isin(test_to_cas.keys())].copy()
        if len(chunk) == 0:
            continue
        chunk = chunk[chunk["endpoint"].astype(str).str.strip().str.upper() == "EC50"]
        chunk = chunk[chunk["effect"].astype(str).str.strip().str.upper().isin(["GRO", "POP"])]

        def check_duration(row):
            try:
                val = float(row["obs_duration_mean"])
                unit = str(row["obs_duration_unit"]).strip().lower()
                h = val if unit == "h" else (val * 24.0 if unit == "d" else -1.0)
                # 72h with 10% tolerance is 64.8h to 79.2h
                return 64.8 <= h <= 79.2
            except ValueError:
                return False

        chunk = chunk[chunk.apply(check_duration, axis=1)]
        matched_results.append(chunk)

    df_results = pd.concat(matched_results)
    print(f"Loaded {len(df_results)} raw matched Algae results from ECOTOX.")

    curation_log = []
    processed_records = []
    atom_allowlist = {"H", "B", "C", "N", "O", "F", "Si", "P", "S", "Cl", "Se", "Br", "I"}
    std_cache = {}

    # Process Algae records
    for idx, row in df_results.iterrows():
        test_id = row["test_id"]
        raw_cas = test_to_cas.get(test_id)
        if pd.isna(raw_cas):
            continue

        # Clean and standardise CAS key
        cas_str = clean_cas(raw_cas)
        if not cas_str:
            continue

        # Resolve raw SMILES from cache
        smi_raw_mapping = cas_to_smiles.get(cas_str)
        if not smi_raw_mapping:
            curation_log.append({
                "smiles_original": cas_str,
                "stage": "parse",
                "reason": "missing_smiles_mapping"
            })
            continue

        smi_raw = smi_raw_mapping.get("smiles")
        if not smi_raw:
            curation_log.append({
                "smiles_original": cas_str,
                "stage": "parse",
                "reason": "missing_smiles_mapping"
            })
            continue
        
        # Unit conversion
        val_str = str(row["conc1_mean"]).strip()
        try:
            val_raw = float(val_str)
        except ValueError:
            curation_log.append({
                "smiles_original": smi_raw,
                "stage": "activity_filter",
                "reason": f"invalid_concentration_value:{val_str}"
            })
            continue

        if val_raw <= 0:
            curation_log.append({
                "smiles_original": smi_raw,
                "stage": "activity_filter",
                "reason": f"non_positive_concentration_value:{val_raw}"
            })
            continue

        unit = str(row["conc1_unit"]).strip().lower()
        val_mg_l = None

        # Convert to mg/L
        if unit in ["mg/l", "ai mg/l", "ae mg/l", "mg/dm3", "ppm", "ai ppm"]:
            val_mg_l = val_raw
        elif unit in ["ug/l", "ai ug/l", "ug/dm3", "ng/ml", "ppb", "ai ppb"]:
            val_mg_l = val_raw / 1000.0
        elif unit in ["ai ng/l"]:
            val_mg_l = val_raw / 1000000.0
        elif unit in ["g/l"]:
            val_mg_l = val_raw * 1000.0
        elif unit in ["m", "mm", "um", "nm", "umol/l", "nmol/l", "mmol/l"]:
            mw_pc = smi_raw_mapping.get("mw")
            if mw_pc:
                try:
                    mw_val = float(mw_pc)
                    if unit == "m":
                        val_mg_l = val_raw * 1000.0 * mw_val
                    elif unit in ["mm", "mmol/l"]:
                        val_mg_l = val_raw * mw_val
                    elif unit in ["um", "umol/l"]:
                        val_mg_l = val_raw * mw_val / 1000.0
                    elif unit in ["nm", "nmol/l"]:
                        val_mg_l = val_raw * mw_val / 1000000.0
                except ValueError:
                    pass

        if val_mg_l is None:
            curation_log.append({
                "smiles_original": smi_raw,
                "stage": "activity_filter",
                "reason": f"unsupported_concentration_unit:{unit}"
            })
            continue

        # Chemical Standardisation
        if smi_raw not in std_cache:
            std_cache[smi_raw] = standardize_smiles(
                smi_raw,
                atom_allowlist=atom_allowlist
            )
        smi_canon, ikey, cached_flags = std_cache[smi_raw]
        flags = list(cached_flags) if cached_flags is not None else []

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

        # Calculate exact MW of standardized parent and log10 molar
        try:
            std_mol = Chem.MolFromSmiles(smi_canon)
            mw = Descriptors.ExactMolWt(std_mol)
            ec50_mol_per_l = (val_mg_l / 1000.0) / mw
            value_log = math.log10(ec50_mol_per_l)
        except Exception:
            value_log = math.log10(val_mg_l)
            flags.append("mw_conversion_failed_log_fallback")

        species_num = test_to_species.get(test_id)
        species_name = species_map.get(species_num, "Algae unspecified")
        species_taxonomy = species_tax_map.get(species_num, None)
        year_reported = test_to_year.get(test_id)

        processed_records.append({
            "inchikey": ikey,
            "smiles_canonical": smi_canon,
            "smiles_original": smi_raw,
            "cas": cas_str,
            "name": None,
            "chembl_id": None,
            "endpoint": endpoint,
            "value": val_mg_l,
            "value_units": "mg/L",
            "value_log": value_log,
            "value_class": None,
            "species": species_name,
            "species_taxonomy": species_taxonomy,
            "test_type": "in_vivo",
            "exposure_route": "aquatic",
            "exposure_duration_h": 72.0,
            "effect": "growth_rate" if row["effect"].strip().upper() == "GRO" else "biomass",
            "source": "EPA ECOTOX ASCII",
            "source_ref": "EPA ECOTOX",
            "source_record_id": str(row["result_id"]),
            "year_reported": year_reported,
            "quality_flags": flags
        })

    if not processed_records:
        raise ValueError("No Algae records successfully curated.")

    df_ecotox = pd.DataFrame(processed_records)

    # 4. Deduplicate and Consolidate: Group by InChIKey
    combined_records = []
    all_ikeys = df_ecotox["inchikey"].unique()

    for ikey in all_ikeys:
        group = df_ecotox[df_ecotox["inchikey"] == ikey]
        
        # Prefer ErC50 (growth_rate) over EbC50 (biomass) where both exist for the same compound
        if "growth_rate" in group["effect"].values and "biomass" in group["effect"].values:
            group = group[group["effect"] == "growth_rate"]

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
            "value_units": "mg/L",
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
        "raw_records": len(df_results),
        "after_parse": len(processed_records),
        "after_standardisation": len(processed_records),
        "after_filter": len(processed_records),
        "after_aggregation": len(df_valid),
        "rejection_rate": (len(df_results) - len(processed_records)) / len(df_results) if len(df_results) > 0 else 0.0
    }

    with open(curated_dir / "curation_stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    print(f"Curation complete: {len(df_valid)} unique algae records saved.")

if __name__ == "__main__":
    run_curate()
