import os
import json
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
from rdkit import Chem
from rdkit.Chem import Descriptors

RAW_DIR = Path("/home/svakal/Projects/Edeon/data/raw/algae")
FISH_RAW_DIR = Path("/home/svakal/Projects/Edeon/data/raw/fish")
ECOTOX_DIR = FISH_RAW_DIR / "ecotox_ascii_03_12_2026"

def get_chemical_properties(cas: str) -> tuple:
    """Hybrid resolver: Tries NCI CACTUS first, falls back to PubChem."""
    cas_str = str(cas).strip()
    
    # 1. Try NCI CACTUS
    cactus_url = f"https://cactus.nci.nih.gov/chemical/structure/{cas_str}/smiles"
    try:
        req = urllib.request.Request(cactus_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            smiles = response.read().decode('utf-8').strip()
            if smiles and "invalid" not in smiles.lower():
                mol = Chem.MolFromSmiles(smiles)
                if mol:
                    mw = Descriptors.ExactMolWt(mol)
                    return cas_str, smiles, mw
    except Exception:
        pass

    # 2. Fall back to PubChem PUG REST
    pubchem_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{cas_str}/property/CanonicalSMILES,IsomericSMILES,ExactMass/JSON"
    try:
        req = urllib.request.Request(pubchem_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            res = json.loads(response.read().decode('utf-8'))
            props = res["PropertyTable"]["Properties"][0]
            smiles = props.get("IsomericSMILES") or props.get("CanonicalSMILES")
            mw = props.get("ExactMass")
            return cas_str, smiles, mw
    except Exception:
        pass

    return cas_str, None, None

def run_acquire(endpoint: str = None) -> None:
    """Verifies ECOTOX ASCII directory and unifies CAS-to-SMILES mappings for Algae."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    
    if not ECOTOX_DIR.exists():
        raise FileNotFoundError(
            f"Expected ECOTOX ASCII directory at {ECOTOX_DIR}. "
            "Please ensure the ASCII directory is placed in raw/fish."
        )

    # Species numbers for target algae:
    # 58471: Raphidocelis subcapitata
    # 58477: Selenastrum capricornutum
    # 479: Chlorella vulgaris
    # 17449: Desmodesmus subspicatus
    species_nums = {58471, 58477, 479, 17449}
    print("Scanning ECOTOX ASCII files for unique target Algae CAS numbers...")

    # Load species map
    species_df = pd.read_csv(ECOTOX_DIR / "validation/species.txt", sep="|", low_memory=False)
    species_map = species_df[species_df["species_number"].isin(species_nums)].set_index("species_number")["latin_name"].to_dict()

    # Load tests
    tests_iter = pd.read_csv(
        ECOTOX_DIR / "tests.txt",
        sep="|",
        usecols=["test_id", "test_cas", "species_number", "exposure_type"],
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

    # Load results
    results_iter = pd.read_csv(
        ECOTOX_DIR / "results.txt",
        sep="|",
        usecols=["result_id", "test_id", "obs_duration_mean", "obs_duration_unit", "endpoint", "effect"],
        chunksize=100000,
        low_memory=False
    )

    matched_test_ids = set()
    for chunk in results_iter:
        chunk = chunk[chunk["test_id"].isin(test_to_cas.keys())]
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
        matched_test_ids.update(chunk["test_id"].tolist())

    # Get unique CAS numbers
    target_cas_raw = {test_to_cas[tid] for tid in matched_test_ids if tid in test_to_cas}
    target_cas = []
    for c in target_cas_raw:
        if pd.isna(c):
            continue
        c_str = str(c).strip()
        if c_str.isdigit():
            if len(c_str) > 4:
                c_str = f"{c_str[:-3]}-{c_str[-3:-1]}-{c_str[-1]}"
        target_cas.append(c_str)
        
    target_cas = sorted(list(set(target_cas)))
    print(f"Found {len(target_cas)} unique target Algae CAS numbers.")

    # Re-use resolved structure mapping from fish and daphnia to prevent duplicate queries
    mapping_file = RAW_DIR / "cas_to_smiles.json"
    fish_mapping = FISH_RAW_DIR / "cas_to_smiles.json"
    daphnia_mapping = Path("/home/svakal/Projects/Edeon/data/raw/daphnia/cas_to_smiles.json")
    
    cache = {}
    if fish_mapping.exists():
        with open(fish_mapping, "r") as f:
            cache.update(json.load(f))
        print(f"Loaded existing cached structure mappings from fish dataset.")
    if daphnia_mapping.exists():
        with open(daphnia_mapping, "r") as f:
            cache.update(json.load(f))
        print(f"Loaded existing cached structure mappings from daphnia dataset.")
    if mapping_file.exists():
        with open(mapping_file, "r") as f:
            cache.update(json.load(f))
        print(f"Loaded cached CAS-to-SMILES mappings from local algae cache.")

    cas_to_query = [c for c in target_cas if c not in cache]

    if cas_to_query:
        print(f"Resolving {len(cas_to_query)} new CAS numbers concurrently via hybrid resolver...")
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(get_chemical_properties, cas): cas for cas in cas_to_query}
            for idx, future in enumerate(as_completed(futures)):
                cas, smiles, mw = future.result()
                if smiles:
                    cache[cas] = {"smiles": smiles, "mw": mw}
                else:
                    cache[cas] = {"smiles": None, "mw": None}
                if (idx + 1) % 100 == 0:
                    print(f"Resolved {idx + 1}/{len(cas_to_query)} CAS numbers...")

    with open(mapping_file, "w") as f:
        json.dump(cache, f, indent=2)
    print(f"CAS-to-SMILES mapping saved to {mapping_file}.")

    # Record access metadata
    meta_path = RAW_DIR / "access_metadata.txt"
    with open(meta_path, "w", encoding="utf-8") as f:
        f.write("Source: EPA ECOTOX ASCII Bulk Export\n")
        f.write("Release Date: 03/12/2026\n")
        f.write("Access Date: 2026-05-31\n")
        f.write("Chemical structure mappings: Hybrid NCI CACTUS + PubChem PUG REST API\n")

    print("Acquisition stage completed successfully.")

if __name__ == "__main__":
    run_acquire()
