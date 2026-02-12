# Edeon Phase 1 — Data Curation Pipeline Implementation Specification

**Audience:** coding agent.
**Goal:** build a reproducible data curation pipeline that produces versioned, splittable, documented datasets for 11 endpoints. The output of Phase 1 is the input to Phase 2 (Tier-1 model training) and the dataset section of Paper 3 (Open Benchmarks for Pesticide Ecotoxicity Prediction).

**This phase trains zero models.** It produces datasets only. If the agent finds itself writing model training code, it has gone out of scope — stop and consult `docs/PHASE1_NOTES.md`.

---

## 0. Context

Phase 0 built the architecture: `ModelBackend` interface, `BackendRegistry`, deployment bridge from QSAR Studio, model cards, UQ/AD wrappers. The existing LogP predictors are now Tier-2 backends.

Phase 1 builds the *data foundation* for Phase 2's Tier-1 reference models. For each of 11 endpoints, the pipeline must:

1. Acquire raw data from canonical public sources.
2. Apply a standard chemistry curation pipeline (SMILES canonicalisation, salt/solvent stripping, fragment selection, neutralisation, duplicate aggregation).
3. Normalise units and activity values to a canonical schema.
4. Generate three frozen splits: scaffold-based, random, and time-based (where temporal metadata exists).
5. Document everything in a structured Data Card.
6. Emit reproducible artefacts that downstream Phase 2 training can consume directly.

The same artefacts feed Paper 3's dataset section, so curation quality is a publication-level concern, not just an engineering one.

---

## 1. Tech Stack Assumptions

- **Python**: 3.11+
- **Core chemistry**: RDKit (rdkit-pypi 2024.03.5 or later), ChEMBL Structure Pipeline (`chembl_structure_pipeline`) for canonical curation, MolVS for fallback
- **Data**: pandas, polars (preferred for large ECOTOX subsets), pyarrow (Parquet IO)
- **Validation / schema**: pydantic v2, yaml
- **CLI**: typer (or click — match existing project convention)
- **Hashing & provenance**: hashlib (SHA-256), `python-dateutil`
- **Optional ML utilities** (for scaffold splits and feature precompute only — no model training): scikit-learn ≥1.4, scaffold splitting via RDKit's `Chem.Scaffolds.MurckoScaffold`
- **DVC** (optional but recommended): for dataset versioning if the project already uses it; otherwise rely on the manifest + SHA-256 hashing scheme defined below

No deep-learning frameworks are needed for Phase 1.

---

## 2. Architectural Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                  edeon-data CLI                                  │
│  edeon-data <endpoint> acquire | curate | split | card | all    │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
   │   Shared     │   │  Per-endpoint│   │   Output     │
   │ utilities    │   │   modules    │   │   bundles    │
   │              │   │              │   │              │
   │ standardize  │   │ bee/         │   │ data/curated/│
   │ split        │   │ rat_ld50/    │   │   <endpoint>/│
   │ schema       │   │ fish/        │   │     v1.0/    │
   │ data_card    │   │ daphnia/     │   │              │
   │ io           │   │ algae/       │   │              │
   │              │   │ earthworm/   │   │              │
   │              │   │ bird/        │   │              │
   │              │   │ koc/         │   │              │
   │              │   │ dt50/        │   │              │
   │              │   │ bcf/         │   │              │
   │              │   │ skin_sens/   │   │              │
   └──────────────┘   └──────────────┘   └──────────────┘
```

Each endpoint module exposes four stage functions: `acquire()`, `curate()`, `split()`, `card()`. They share a single canonical record schema (Section 4). Stages are idempotent: re-running with the same inputs produces byte-identical outputs (modulo timestamps in the card).

---

## 3. Repository Layout

Create the following structure. Preserve existing project layout.

```
edeon/
├── python/
│   └── edeon_data/                       # NEW — top-level package
│       ├── __init__.py
│       ├── cli.py                        # typer entry point
│       ├── schema.py                     # CuratedRecord, DataCard pydantic models
│       ├── endpoints.py                  # Re-export Endpoint enum from edeon_models
│       ├── shared/
│       │   ├── __init__.py
│       │   ├── standardize.py            # RDKit + ChEMBL Structure Pipeline curation
│       │   ├── splits.py                 # Scaffold, random, time splits
│       │   ├── activity.py               # Unit conversions, log transforms, aggregation
│       │   ├── io.py                     # Parquet/CSV/YAML IO with SHA-256
│       │   ├── filters.py                # Common compound filters (atoms, MW range, etc.)
│       │   └── manifest.py               # Dataset manifest construction
│       ├── endpoints/
│       │   ├── __init__.py
│       │   ├── bee/
│       │   │   ├── __init__.py
│       │   │   ├── acquire.py
│       │   │   ├── curate.py
│       │   │   ├── split.py
│       │   │   └── card.py
│       │   ├── rat_ld50/
│       │   ├── fish/
│       │   ├── daphnia/
│       │   ├── algae/
│       │   ├── earthworm/
│       │   ├── bird/
│       │   ├── koc/
│       │   ├── dt50/
│       │   ├── bcf/
│       │   └── skin_sens/
│       └── tests/
│           ├── test_schema.py
│           ├── test_standardize.py
│           ├── test_splits.py
│           └── test_endpoint_smoke.py
├── data/                                 # NEW — output trees
│   ├── raw/                              # Raw acquired files (large, gitignored)
│   │   └── <endpoint>/<source>/
│   └── curated/                          # Versioned curated outputs (committed)
│       └── <endpoint>/v1.0/
│           ├── curated.parquet
│           ├── curated.csv               # Human-readable mirror
│           ├── splits/
│           │   ├── scaffold/
│           │   │   ├── train.parquet
│           │   │   ├── cal.parquet
│           │   │   └── test.parquet
│           │   ├── random/
│           │   │   ├── train.parquet
│           │   │   ├── cal.parquet
│           │   │   └── test.parquet
│           │   └── time/                 # Only if year metadata exists
│           │       ├── train.parquet
│           │       ├── cal.parquet
│           │       └── test.parquet
│           ├── data_card.yaml
│           ├── curation_log.json
│           └── manifest.json             # SHA-256s + sizes
├── docs/
│   ├── PHASE1_NOTES.md                   # NEW — agent deviation log
│   ├── DATA_CARD_SCHEMA.md               # NEW
│   ├── CURATION_RULES.md                 # NEW — explicit inclusion/exclusion criteria
│   └── DATASET_SOURCES.md                # NEW — provenance for each source
└── .github/
    └── workflows/
        └── data_smoke.yml                # NEW — smoke tests data pipelines
```

`data/raw/` should be gitignored (datasets are large). `data/curated/<endpoint>/v1.0/` should be committed (sizes are manageable; ECOTOX subsets compress well to Parquet).

---

## 4. Canonical Data Schema

All curated outputs conform to a single schema. Each row = one compound–endpoint observation after aggregation.

### 4.1 `CuratedRecord` (pydantic model)

```python
# python/edeon_data/schema.py
from __future__ import annotations
from typing import Optional, Literal
from pydantic import BaseModel, Field, ConfigDict


class CuratedRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    # Identity
    inchikey: str = Field(..., description="Canonical InChIKey (14-block) of curated structure")
    smiles_canonical: str = Field(..., description="Canonical SMILES after standardisation")
    smiles_original: Optional[str] = Field(None, description="Original SMILES from source")
    cas: Optional[str] = None
    name: Optional[str] = None
    chembl_id: Optional[str] = None  # If aligned to ChEMBL

    # Endpoint
    endpoint: str = Field(..., description="Canonical Endpoint enum value")
    value: float = Field(..., description="Numeric value (regression) or class index (classification)")
    value_units: str = Field(..., description="Original units before transformation")
    value_log: Optional[float] = Field(
        None,
        description="log10-transformed value where applicable (e.g. pLC50 = -log10(LC50_molar))"
    )
    value_class: Optional[str] = Field(
        None,
        description="Categorical class label for classification endpoints"
    )

    # Test context (ecotox / tox endpoints)
    species: Optional[str] = None
    species_taxonomy: Optional[str] = None  # e.g. "Animalia;Arthropoda;Insecta;Hymenoptera"
    test_type: Optional[str] = None  # OECD guideline if known
    exposure_route: Optional[str] = None  # "oral", "contact", "inhalation"
    exposure_duration_h: Optional[float] = None
    effect: Optional[str] = None  # "mortality", "growth_inhibition"

    # Provenance
    source: str = Field(..., description="Source dataset identifier, e.g. 'ApisTox-v1.0'")
    source_ref: Optional[str] = Field(None, description="DOI or URL for source")
    source_record_id: Optional[str] = None  # ID in source database
    year_reported: Optional[int] = Field(None, description="Year of original measurement; used for time-split")

    # Aggregation
    aggregation_n: int = Field(1, description="Number of raw records aggregated into this row")
    aggregation_method: Optional[Literal["mean", "median", "geomean", "majority_vote", "single"]] = "single"
    aggregation_cv: Optional[float] = Field(None, description="Coefficient of variation across aggregated records")

    # Quality
    quality_flags: list[str] = Field(default_factory=list, description="Curation warnings for this record")
```

### 4.2 Parquet schema

When writing to Parquet, use these column types explicitly:
- `inchikey`, `smiles_canonical`, `endpoint`, `source`, `value_units`: string
- `value`, `value_log`, `aggregation_cv`, `exposure_duration_h`: float64
- `aggregation_n`, `year_reported`: int32 (nullable)
- `quality_flags`: list<string>
- All other Optional[str]: string (nullable)

This schema is fixed across endpoints. Endpoint-specific extra columns are stored under `source_record_id` or in the data card, not added to the schema.

---

## 5. Endpoint Source Manifest

Authoritative source list. The agent must use these sources. URLs may need verification at runtime — document any discrepancies in `docs/PHASE1_NOTES.md`.

| Endpoint | Primary source | Access | Approx size | License |
|---|---|---|---|---|
| **bee_acute_oral_ld50** + **bee_acute_contact_ld50** | ApisTox (Adamczyk et al., Sci. Data 2025) | Zenodo DOI 10.5281/zenodo.11062076 | ~1,035 compounds | CC BY 4.0 |
| **rat_acute_oral_ld50** | EPA CATMoS via NICEATM ICE | https://ice.ntp.niehs.nih.gov/ — Acute Oral Toxicity dataset | ~8,994 chemicals | Public domain (US gov) |
| **fish_acute_lc50** | ECOTOX (EPA) + EPA Williams ensemble training data | https://cfpub.epa.gov/ecotox/ ASCII bulk download | ~7,000+ after filtering | Public domain (US gov) |
| **daphnia_acute_ec50** | ECOTOX (EPA) | Same as above, filtered to *Daphnia magna* 48h | ~3,000+ | Public domain |
| **algae_growth_ec50** | ECOTOX (EPA) | Same, filtered to OECD 201 species | ~1,500+ | Public domain |
| **earthworm_acute_lc50** | Kotli et al. 2024 (*J. Hazard. Mater.* 461:132577) + Pore et al. 2024 supplementary | Article supplementary materials | ~1,000 | Author-released; cite |
| **bird_acute_oral_ld50** | ECOTOX + EFSA OpenFoodTox + literature compilations | ECOTOX bulk + EFSA Zenodo | ~600 | Public domain / CC BY |
| **soil_koc** | OPERA training set (Mansouri et al.) + OECD 121 compilation | https://github.com/NIEHS/OPERA | ~800 | Public domain |
| **soil_dt50** | EAWAG-SOIL via enviPath | https://envipath.org/ — Soil package | ~870 compounds, ~6,300 records | CC BY (verify on enviPath) |
| **bcf** | OPERA BCF training set + Lunghini et al. 2020 compilation | OPERA GitHub | ~1,000 | Public domain |
| **skin_sensitization** | NICEATM LLNA dataset + ICCVAM CCS data | NICEATM/NIEHS public release | ~1,500 | Public domain |

**Manual step required**: enviPath (EAWAG-SOIL) may require account registration for full bulk export. The agent should document this; a human will provide an export file if API access is blocked. Place such files at `data/raw/<endpoint>/<source>/` before running curate.

**For each endpoint**, fill `docs/DATASET_SOURCES.md` with: full citation, access URL, access date, license, file format, raw record count, retrieval method (API/download/manual).

---

## 6. Standardisation Standards

All endpoints use the same chemistry curation pipeline. Implement in `python/edeon_data/shared/standardize.py`.

### 6.1 Curation pipeline (in order)

1. **SMILES parsing**: parse via `Chem.MolFromSmiles(smi, sanitize=True)`. Reject parse failures.
2. **ChEMBL Structure Pipeline normalisation**: apply `chembl_structure_pipeline.standardize_mol()` then `get_parent_mol()`. This handles:
   - Aromaticity perception (Kekulé / aromatic harmonisation)
   - Functional group normalisation (nitro, sulfonate, etc.)
   - Salt/solvent stripping (keeps largest organic fragment)
   - Neutralisation of common charged forms
3. **Atom filter**: reject compounds containing atoms outside {H, B, C, N, O, F, Si, P, S, Cl, Se, Br, I}. Optionally allow metals if the endpoint historically includes them (e.g., copper-based fungicides) — document in the data card.
4. **Size filter**: reject MW < 50 Da or MW > 1500 Da (this excludes counterions and oligomers; tune per endpoint if needed and document).
5. **Tautomer canonicalisation**: apply RDKit's `MolStandardize.rdMolStandardize.TautomerEnumerator().Canonicalize(mol)` to select a canonical tautomer. Document this choice in the data card.
6. **InChIKey generation**: compute via `Chem.MolToInchiKey(mol)`. Use the full InChIKey as the canonical identifier.
7. **Canonical SMILES**: `Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)`.

### 6.2 Failure handling

Each rejected compound is recorded in `curation_log.json` with:
- Original SMILES (if present)
- Stage at which it was rejected
- Reason (parse error, disallowed atom, MW out of range, etc.)

Total rejections must be < 20% of input — otherwise the agent stops and documents the issue (likely source data quality problem).

### 6.3 Activity-side curation

**Numeric (regression) endpoints**:
- Convert all values to a single canonical unit (defined per endpoint in `docs/CURATION_RULES.md`).
- Apply log10 transformation where the distribution is right-skewed: `value_log = log10(value_canonical_molar)` for concentrations, `value_log = log10(value_mg_per_kg)` for doses if molar conversion isn't applicable.
- Reject records with non-positive values (cannot log-transform).
- Flag (but keep) records with `>` or `<` qualifiers (right- and left-censored). Mark with `quality_flags=["censored_upper"]` or `["censored_lower"]`. Phase 2 may choose to exclude these.

**Categorical (classification) endpoints**:
- Map source labels to canonical class names (defined per endpoint).
- Document the mapping table in the data card.

### 6.4 Duplicate aggregation

After standardisation, group by `inchikey`:

- **Regression**: aggregate by geometric mean of values (arithmetic mean of `value_log`). Compute CV across raw records. Flag with `quality_flags=["high_cv"]` if CV > 0.5 (i.e., raw values span > 1 log unit).
- **Classification**: majority vote. If tied, flag with `quality_flags=["class_conflict"]` and use the more conservative class (higher toxicity / concern).
- Always record `aggregation_n` and `aggregation_method`.

If a compound has > 10 raw records and CV > 1.0, flag with `quality_flags=["extreme_variance"]` for human review.

---

## 7. Splitting Standards

All endpoints produce three split types where applicable. Implement in `python/edeon_data/shared/splits.py`.

### 7.1 Scaffold split (Bemis–Murcko)

```python
from rdkit.Chem.Scaffolds import MurckoScaffold

def bemis_murcko_scaffold(smiles: str) -> str:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return ""
    scaffold = MurckoScaffold.GetScaffoldForMol(mol)
    return Chem.MolToSmiles(scaffold, canonical=True)
```

Group compounds by scaffold. Order scaffolds by descending group size (largest scaffolds in train, singletons in test — the standard "out-of-distribution" scaffold split). Assign groups to splits to reach target ratios.

**Default ratios**: train 70% / cal 15% / test 15%.

The `cal` (calibration) split is **mandatory** — Phase 2 uses it for conformal prediction calibration, distinct from `test`.

### 7.2 Random split

Standard random shuffle with `random_state=42` (hard-coded; document it). Stratified by `value_class` for classification endpoints; stratified by binned `value_log` (10 quantile bins) for regression endpoints.

Same 70/15/15 ratios.

### 7.3 Time-based split

If `year_reported` is populated for ≥ 50% of records:

- Sort by year ascending.
- Assign first 70% (by year cumulative) to train, next 15% to cal, last 15% to test.
- If a year boundary falls inside a partition, assign all records from that year to the *earlier* partition.

If `year_reported` is sparse, skip time split and note this in the data card under `splits.time.status: "not_available"`.

### 7.4 Split quality checks

After splitting:

- Verify no `inchikey` appears in more than one split (no leakage). Hard fail if violated.
- Compute and record in the data card:
  - Per-split N
  - Per-split mean and std of `value_log` (regression)
  - Per-split class distribution (classification)
  - Scaffold split: mean Tanimoto similarity of each test compound to its nearest training compound (the "scaffold split tightness" metric)

---

## 8. Data Card Schema

Each endpoint outputs `data_card.yaml`. Implement schema in `python/edeon_data/schema.py`.

```yaml
# data/curated/bee/v1.0/data_card.yaml
dataset_id: edeon-bee-v1.0
endpoint: bee_acute_oral_ld50
version: 1.0.0
created: 2026-06-01T10:00:00Z
created_by: edeon-data-pipeline
sources:
  - name: ApisTox
    citation: "Adamczyk J, Poziemski J, Siedlecki P (2025). Sci Data 12:5."
    doi: 10.1038/s41597-024-04232-w
    url: https://zenodo.org/records/11062076
    license: CC BY 4.0
    access_date: 2026-05-20
    raw_records: 1035
inclusion_criteria:
  - "Acute oral honeybee toxicity records (LD50, µg/bee)"
  - "Apis mellifera only"
  - "Time-split as provided by ApisTox v1.0"
exclusion_criteria:
  - "Mixtures, formulations (active ingredient only retained)"
  - "Records with non-positive numeric values"
  - "Compounds containing atoms outside {H, B, C, N, O, F, Si, P, S, Cl, Se, Br, I, metals_allowlist}"
standardisation:
  tool: chembl_structure_pipeline
  version: 1.2.0
  tautomer: rdkit-canonical
  atom_allowlist: [H, B, C, N, O, F, Si, P, S, Cl, Se, Br, I]
  mw_range: [50, 1500]
activity:
  units_canonical: ug/bee
  log_transform: log10
  aggregation: geometric_mean
  censored_handling: flagged_kept
curation_summary:
  raw_records: 1035
  after_parse: 1029
  after_standardisation: 1018
  after_filter: 1002
  after_aggregation: 998
  rejection_rate: 0.036
splits:
  scaffold:
    train: 698
    cal: 150
    test: 150
    test_to_train_nn_tanimoto_mean: 0.42
  random:
    train: 698
    cal: 150
    test: 150
    seed: 42
  time:
    train: 698
    cal: 150
    test: 150
    train_year_max: 2019
    cal_year_range: [2020, 2021]
    test_year_range: [2022, 2024]
known_biases:
  - "ApisTox over-represents organophosphates and neonicotinoids relative to broader chemical space"
  - "Recent diamide insecticides (post-2015) under-represented"
intended_use: "Training and benchmarking honeybee acute oral LD50 prediction models"
not_intended_for:
  - "Direct regulatory dossier submission"
  - "Quantitative human risk assessment"
sha256:
  curated_parquet: <hash>
  scaffold_train: <hash>
  scaffold_cal: <hash>
  scaffold_test: <hash>
  random_train: <hash>
  random_cal: <hash>
  random_test: <hash>
  time_train: <hash>
  time_cal: <hash>
  time_test: <hash>
```

The `sha256` fields are computed at write time over the canonical Parquet bytes.

---

## 9. Task Manifest

Tasks are grouped. Within a group, execute in numeric order. Across groups, respect explicit dependencies.

---

### Group A — Shared Infrastructure

These must complete before any per-endpoint module.

#### Task A1: Project scaffolding
**Depends on:** none.
**Files:** Create the directory tree from Section 3, including `__init__.py` files. Add `pyproject.toml` entry for `edeon_data` if separate package; otherwise add to existing project setup.

**Acceptance:** `python -c "import edeon_data"` succeeds.

---

#### Task A2: Canonical schema
**Depends on:** A1.
**File:** `python/edeon_data/schema.py`
**Action:** Implement `CuratedRecord` (Section 4.1) and `DataCard` pydantic models. `DataCard` mirrors Section 8 YAML structure.

**Acceptance:** Round-trip serialization preserves all fields. Tests in `tests/test_schema.py`.

---

#### Task A3: Endpoint enum re-export
**Depends on:** A1.
**File:** `python/edeon_data/endpoints.py`
**Action:** Re-export `Endpoint` from `edeon_models.endpoints` (defined in Phase 0). If `edeon_models` is not importable (Phase 0 not merged), define a local fallback enum matching the same string values.

**Acceptance:** `from edeon_data.endpoints import Endpoint` works.

---

#### Task A4: Standardisation module
**Depends on:** A2.
**File:** `python/edeon_data/shared/standardize.py`
**Action:** Implement the full curation pipeline from Section 6.1:

```python
from rdkit import Chem
from rdkit.Chem.MolStandardize import rdMolStandardize
from chembl_structure_pipeline import standardizer, checker

ATOM_ALLOWLIST_DEFAULT = {"H", "B", "C", "N", "O", "F", "Si", "P", "S", "Cl", "Se", "Br", "I"}
METAL_ALLOWLIST_AGRO = {"Cu", "Zn", "Mn", "Sn", "Hg"}  # used by some legacy pesticides


def standardize_smiles(
    smiles: str,
    atom_allowlist: set[str] = None,
    mw_min: float = 50.0,
    mw_max: float = 1500.0,
    canonicalize_tautomer: bool = True,
) -> tuple[Optional[str], Optional[str], list[str]]:
    """
    Returns (canonical_smiles, inchikey, flags) where flags is a list of
    quality flags. If the structure is rejected, returns (None, None, [reason]).
    """
    flags = []
    mol = Chem.MolFromSmiles(smiles, sanitize=True)
    if mol is None:
        return None, None, ["parse_failed"]
    # ChEMBL pipeline
    try:
        mol_std = standardizer.standardize_mol(mol)
        mol_parent = standardizer.get_parent_mol(mol_std)[0]
    except Exception as e:
        return None, None, [f"chembl_pipeline_failed:{e.__class__.__name__}"]
    # Atom allowlist
    atoms = {a.GetSymbol() for a in mol_parent.GetAtoms()}
    allowed = atom_allowlist if atom_allowlist is not None else ATOM_ALLOWLIST_DEFAULT
    disallowed = atoms - allowed
    if disallowed:
        return None, None, [f"disallowed_atoms:{','.join(sorted(disallowed))}"]
    # MW range
    mw = Chem.Descriptors.ExactMolWt(mol_parent)
    if mw < mw_min or mw > mw_max:
        return None, None, [f"mw_out_of_range:{mw:.1f}"]
    # Tautomer
    if canonicalize_tautomer:
        try:
            enum = rdMolStandardize.TautomerEnumerator()
            mol_parent = enum.Canonicalize(mol_parent)
        except Exception:
            flags.append("tautomer_canonicalization_failed")
    smi = Chem.MolToSmiles(mol_parent, canonical=True, isomericSmiles=True)
    ikey = Chem.MolToInchiKey(mol_parent)
    return smi, ikey, flags
```

Add a `standardize_dataframe(df, smiles_col)` helper that processes a DataFrame and returns `(curated_df, rejections_df)`.

**Acceptance:** Test against 20-compound mixed set including salts, mixtures, charged forms, and one invalid SMILES. Verify exact expected outputs in `tests/test_standardize.py`.

---

#### Task A5: Activity normalisation
**Depends on:** A2.
**File:** `python/edeon_data/shared/activity.py`
**Action:** Implement:

```python
def to_canonical_units(value: float, source_units: str, target_units: str, mw: Optional[float] = None) -> float:
    """Convert between common ecotox units. Supports:
       mg/L ↔ µg/L ↔ ppm ↔ molar (requires MW)
       mg/kg ↔ µg/kg ↔ g/kg
       ug/bee ↔ ng/bee ↔ mg/bee
    """

def log_transform(value: float, mw: Optional[float] = None, target: str = "log10_molar") -> float:
    """Apply log10 transformation. For pXX endpoints, requires conversion to molar first."""

def aggregate_records(group: pd.DataFrame, mode: Literal["regression", "classification"]) -> dict:
    """Aggregate a group of records for the same compound.
       Returns dict with value, value_log, aggregation_n, aggregation_method, aggregation_cv, flags.
    """
```

**Acceptance:** Unit conversions verified against known test cases (e.g., 10 mg/L acetone = 1.72e-4 M). Aggregation with replicate records produces correct mean and CV.

---

#### Task A6: Splitting module
**Depends on:** A2.
**File:** `python/edeon_data/shared/splits.py`
**Action:** Implement scaffold, random, and time splits per Section 7. Each returns three DataFrames (train, cal, test) and a metadata dict for the data card. Apply split quality checks (Section 7.4).

```python
def scaffold_split(df: pd.DataFrame, smiles_col: str = "smiles_canonical",
                   ratios: tuple = (0.7, 0.15, 0.15), seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    ...

def random_split(df: pd.DataFrame, value_col: str, classification: bool = False,
                 ratios: tuple = (0.7, 0.15, 0.15), seed: int = 42) -> tuple[..., dict]:
    ...

def time_split(df: pd.DataFrame, year_col: str = "year_reported",
               ratios: tuple = (0.7, 0.15, 0.15)) -> tuple[..., dict] | None:
    """Returns None if year metadata is too sparse."""
    ...
```

**Acceptance:** No `inchikey` leakage across splits in tests. Scaffold split tightness metric computed correctly.

---

#### Task A7: IO and provenance
**Depends on:** A2.
**File:** `python/edeon_data/shared/io.py`
**Action:** Implement:

```python
def write_parquet_with_hash(df: pd.DataFrame, path: Path) -> str:
    """Write Parquet and return SHA-256 of the on-disk bytes."""

def write_csv_mirror(df: pd.DataFrame, path: Path) -> None:
    """Write CSV mirror with stable column ordering."""

def write_data_card(card: DataCard, path: Path) -> None:
    """Write YAML data card with stable key ordering."""

def write_curation_log(entries: list[dict], path: Path) -> None:
    """Write structured JSON log of all curation events."""

def write_manifest(bundle_dir: Path) -> None:
    """Walk a curated/<endpoint>/v1.0/ directory and write manifest.json with all file sizes and SHA-256s."""
```

**Acceptance:** Writing then re-reading produces identical content (modulo file timestamps).

---

#### Task A8: CLI scaffolding
**Depends on:** A1.
**File:** `python/edeon_data/cli.py`
**Action:** Implement typer CLI:

```
edeon-data <endpoint> acquire        # Fetches raw data
edeon-data <endpoint> curate         # Applies standardisation
edeon-data <endpoint> split          # Generates frozen splits
edeon-data <endpoint> card           # Generates data card
edeon-data <endpoint> all            # Runs the full pipeline
edeon-data --list                    # Lists available endpoints
edeon-data --version <endpoint>      # Shows current version
```

Each stage writes its outputs to `data/raw/<endpoint>/` or `data/curated/<endpoint>/v1.0/`.

**Acceptance:** `edeon-data --list` shows all 11 endpoints. `edeon-data --help` produces usage.

---

#### Task A9: Document curation rules
**Depends on:** A4, A5.
**File:** `docs/CURATION_RULES.md`
**Action:** Document the rules from Sections 6.1–6.4 plus per-endpoint specifics (canonical units, log-transform choice, special inclusion/exclusion). Per-endpoint sections will be filled by the endpoint tasks (B-series).

**Acceptance:** Document exists with shared rules; endpoint-specific sections marked as stubs to be filled.

---

### Group B — Per-Endpoint Pipelines

Each endpoint follows the same task pattern. The template is given once below, then summarised for each endpoint with specifics.

**Per-endpoint task template** (apply to each B-series task):

For endpoint `<EP>`:
- **Bn.1**: implement `endpoints/<EP>/acquire.py` — fetches raw data from source(s), writes to `data/raw/<EP>/<source>/`, records access metadata.
- **Bn.2**: implement `endpoints/<EP>/curate.py` — applies endpoint-specific filters + the shared standardisation + activity normalisation; outputs `data/curated/<EP>/v1.0/curated.parquet`.
- **Bn.3**: implement `endpoints/<EP>/split.py` — applies all three split strategies; outputs splits.
- **Bn.4**: implement `endpoints/<EP>/card.py` — emits `data_card.yaml`.
- **Bn.5**: run `edeon-data <EP> all` end-to-end. Produce a `curation_log.json` and `manifest.json`. Write a summary report to `docs/PHASE1_NOTES.md` with rejection statistics.

#### Task B1: Bee (oral and contact)
**Depends on:** Group A.
**Source:** ApisTox via Zenodo (DOI 10.5281/zenodo.11062076).
**Specifics:**
- ApisTox provides separate datasets for oral and contact. Produce **two** curated bundles: `data/curated/bee_acute_oral_ld50/v1.0/` and `data/curated/bee_acute_contact_ld50/v1.0/`.
- Canonical units: `µg/bee`.
- log10-transform: `value_log = log10(value_ug_per_bee)`.
- Use ApisTox's provided time-split as the canonical time split (do not regenerate).
- Use the binary toxicity labels for an auxiliary classification version: produce `value_class ∈ {"toxic", "nontoxic"}`.
- Atom allowlist may include Cu (some old apiary chemicals).

**Acceptance:** Two bundles produced. ApisTox's published metrics (split sizes, class balance) reproduced.

---

#### Task B2: Rat acute oral LD50
**Depends on:** Group A.
**Source:** EPA CATMoS via NICEATM ICE (https://ice.ntp.niehs.nih.gov/). Download the Acute Oral Toxicity training dataset.
**Specifics:**
- Canonical units: `mg/kg bw`.
- log10-transform: `value_log = log10(LD50_mmol_per_kg)` where MW conversion is possible. Fall back to `log10(LD50_mg_per_kg)` for compounds lacking molecular weight.
- Also produce categorical labels matching GHS acute oral categories (Cat 1–5). Encode as `value_class`.
- CATMoS records may include in vitro / read-across estimates — restrict to in vivo LD50 only.

**Acceptance:** Bundle produced. Class distribution within 5% of published CATMoS distribution.

---

#### Task B3: Fish acute LC50
**Depends on:** Group A.
**Sources:**
- ECOTOX bulk download (https://cfpub.epa.gov/ecotox/) — Aquatic Toxicity ASCII export.
- EPA Williams et al. ensemble fish toxicity training data (compiled CSV, locate via EPA CompTox Dashboard or Williams 2017 supplementary).

**Specifics:**
- Filter ECOTOX records to:
  - Endpoint = `LC50`
  - Effect = `MOR` (mortality)
  - Test duration = 96h (with 5% tolerance)
  - Species ∈ {*Oncorhynchus mykiss*, *Pimephales promelas*, *Lepomis macrochirus*, *Cyprinus carpio*, *Danio rerio*, *Salmo salar*}
  - Result reported in mg/L (after unit conversion)
  - Exposure = aquatic
- Canonical units: `mg/L`.
- log10-transform: `value_log = log10(LC50_mol_per_L)` (pLC50 with MW).
- Add `species` column.
- Cross-merge with Williams ensemble dataset (deduplicate by InChIKey after standardisation, prefer ECOTOX values where conflict).

**Acceptance:** Bundle produced with `aggregation_n` documenting consolidation.

---

#### Task B4: Daphnia acute EC50
**Depends on:** Group A.
**Source:** ECOTOX.
**Specifics:**
- Filter to:
  - Species = *Daphnia magna* (allow *D. pulex* as secondary, flag with `species_secondary`)
  - Endpoint = `EC50`
  - Effect = `IMM` (immobilisation) or `MOR`
  - Test duration = 48h (with 5% tolerance)
- Canonical units: `mg/L`.
- log10-transform: `value_log = log10(EC50_mol_per_L)`.

**Acceptance:** Bundle produced.

---

#### Task B5: Algae growth EC50
**Depends on:** Group A.
**Source:** ECOTOX.
**Specifics:**
- Filter to:
  - Species ∈ {*Raphidocelis subcapitata* (formerly *Pseudokirchneriella subcapitata*), *Chlorella vulgaris*, *Selenastrum capricornutum* (synonym), *Desmodesmus subspicatus*}
  - Endpoint ∈ {`EC50`, `ErC50` (growth-rate-based), `EbC50` (biomass-based)}
  - Effect = `GRO` (growth) or `POP` (population)
  - Test duration = 72h (with 10% tolerance)
- Canonical units: `mg/L`.
- log10-transform: `value_log = log10(EC50_mol_per_L)`.
- Prefer `ErC50` over `EbC50` where both exist for the same record (growth-rate-based is the OECD 201 reference).

**Acceptance:** Bundle produced.

---

#### Task B6: Earthworm acute LC50
**Depends on:** Group A.
**Sources:**
- Kotli et al. 2024, *J. Hazard. Mater.* 461:132577 — supplementary dataset (PPDB-derived).
- Pore et al. 2024, *J. Hazard. Mater.* 479:135725 — supplementary dataset.

**Specifics:**
- Both papers compile from PPDB but PPDB itself is licensed — **do not redistribute PPDB content directly**. Use only the structures and values disclosed in the published supplementary files, which is permissible under the publications' terms.
- Species: *Eisenia fetida* (standard) or *Eisenia andrei* (acceptable substitute).
- Canonical units: `mg/kg dry soil`.
- log10-transform: `value_log = log10(LC50_mg_per_kg)`.
- Cross-source deduplication by InChIKey; geometric mean for conflicts.
- Where the published compilations omit the OECD test guideline, assume OECD 207 (14-day) and document this assumption.

**Acceptance:** Bundle produced. Document in `docs/PHASE1_NOTES.md` that source records are from published supplementary material, not PPDB directly.

---

#### Task B7: Bird acute oral LD50
**Depends on:** Group A.
**Sources:**
- ECOTOX (filtered to avian species).
- EFSA OpenFoodTox (Zenodo deposit — locate latest version).
- Optionally: avian portions of EPA pesticide ecological risk assessments.

**Specifics:**
- Species pooling: produce primary records for the two regulatory species (*Colinus virginianus* — bobwhite quail; *Anas platyrhynchos* — mallard duck), but **also** retain *Coturnix japonica*, *Phasianus colchicus*, *Passer domesticus* records and tag `species`. Phase 2 models may decide to pool or split.
- Endpoint = `LD50`, exposure route = `oral`.
- Canonical units: `mg/kg bw`.
- log10-transform: `value_log = log10(LD50_mg_per_kg)`.
- Data is sparse — accept all OECD 223 records (14-day) and document the smaller dataset size honestly in the card.

**Acceptance:** Bundle produced. Card explicitly states n per species.

---

#### Task B8: Soil Koc
**Depends on:** Group A.
**Sources:**
- OPERA training data via the NIEHS OPERA GitHub repository (https://github.com/NIEHS/OPERA).
- OECD 121 / OECD 106 compilations from published supplementary material.

**Specifics:**
- Canonical units: log10 L/kg (Koc is typically reported as log Koc directly).
- For ionizable compounds: prefer Koc values measured at pH 5.5–7 (the regulatory standard range); flag others as `quality_flags=["ph_outside_range"]`.
- Compute pKa via RDKit / ChemAxon if available — record in `quality_flags` (e.g., `["ionizable_acid"]`) when applicable. If neither tool available, skip pKa annotation.

**Acceptance:** Bundle produced.

---

#### Task B9: Soil DT50
**Depends on:** Group A.
**Source:** EAWAG-SOIL via enviPath (https://envipath.org/) — Soil package bulk export.
**Specifics:**
- enviPath access may require an account. If API access is blocked, expect a human to drop the bulk export at `data/raw/dt50/envipath/`. Document any blocker.
- Canonical units: `days`.
- log10-transform: `value_log = log10(DT50_days)`.
- **Multi-record per compound**: EAWAG-SOIL gives multiple DT50 values per compound from different soil studies. Do NOT aggregate to a single value — preserve all records and add a `study_id` column. The geometric mean and CV go in `aggregation_cv` but Phase 2 will likely model the *distribution*, not the mean (following Gnann et al. 2025 *ES&T*).
- This is the only endpoint with intentionally one-to-many records-per-compound. Document this clearly.

**Acceptance:** Bundle produced. Card explicitly notes the one-to-many record structure.

---

#### Task B10: BCF
**Depends on:** Group A.
**Sources:**
- OPERA BCF training set (NIEHS GitHub).
- Lunghini et al. 2020 (*Environ. Sci. Pollut. Res.*) supplementary compilation.

**Specifics:**
- Whole-fish endpoint; reject records limited to specific tissues (liver, gills).
- Canonical units: `L/kg` (BCF is unitless but typically reported as L/kg wet weight).
- log10-transform: `value_log = log10(BCF)`.
- Flag ionizable compounds — BCF for weak acids/bases differs significantly between LogP and LogD-based predictions. Add `quality_flags=["ionizable"]` where pKa is between 3 and 11.

**Acceptance:** Bundle produced.

---

#### Task B11: Skin sensitization
**Depends on:** Group A.
**Sources:**
- NICEATM LLNA dataset (public release).
- ICCVAM CCS (Cosmetics Substance) dataset where overlapping.

**Specifics:**
- **Classification endpoint** — no continuous value.
- Two label schemes; the agent produces both:
  - Binary: `value_class ∈ {"sensitizer", "non_sensitizer"}`.
  - 4-class GHS: `value_class ∈ {"non", "weak", "moderate", "strong"}` based on LLNA EC3 thresholds (EC3 > 100, 10–100, 1–10, < 1 % respectively).
- Resolve label conflicts: prefer LLNA over CCS where both exist.
- Apply random and scaffold splits stratified by 4-class label. Time split likely not feasible (no consistent year metadata).

**Acceptance:** Bundle produced with both binary and 4-class labels.

---

### Group C — Quality Assurance

#### Task C1: Cross-endpoint sanity checks
**Depends on:** All B-tasks complete.
**File:** `python/edeon_data/tests/test_endpoint_smoke.py`
**Action:** For each curated bundle, assert:
- Schema conformance (all records validate against `CuratedRecord`).
- No null `inchikey` or `value`.
- No leakage across splits.
- Data card YAML validates against `DataCard` schema.
- SHA-256 manifest matches actual files.
- Per-endpoint minimum size threshold met (configurable; default 100 compounds).

**Acceptance:** All endpoints pass smoke tests in CI.

---

#### Task C2: Cross-endpoint compound overlap report
**Depends on:** C1.
**Action:** Produce `data/curated/_cross_endpoint_overlap.csv` listing InChIKeys present in ≥ 2 endpoints with their values. This is the basis for Paper 3's "shared compounds" cross-endpoint analysis.

**Acceptance:** Report exists.

---

#### Task C3: Split tightness audit
**Depends on:** C1.
**Action:** For each scaffold split, verify the mean test-set nearest-neighbour Tanimoto similarity is < 0.5 (the "challenging split" threshold). If exceeded for any endpoint, flag in `docs/PHASE1_NOTES.md` for human review — the scaffold algorithm may have produced an unrealistically easy split (e.g., not enough scaffold diversity).

**Acceptance:** Audit complete; report any concerns.

---

#### Task C4: Curation summary report
**Depends on:** C1.
**File:** `docs/CURATION_SUMMARY.md`
**Action:** Auto-generated table of:
- Endpoint
- Raw records → curated records
- Rejection rate
- Train/cal/test sizes (per split type)
- Value range (log)
- Key biases noted in card

This document is one of the central artefacts for Paper 3.

**Acceptance:** Markdown document generated and committed.

---

### Group D — Release Bundle

#### Task D1: Manifest
**Depends on:** All B and C tasks.
**Action:** Build a top-level `data/curated/MANIFEST.json` listing every dataset with version, SHA-256s, sizes, and source DOIs. This is the artefact downstream consumers (Phase 2 trainers, Paper 3 supplementary) reference.

**Acceptance:** Manifest exists and validates against a JSON schema in `python/edeon_data/schema.py`.

---

#### Task D2: Zenodo deposit preparation
**Depends on:** D1.
**Action:** Bundle all curated/* into a single Zenodo-ready archive:
- `edeon-curated-datasets-v1.0.zip` containing the `data/curated/` tree.
- A top-level `README.md` summarising the bundle, citation, license terms per endpoint.
- A `CHANGELOG.md` for future version bumps.

The actual Zenodo upload is a manual step (requires Anthropic auth / Zenodo account). Document the prepared bundle path and provide a checklist for the human to complete:
- [ ] Create Zenodo deposit with title "Edeon Curated Agrochemistry Datasets v1.0"
- [ ] Upload the zip
- [ ] Add metadata (authors, license, related identifiers)
- [ ] Reserve DOI
- [ ] Update `data_card.yaml` files with the reserved DOI under `dataset_doi`
- [ ] Publish

**Acceptance:** Bundle ready at known path with checklist.

---

#### Task D3: Data smoke CI workflow
**Depends on:** C1.
**File:** `.github/workflows/data_smoke.yml`
**Action:**

```yaml
name: Data Smoke Tests
on: [push, pull_request]
jobs:
  smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: |
          pip install -e ./python/edeon_data
          pip install pytest
      - name: Verify manifests
        run: |
          python -m edeon_data.tools.verify_manifests
      - name: Run smoke tests
        run: pytest python/edeon_data/tests/test_endpoint_smoke.py -v
```

Run only on commits touching `data/curated/` or `python/edeon_data/`.

**Acceptance:** Workflow runs on PR.

---

## 10. Acceptance Criteria for Phase 1 Complete

Phase 1 is complete when ALL of the following hold:

1. The directory tree from Section 3 exists.
2. The shared infrastructure (Group A) passes all unit tests.
3. For all 11 endpoint identifiers (B1 covers two), a `data/curated/<endpoint>/v1.0/` bundle exists with:
   - `curated.parquet` and `curated.csv` (≥ 100 records, ≥ 95% schema conformance)
   - Scaffold splits in `splits/scaffold/{train,cal,test}.parquet`
   - Random splits in `splits/random/{train,cal,test}.parquet`
   - Time splits in `splits/time/{train,cal,test}.parquet` where year metadata permits (else documented absence)
   - `data_card.yaml` validating against the schema
   - `curation_log.json`
   - `manifest.json` with SHA-256 of every file
4. `docs/CURATION_SUMMARY.md` summarises all endpoints.
5. `docs/DATASET_SOURCES.md` documents every source.
6. `docs/CURATION_RULES.md` documents both shared and per-endpoint rules.
7. `data/curated/MANIFEST.json` is complete.
8. CI smoke tests (`data_smoke.yml`) pass.
9. Zenodo bundle prepared at `dist/edeon-curated-datasets-v1.0.zip` with checklist.
10. `docs/PHASE1_NOTES.md` documents all deviations, manual interventions, and blockers.

---

## 11. Out of Scope (for Phase 1)

Explicitly **do not** in Phase 1:

- Train any models. (Phase 2.)
- Compute featurizations beyond what's needed for scaffold-splitting (no fingerprint files, no descriptor matrices saved). Phase 2 will compute features from the curated SMILES.
- Integrate live API queries into Edeon at runtime — Phase 1 is offline batch curation.
- Modify any Phase 0 code (`edeon_models/`). Phase 1 *uses* the Endpoint enum from Phase 0 but does not change it.
- Add UI for the data pipeline. Phase 1 is CLI + filesystem artefacts only.
- Build user-facing documentation for compound lookup. The curated datasets are developer/researcher artefacts in Phase 1.
- License PPDB or redistribute PPDB content. The earthworm endpoint uses only the published supplementary files of Kotli/Pore.
- Train tokenisation or embedding models on compound corpora.

If the agent identifies that Phase 1 cannot be completed without one of the above, document in `docs/PHASE1_NOTES.md` and stop.

---

## 12. Manual / Human-in-the-loop Steps

The agent should run all stages it can, then write a checklist of items needing human action:

- **enviPath authentication** for EAWAG-SOIL bulk export, if blocked by API requirements. Place the manually exported file at `data/raw/dt50/envipath/` and re-run.
- **Atom allowlist decisions** for endpoints involving metals (copper-based fungicides for bee, mercury legacy chemicals for fish). The agent applies a conservative allowlist by default and flags affected records — a human approves whether to relax.
- **Aggregation conflicts**: any compound with `aggregation_cv > 1.0` and `aggregation_n > 10` should be listed in a human-review CSV at `data/curated/<endpoint>/v1.0/_review_conflicts.csv`. The agent does NOT silently apply judgment in these cases.
- **Zenodo deposit** publication and DOI reservation.
- **Author list, license fine-print, and acknowledgements** for the Zenodo metadata.

---

## 13. Conventions

- **Naming**: `snake_case` for Python; bundle directories use lower-case endpoint identifiers with underscores.
- **Versioning**: dataset bundles use semantic versions starting at `v1.0`. Increment minor (`v1.1`) for additional records from the same sources with the same curation logic; major (`v2.0`) when curation rules change.
- **Reproducibility**: every random operation seeded with `42`. RDKit version pinned in `pyproject.toml`.
- **Logging**: use Python `logging` with logger `edeon_data`. Each pipeline stage emits structured records to the per-endpoint `curation_log.json`.
- **Timezones**: all timestamps UTC, ISO 8601.

---

## 14. Phase 1 → Phase 2 Handoff

Phase 2 will consume Phase 1's outputs as follows:

- Featurisation will be applied **freshly** to each split using each model's featurizer; no precomputed features ship with Phase 1 bundles.
- The `cal` split is reserved for conformal prediction calibration in Phase 2. Phase 2 must not touch `test` until final reporting.
- The `data_card.yaml` becomes the model card's `training_data` and `applicability_domain.training_set_size` fields.
- The `MANIFEST.json` SHA-256 hashes become the `model_card.training_data.sha256` provenance.

Any Phase 2 task that needs Phase 1 data refers to it by:
`data/curated/<endpoint>/v1.0/splits/<split_type>/<partition>.parquet`

---

## 15. Deviation Log

Maintain `docs/PHASE1_NOTES.md` with:
- Source URLs that have moved or required workarounds.
- Records sent to human review and the resolutions.
- Decisions about atom allowlists and metal-containing compounds.
- enviPath access status.
- Any endpoint where rejection rate exceeded 20% and the agent's investigation.
- Final compound counts and any deviation from expected sizes per Section 5.

This is the artefact a human reviewer reads to validate Phase 1.

---

**End of Phase 1 Specification.**
