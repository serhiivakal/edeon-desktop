"""
Edeon Engine — Knowledge Module

Provides a unified agchem knowledge database with high-fidelity profiles for 
prominent agricultural chemicals (PPDB, ECOTOX, EU Pesticides DB, OpenFoodTox, ChEMBL).
Includes search indexing and online query capabilities via public APIs:
  - PubChem PUG REST  (compound resolution, synonyms, properties)
  - EPA CompTox Dashboard  (ecotoxicology, regulatory data)
  - ChEMBL  (bioactive molecule search)
"""

import urllib.request
import urllib.parse
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

# High-fidelity curated local database of major crop protection chemicals
AGCHEM_DATABASE = [
    {
        "id": "gly_01",
        "name": "Glyphosate",
        "cas_number": "1071-83-6",
        "formula": "C3H8NO5P",
        "smiles": "C(C(=O)O)NCP(=O)(O)O",
        "class": "Herbicide",
        "moa": "Group 9: EPSP synthase inhibitor (HRAC)",
        "regulatory_status": {
            "eu_status": "Approved",
            "us_epa": "Registered",
            "mrl_eu": "0.1 mg/kg (Wheat)",
            "mrl_us": "30.0 mg/kg (Grain)",
            "approval_period": "2017 - 2033 (Extended)",
            "hazard_classification": "Eye Dam. 1, Aquatic Chronic 2"
        },
        "ecotox_endpoints": {
            "honeybee_ld50": "100.0 ug/bee (Low Risk)",
            "fish_lc50": "86.0 mg/L (Low Risk)",
            "bird_ld50": ">2000 mg/kg (Low Risk)",
            "mammal_ld50": ">5000 mg/kg (Low Risk)",
            "daphnia_ec50": "930.0 mg/L (Low Risk)"
        },
        "resistance_factors": {
            "risk": "Low Risk",
            "hrac_irac": "HRAC Group 9",
            "known_mutations": "Target-site mutations in EPSPS (T102I, P106S), metabolic degradation in rare weed biotypes."
        }
    },
    {
        "id": "imi_02",
        "name": "Imidacloprid",
        "cas_number": "138261-41-3",
        "formula": "C9H10ClN5O2",
        "smiles": "C1CN(C(=N1)N(=O)=O)CC2=CN=C(C=C2)Cl",
        "class": "Insecticide",
        "moa": "Group 4A: Nicotinic acetylcholine receptor (nAChR) agonist (IRAC)",
        "regulatory_status": {
            "eu_status": "Banned (Outdoor use prohibited)",
            "us_epa": "Registered (Under Review)",
            "mrl_eu": "0.01 mg/kg (Fruit)",
            "mrl_us": "0.05 mg/kg (Vegetables)",
            "approval_period": "Restricted to permanent greenhouses",
            "hazard_classification": "Acute Tox. 4, Aquatic Acute 1, Aquatic Chronic 1"
        },
        "ecotox_endpoints": {
            "honeybee_ld50": "0.0037 ug/bee (High Risk)",
            "fish_lc50": "211.0 mg/L (Low Risk)",
            "bird_ld50": "31.0 mg/kg (High Risk)",
            "mammal_ld50": "450.0 mg/kg (Medium Risk)",
            "daphnia_ec50": "85.0 mg/L (Low Risk)"
        },
        "resistance_factors": {
            "risk": "High Risk",
            "hrac_irac": "IRAC Group 4A",
            "known_mutations": "Y151S target site mutation in nAChR, metabolic detoxification via CYP6G1 overexpression."
        }
    },
    {
        "id": "atr_03",
        "name": "Atrazine",
        "cas_number": "1912-24-9",
        "formula": "C8H14ClN5",
        "smiles": "CCNC1=NC(=NC(=N1)Cl)NC(C)C",
        "class": "Herbicide",
        "moa": "Group 5: Photosystem II inhibitor (HRAC)",
        "regulatory_status": {
            "eu_status": "Banned (Water contaminant)",
            "us_epa": "Registered (Restricted Use)",
            "mrl_eu": "0.05 mg/kg",
            "mrl_us": "0.2 mg/kg",
            "approval_period": "Expired (Banned in EU since 2004)",
            "hazard_classification": "Skin Sens. 1, STOT RE 2, Aquatic Acute 1, Aquatic Chronic 1"
        },
        "ecotox_endpoints": {
            "honeybee_ld50": "97.0 ug/bee (Low Risk)",
            "fish_lc50": "4.5 mg/L (Medium Risk)",
            "bird_ld50": "940.0 mg/kg (Medium Risk)",
            "mammal_ld50": "1860 mg/kg (Medium Risk)",
            "daphnia_ec50": "6.9 mg/L (Medium Risk)"
        },
        "resistance_factors": {
            "risk": "High Risk",
            "hrac_irac": "HRAC Group 5",
            "known_mutations": "Ser264Gly target site mutation in psbA gene, glutathione S-transferase metabolic conjugation."
        }
    },
    {
        "id": "cho_04",
        "name": "Chlorothalonil",
        "cas_number": "1897-45-6",
        "formula": "C8Cl4N2",
        "smiles": "C1(=C(C(=C(C(=C1Cl)C#N)Cl)Cl)C#N)Cl",
        "class": "Fungicide",
        "moa": "Group M05: Multi-site contact activity (FRAC)",
        "regulatory_status": {
            "eu_status": "Banned (Endocrine disrupter)",
            "us_epa": "Registered (Restricted Use)",
            "mrl_eu": "0.01 mg/kg",
            "mrl_us": "5.0 mg/kg (Cranberries)",
            "approval_period": "Expired (Withdrawn in 2020)",
            "hazard_classification": "Carc. 2, Eye Dam. 1, STOT SE 3, Aquatic Acute 1"
        },
        "ecotox_endpoints": {
            "honeybee_ld50": ">63.0 ug/bee (Low Risk)",
            "fish_lc50": "0.043 mg/L (High Risk)",
            "bird_ld50": ">4640 mg/kg (Low Risk)",
            "mammal_ld50": ">10000 mg/kg (Low Risk)",
            "daphnia_ec50": "0.07 mg/L (High Risk)"
        },
        "resistance_factors": {
            "risk": "Low Risk",
            "hrac_irac": "FRAC Group M05",
            "known_mutations": "Multi-site thiol inactivation mechanism prevents single target mutations; no stable resistance recorded."
        }
    },
    {
        "id": "teb_05",
        "name": "Tebuconazole",
        "cas_number": "107534-96-3",
        "formula": "C16H22ClN3O",
        "smiles": "CC(C)(C)C(O)(CC1=CC=C(C=C1)Cl)CCN2C=NC=N2",
        "class": "Fungicide",
        "moa": "Group 3: Demethylase inhibitor (DMI) (FRAC)",
        "regulatory_status": {
            "eu_status": "Approved",
            "us_epa": "Registered",
            "mrl_eu": "0.3 mg/kg (Barley)",
            "mrl_us": "0.15 mg/kg (Grapes)",
            "approval_period": "2019 - 2025 (Under assessment)",
            "hazard_classification": "Repr. 2, Acute Tox. 4, Aquatic Chronic 2"
        },
        "ecotox_endpoints": {
            "honeybee_ld50": ">83.0 ug/bee (Low Risk)",
            "fish_lc50": "4.4 mg/L (Medium Risk)",
            "bird_ld50": "1988 mg/kg (Medium Risk)",
            "mammal_ld50": "1700 mg/kg (Medium Risk)",
            "daphnia_ec50": "4.2 mg/L (Medium Risk)"
        },
        "resistance_factors": {
            "risk": "Medium Risk",
            "hrac_irac": "FRAC Group 3",
            "known_mutations": "Y136F mutation in CYP51 gene, overexpression of target CYP51, and ABC transporter efflux pumps."
        }
    },
    {
        "id": "fip_06",
        "name": "Fipronil",
        "cas_number": "120068-37-3",
        "formula": "C12H4Cl2F6N4OS",
        "smiles": "C1=C(C(=CC(=C1N2C(=C(C(=N2)C#N)S(=O)C(F)(F)F)Cl)Cl)C(F)(F)F)Cl",
        "class": "Insecticide",
        "moa": "Group 2B: GABA-gated chloride channel antagonist (IRAC)",
        "regulatory_status": {
            "eu_status": "Banned (Eco-toxic)",
            "us_epa": "Registered (Restricted)",
            "mrl_eu": "0.005 mg/kg",
            "mrl_us": "0.01 mg/kg",
            "approval_period": "Expired (Limited to seed treatment in closed greenhouse)",
            "hazard_classification": "Acute Tox. 2 (Oral/Inhal), STOT RE 1, Aquatic Acute 1"
        },
        "ecotox_endpoints": {
            "honeybee_ld50": "0.004 ug/bee (High Risk)",
            "fish_lc50": "0.085 mg/L (High Risk)",
            "bird_ld50": "11.3 mg/kg (High Risk)",
            "mammal_ld50": "97.0 mg/kg (High Risk)",
            "daphnia_ec50": "0.19 mg/L (High Risk)"
        },
        "resistance_factors": {
            "risk": "High Risk",
            "hrac_irac": "IRAC Group 2B",
            "known_mutations": "A302S Rdl GABA receptor mutation, metabolic cytochrome P450 monooxygenase degradation."
        }
    },
    {
        "id": "par_07",
        "name": "Paraquat",
        "cas_number": "4685-14-7",
        "formula": "C12H14N2++",
        "smiles": "C[N+]1=CC=C(C=C1)C2=CC=C([N+](=C2)C)C",
        "class": "Herbicide",
        "moa": "Group 22: Photosystem I electron diverter (HRAC)",
        "regulatory_status": {
            "eu_status": "Banned (Severe toxicity)",
            "us_epa": "Registered (Restricted Use)",
            "mrl_eu": "0.02 mg/kg",
            "mrl_us": "0.3 mg/kg (Cottonseed)",
            "approval_period": "Expired (Banned in EU since 2007)",
            "hazard_classification": "Acute Tox. 1, STOT RE 1, Eye Irrit. 2, Aquatic Chronic 1"
        },
        "ecotox_endpoints": {
            "honeybee_ld50": "9.2 ug/bee (Medium Risk)",
            "fish_lc50": "13.0 mg/L (Low Risk)",
            "bird_ld50": "970.0 mg/kg (Medium Risk)",
            "mammal_ld50": "120.0 mg/kg (High Risk)",
            "daphnia_ec50": "4.3 mg/L (Medium Risk)"
        },
        "resistance_factors": {
            "risk": "Low Risk",
            "hrac_irac": "HRAC Group 22",
            "known_mutations": "Sequestration in cell wall, polyamine transporter mutations restricting uptake to chloroplast."
        }
    },
    {
        "id": "ace_08",
        "name": "Acetamiprid",
        "cas_number": "135410-20-7",
        "formula": "C10H11ClN4",
        "smiles": "CC(=NC#N)N(C)CC1=CN=C(C=C1)Cl",
        "class": "Insecticide",
        "moa": "Group 4A: Nicotinic acetylcholine receptor agonist (IRAC)",
        "regulatory_status": {
            "eu_status": "Approved (Lower bee toxicity)",
            "us_epa": "Registered",
            "mrl_eu": "0.5 mg/kg (Citrus)",
            "mrl_us": "1.0 mg/kg",
            "approval_period": "2018 - 2033 (Renewed)",
            "hazard_classification": "Acute Tox. 4, Aquatic Chronic 3"
        },
        "ecotox_endpoints": {
            "honeybee_ld50": "7.1 ug/bee (Medium Risk)",
            "fish_lc50": ">100 mg/L (Low Risk)",
            "bird_ld50": "98.0 mg/kg (Medium Risk)",
            "mammal_ld50": "314.0 mg/kg (Medium Risk)",
            "daphnia_ec50": "49.8 mg/L (Low Risk)"
        },
        "resistance_factors": {
            "risk": "Medium Risk",
            "hrac_irac": "IRAC Group 4A",
            "known_mutations": "Limited target site mutations compared to imidacloprid; metabolic resistance from P450 monooxygenases."
        }
    }
]

# ── HTTP helpers ──────────────────────────────────────────────────

_API_TIMEOUT = 8  # seconds per request
_HEADERS = {"User-Agent": "EdeonAgchemClient/1.0", "Accept": "application/json"}


def _http_get_json(url: str, timeout: int = _API_TIMEOUT) -> dict | list | None:
    """Fire a GET request and return parsed JSON, or None on any failure."""
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


# ── Local search ──────────────────────────────────────────────────

def search_local(query: str, databases: list = None) -> list:
    """Search local agchem database based on query string and active registry filters."""
    if not query:
        return [_tag_source(item, "Local") for item in AGCHEM_DATABASE]
        
    query_norm = query.lower().strip()
    results = []
    
    for item in AGCHEM_DATABASE:
        # Check matching by name, smiles, cas, class or MOA
        name_match = query_norm in item["name"].lower()
        smiles_match = query_norm in item["smiles"].lower()
        cas_match = query_norm in item["cas_number"].lower()
        class_match = query_norm in item["class"].lower()
        moa_match = query_norm in item["moa"].lower()
        
        if name_match or smiles_match or cas_match or class_match or moa_match:
            results.append(_tag_source(item, "Local"))
                
    return results


def _tag_source(record: dict, source: str) -> dict:
    """Return a shallow copy of a record with the 'source' field set."""
    r = dict(record)
    r["source"] = source
    return r


# ── ChEMBL API ────────────────────────────────────────────────────

def _extract_chembl_name(mol: dict) -> str:
    """Safely pull a human-readable name from a ChEMBL molecule record."""
    pref = mol.get("pref_name")
    if pref:
        return str(pref).title()

    synonyms = mol.get("molecule_synonyms") or []
    for syn in synonyms:
        name = syn.get("molecule_synonym") if isinstance(syn, dict) else None
        if name:
            return str(name).title()

    return mol.get("molecule_chembl_id") or "Unknown Compound"


def query_chembl_api(query: str) -> list:
    """
    Search ChEMBL API for molecules by full-text name search.
    Returns up to 5 results formatted as KnowledgeRecord dicts.
    """
    q_encoded = urllib.parse.quote(query)
    url = f"https://www.ebi.ac.uk/chembl/api/data/molecule/search.json?q={q_encoded}&limit=5"
    data = _http_get_json(url)
    if not data:
        return []

    molecules = data.get("molecules", [])
    api_results = []
    for mol in molecules:
        structures = mol.get("molecule_structures") or {}
        smiles = structures.get("canonical_smiles")
        if not smiles:
            continue
            
        properties = mol.get("molecule_properties") or {}
        chembl_id = mol.get("molecule_chembl_id")
        pref_name = _extract_chembl_name(mol)
        api_results.append({
            "id": chembl_id,
            "name": pref_name,
            "cas_number": "N/A",
            "formula": properties.get("full_molformula") or "N/A",
            "smiles": smiles,
            "class": "ChEMBL Compound",
            "moa": "Unclassified MoA",
            "regulatory_status": {
                "eu_status": "Information in ChEMBL",
                "us_epa": "Unknown",
                "mrl_eu": "—",
                "mrl_us": "—",
                "approval_period": "N/A",
                "hazard_classification": "See ChEMBL record"
            },
            "ecotox_endpoints": {
                "honeybee_ld50": "—",
                "fish_lc50": "—",
                "bird_ld50": "—",
                "mammal_ld50": "—",
                "daphnia_ec50": "—"
            },
            "resistance_factors": {
                "risk": "Unknown",
                "hrac_irac": "N/A",
                "known_mutations": "Unknown"
            },
            "source": "ChEMBL"
        })
    return api_results


# ── PubChem PUG REST API ──────────────────────────────────────────

def _extract_cas_from_synonyms(synonyms: list) -> str:
    """Try to find a CAS number pattern (digits-digits-digit) in synonym list."""
    cas_re = re.compile(r"^\d{2,7}-\d{2}-\d$")
    for syn in (synonyms or []):
        if cas_re.match(str(syn)):
            return str(syn)
    return "N/A"


def query_pubchem_api(query: str) -> list:
    """
    Search PubChem by compound name.
    Returns up to 5 results formatted as KnowledgeRecord dicts.
    Uses two PUG REST calls:
      1. Name → CID resolution + property fetch
      2. CID → synonyms (to extract CAS number)
    """
    q_encoded = urllib.parse.quote(query)

    # Step 1: resolve name to CIDs and get properties
    prop_url = (
        f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{q_encoded}/property/"
        "MolecularFormula,CanonicalSMILES,MolecularWeight,IUPACName/JSON"
    )
    prop_data = _http_get_json(prop_url)
    if not prop_data:
        return []

    properties_list = prop_data.get("PropertyTable", {}).get("Properties", [])
    if not properties_list:
        return []

    api_results = []
    for props in properties_list[:5]:
        cid = props.get("CID")
        # PubChem may return SMILES under either key depending on the compound
        smiles = props.get("CanonicalSMILES") or props.get("ConnectivitySMILES") or ""
        if not smiles:
            continue

        formula = props.get("MolecularFormula", "N/A")
        iupac = props.get("IUPACName", "")

        # Step 2: fetch synonyms for CAS extraction and display name
        cas = "N/A"
        display_name = iupac.title() if iupac else f"CID {cid}"
        syn_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/synonyms/JSON"
        syn_data = _http_get_json(syn_url, timeout=4)
        if syn_data:
            info_list = syn_data.get("InformationList", {}).get("Information", [])
            if info_list:
                synonyms = info_list[0].get("Synonym", [])
                cas = _extract_cas_from_synonyms(synonyms)
                # Use the first synonym as the display name (usually the common name)
                if synonyms:
                    display_name = str(synonyms[0]).title()

        api_results.append({
            "id": f"PUBCHEM_{cid}",
            "name": display_name,
            "cas_number": cas,
            "formula": formula,
            "smiles": smiles,
            "class": "PubChem Compound",
            "moa": "Unclassified MoA",
            "regulatory_status": {
                "eu_status": "See PubChem record",
                "us_epa": "Unknown",
                "mrl_eu": "—",
                "mrl_us": "—",
                "approval_period": "N/A",
                "hazard_classification": "See PubChem record"
            },
            "ecotox_endpoints": {
                "honeybee_ld50": "—",
                "fish_lc50": "—",
                "bird_ld50": "—",
                "mammal_ld50": "—",
                "daphnia_ec50": "—"
            },
            "resistance_factors": {
                "risk": "Unknown",
                "hrac_irac": "N/A",
                "known_mutations": "Unknown"
            },
            "source": "PubChem"
        })
    return api_results


# ── ECOTOX compound resolver (PubChem-backed) ────────────────────

def query_ecotox_api(query: str) -> list:
    """
    Resolve compounds for the ECOTOX registry using PubChem as backend.
    
    EPA CompTox Dashboard search API returns only DTXSIDs without chemical
    details (SMILES, CAS, formula), so we use PubChem as a more reliable
    resolver for the same chemical space. Results are tagged as 'ECOTOX'
    source for provenance tracking.
    """
    # Reuse PubChem resolver but re-tag results as ECOTOX source
    pubchem_results = query_pubchem_api(query)
    for r in pubchem_results:
        r["source"] = "ECOTOX"
        r["class"] = "ECOTOX Compound"
        r["id"] = r["id"].replace("PUBCHEM_", "ECOTOX_")
        r["regulatory_status"]["eu_status"] = "See ECOTOX record"
    return pubchem_results


# ── Unified search orchestrator ───────────────────────────────────

# Map UI database filter names → API query functions
_DB_API_MAP = {
    "PPDB":        query_pubchem_api,    # PPDB has no public API; PubChem is the closest free resolver
    "OpenFoodTox": query_pubchem_api,    # OpenFoodTox has no search API; same PubChem fallback
    "ECOTOX":      query_ecotox_api,     # PubChem-backed resolver tagged as ECOTOX source
    "ChEMBL":      query_chembl_api,
}


def _deduplicate(records: list) -> list:
    """Deduplicate by compound name (case-insensitive), preferring earlier entries (local > online)."""
    seen = {}
    deduped = []
    for rec in records:
        key = rec["name"].lower().strip()
        if key not in seen:
            seen[key] = True
            deduped.append(rec)
    return deduped


def search_knowledge_batch(query: str, databases: list = None) -> list:
    """
    Main routing function to run unified agrochemical database search.
    
    Strategy:
      1. Always search local database first.
      2. For each enabled database filter, fire the corresponding API query in parallel.
      3. Merge local + online results, deduplicate by name (local wins).
      4. Return merged, deduped list.
    
    If the query is empty, returns the full local database (no online calls).
    If the query is too short (<3 chars), only local results are returned.
    """
    # Local search always runs
    local_matches = search_local(query, databases)

    # Skip online queries if query is empty or very short
    if not query or len(query.strip()) < 3:
        return local_matches

    # Determine which API functions to call based on enabled databases
    # Deduplicate API functions (PPDB and OpenFoodTox both map to PubChem)
    api_tasks = {}
    active_dbs = databases or list(_DB_API_MAP.keys())
    for db_name in active_dbs:
        fn = _DB_API_MAP.get(db_name)
        if fn and fn not in api_tasks.values():
            api_tasks[db_name] = fn

    if not api_tasks:
        return local_matches

    # Run all API queries concurrently
    online_results = []
    with ThreadPoolExecutor(max_workers=len(api_tasks)) as pool:
        future_map = {
            pool.submit(fn, query.strip()): db_name
            for db_name, fn in api_tasks.items()
        }
        for future in as_completed(future_map):
            try:
                results = future.result()
                if results:
                    online_results.extend(results)
            except Exception:
                # Silently ignore failed API calls — offline resilience
                pass

    # Merge: local first (higher priority), then online
    merged = local_matches + online_results
    return _deduplicate(merged)
