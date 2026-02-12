import os
import json
import math
import re
import pandas as pd
from pathlib import Path
from rdkit import Chem
from rdkit.Chem import Descriptors

from edeon_data.shared.standardize import standardize_smiles
from edeon_data.shared.activity import aggregate_records
from edeon_data.shared.io import write_parquet_with_hash, write_csv_mirror, write_curation_log
from edeon_data.schema import CuratedRecord

RAW_DIR = Path("/home/svakal/Projects/Edeon/data/raw/bird")
FISH_RAW_DIR = Path("/home/svakal/Projects/Edeon/data/raw/fish")
ECOTOX_DIR = FISH_RAW_DIR / "ecotox_ascii_03_12_2026"

def clean_excel_escapes(text):
    """Decodes XML-style hex escapes from Excel (e.g. _x0028_ -> ()."""
    if not isinstance(text, str):
        return text
    return re.sub(r'_x([0-9a-fA-F]{4})_', lambda m: chr(int(m.group(1), 16)), text)

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
    """Standardizes and curates the Bird Acute Oral LD50 dataset."""
    endpoint = "bird_acute_oral_ld50"
    curated_dir = Path(f"/home/svakal/Projects/Edeon/data/curated/{endpoint}/v1.0")
    curated_dir.mkdir(parents=True, exist_ok=True)

    # Load CAS mapping from fish/daphnia/algae
    mapping_file = RAW_DIR / "cas_to_smiles.json"
    unified_mapping = {}
    
    # Gather from previous raw caches to maximize offline coverage
    for source_dir in ["fish", "daphnia", "algae"]:
        cache_path = Path(f"/home/svakal/Projects/Edeon/data/raw/{source_dir}/cas_to_smiles.json")
        if cache_path.exists():
            with open(cache_path) as f:
                unified_mapping.update(json.load(f))
                
    print(f"Loaded {len(unified_mapping)} unified structure mappings from existing caches.")

    processed_records = []
    curation_log = []
    atom_allowlist = {"H", "B", "C", "N", "O", "F", "Si", "P", "S", "Cl", "Se", "Br", "I"}
    std_cache = {}

    species_mapping_rules = {
        "Bobwhite quail": "Colinus virginianus",
        "Mallard duck": "Anas platyrhynchos",
        "Japanese quail": "Coturnix japonica",
        "Common pheasant": "Phasianus colchicus",
        "House sparrow": "Passer domesticus",
        "Quail": "Avian unspecified",
        "Duck": "Avian unspecified",
        "Bird": "Avian unspecified",
        "Common quail": "Avian unspecified"
    }

    # ==========================================
    # 1. PROCESS EFSA OPENFOODTOX DATA
    # ==========================================
    ref_points_path = RAW_DIR / "ReferencePoints_KJ_2023.xlsx"
    sub_char_path = RAW_DIR / "SubstanceCharacterisation_KJ_2023.xlsx"

    if ref_points_path.exists() and sub_char_path.exists():
        print("Loading and curating EFSA OpenFoodTox sheets...")
        df_ref = pd.read_excel(ref_points_path)
        df_sub = pd.read_excel(sub_char_path)

        # Join Substance Characterisation & Reference Points
        df_joined = pd.merge(df_ref, df_sub, on="Substance", how="inner")

        for idx, row in df_joined.iterrows():
            species_raw = clean_excel_escapes(row["Species"])
            endpoint_raw = clean_excel_escapes(row["Endpoint"])
            substance_name = clean_excel_escapes(row["Substance"])
            route_raw = str(clean_excel_escapes(row.get("Route", ""))).strip().lower()
            smi_raw = clean_excel_escapes(row.get("smiles"))

            if not species_raw or not endpoint_raw or not smi_raw:
                continue

            # Inclusions
            if species_raw not in species_mapping_rules:
                continue
            if endpoint_raw != "LD50":
                continue
            if "oral" not in route_raw:
                continue

            try:
                val_raw = float(row["value"])
            except ValueError:
                continue

            if val_raw <= 0 or pd.isna(val_raw):
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
                continue

            # log10 transformation on mg/kg bw
            value_log = math.log10(val_raw)
            species_clean = species_mapping_rules[species_raw]
            year_reported = int(row["Year"]) if not pd.isna(row["Year"]) else None

            processed_records.append({
                "inchikey": ikey,
                "smiles_canonical": smi_canon,
                "smiles_original": smi_raw,
                "cas": clean_cas(row.get("CASNumber")),
                "name": substance_name,
                "chembl_id": None,
                "endpoint": endpoint,
                "value": val_raw,
                "value_units": "mg/kg bw",
                "value_log": value_log,
                "value_class": None,
                "species": species_clean,
                "species_taxonomy": f"Animalia;Chordata;Aves;{species_clean}",
                "test_type": "in_vivo",
                "exposure_route": "oral",
                "exposure_duration_h": 24.0,
                "effect": "mortality",
                "source": "EFSA OpenFoodTox",
                "source_ref": "EFSA Chemical Hazards Database",
                "source_record_id": str(row.get("OutputID", idx)),
                "year_reported": year_reported,
                "quality_flags": flags
            })

    # ==========================================
    # 2. PROCESS EPA ECOTOX DATA
    # ==========================================
    print("Loading and curating ECOTOX bird records...")
    # Avian species mappings
    ecotox_species_nums = {
        2994: "Anas platyrhynchos",
        4435: "Coturnix japonica",
        4437: "Phasianus colchicus",
        16312: "Phasianus colchicus",
        17549: "Phasianus colchicus",
        4456: "Colinus virginianus",
        17183: "Colinus virginianus",
        4495: "Passer domesticus",
        11782: "Passer domesticus"
    }

    # Species map
    species_df = pd.read_csv(ECOTOX_DIR / "validation/species.txt", sep="|", low_memory=False)
    species_tax_map = species_df[species_df["species_number"].isin(ecotox_species_nums.keys())].set_index("species_number").apply(
        lambda r: f"{r['kingdom']};{r['phylum_division']};{r['subphylum_div']};{r['superclass']};{r['class']};{r['tax_order']};{r['family']};{r['genus']};{r['latin_name']}",
        axis=1
    ).to_dict()

    # Load tests
    tests_iter = pd.read_csv(
        ECOTOX_DIR / "tests.txt",
        sep="|",
        usecols=["test_id", "test_cas", "species_number", "exposure_type", "published_date"],
        chunksize=100000,
        low_memory=False
    )
    df_tests = pd.concat([chunk[chunk["species_number"].isin(ecotox_species_nums.keys())] for chunk in tests_iter])

    # Oral exposures only
    df_tests = df_tests[df_tests["exposure_type"].isin(["OR", "GV", "OR/"])]
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

    # Load results
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
        chunk = chunk[chunk["endpoint"].astype(str).str.strip().str.upper() == "LD50"]
        matched_results.append(chunk)

    df_results = pd.concat(matched_results)
    print(f"Loaded {len(df_results)} raw matched avian results from ECOTOX.")

    for idx, row in df_results.iterrows():
        test_id = row["test_id"]
        raw_cas = test_to_cas.get(test_id)
        if pd.isna(raw_cas):
            continue

        cas_str = clean_cas(raw_cas)
        if not cas_str:
            continue

        smi_raw_mapping = unified_mapping.get(cas_str)
        if not smi_raw_mapping:
            curation_log.append({
                "smiles_original": cas_str,
                "stage": "parse",
                "reason": "missing_smiles_mapping"
            })
            continue

        smi_raw = smi_raw_mapping.get("smiles")
        if not smi_raw:
            continue
        
        # Unit conversion
        val_str = str(row["conc1_mean"]).strip()
        try:
            val_raw = float(val_str)
        except ValueError:
            continue

        if val_raw <= 0:
            continue

        unit = str(row["conc1_unit"]).strip().lower()
        val_mg_kg = None

        # Convert to mg/kg bw
        if unit in ["mg/kg org", "mg/kg bdwt", "mg/kg", "ai mg/kg", "ai mg/kg bdwt"]:
            val_mg_kg = val_raw
        elif unit in ["g/kg"]:
            val_mg_kg = val_raw * 1000.0
        elif unit in ["ug/kg org", "ug/kg"]:
            val_mg_kg = val_raw / 1000.0

        if val_mg_kg is None:
            curation_log.append({
                "smiles_original": smi_raw,
                "stage": "activity_filter",
                "reason": f"unsupported_concentration_unit:{unit}"
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
            continue

        # log10 transformation on mg/kg bw
        value_log = math.log10(val_mg_kg)
        species_num = test_to_species.get(test_id)
        species_clean = ecotox_species_nums.get(species_num, "Avian unspecified")
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
            "value": val_mg_kg,
            "value_units": "mg/kg bw",
            "value_log": value_log,
            "value_class": None,
            "species": species_clean,
            "species_taxonomy": species_taxonomy,
            "test_type": "in_vivo",
            "exposure_route": "oral",
            "exposure_duration_h": 24.0,
            "effect": "mortality",
            "source": "EPA ECOTOX ASCII",
            "source_ref": "EPA ECOTOX",
            "source_record_id": str(row["result_id"]),
            "year_reported": year_reported,
            "quality_flags": flags
        })

    if not processed_records:
        raise ValueError("No Bird records successfully curated.")

    df_combined = pd.DataFrame(processed_records)

    # 3. Deduplicate and Consolidate: Group by InChIKey
    combined_records = []
    all_ikeys = df_combined["inchikey"].unique()

    for ikey in all_ikeys:
        group = df_combined[df_combined["inchikey"] == ikey]
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
            "value_units": "mg/kg bw",
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
        "raw_records": len(df_results) + (len(df_joined) if 'df_joined' in locals() else 0),
        "after_parse": len(processed_records),
        "after_standardisation": len(processed_records),
        "after_filter": len(processed_records),
        "after_aggregation": len(df_valid),
        "rejection_rate": ( (len(df_results) + (len(df_joined) if 'df_joined' in locals() else 0)) - len(processed_records) ) / (len(df_results) + (len(df_joined) if 'df_joined' in locals() else 1))
    }

    with open(curated_dir / "curation_stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    # Save structure cache locally for reproducibility
    with open(mapping_file, "w") as f:
        json.dump(unified_mapping, f, indent=2)

    print(f"Curation complete: {len(df_valid)} unique bird records saved.")

if __name__ == "__main__":
    run_curate()
