# Edeon Phase 6 — Engineering Fixes Implementation Specification

**Audience:** coding agent.
**Goal:** replace the two remaining engineering-grade liabilities in Edeon with proper implementations:

1. **Bioisostere engine** — replace the hard-coded SMILES pattern-matching with a proper SMARTS-transformation library backed by SwissBioisostere data and/or mmpdb-derived rules. Each suggested replacement carries source database, occurrence frequency in marketed compounds, and **computed** property deltas using the deployed Tier-1 models (not directional hints).
2. **3D docking** — replace the misleading "load a conformer into the same viewport" with actual AutoDock Vina docking against the loaded receptor structure, with user-defined or auto-detected binding box. Optional GNINA support for CNN-rescored docking.

This phase introduces no ML model training. It is pure engineering work: data acquisition, binary integration, frontend wiring, and cross-platform packaging.

**Independence note:** the bioisostere engine (Groups A + C-bio) and docking (Groups B + C-dock) are fully independent. Two agents could work in parallel without conflicts. Each piece can ship separately if the other slips.

---

## 0. Context and Hard Rules

**Hard rule 1: bioisostere suggestions must compute real property deltas, not directional hints.**
The current implementation says "replace CF3 with CHF2 will probably reduce LogP." That's hand-waving. The Phase 6 engine generates the actual transformed molecule, runs it through the deployed Tier-1 backends, and shows the *numerical* predicted property values (with CIs from Phase 2-5 conformal calibration) for both original and transformed compounds.

**Hard rule 2: 3D docking must be actual docking, not visualization theatre.**
The Phase 6 docking workflow:
- Prepares the loaded receptor as a Vina-compatible PDBQT
- Prepares the query ligand via Meeko (RDKit-based PDBQT conversion)
- Calls the Vina binary as a subprocess
- Parses the multiple poses returned with their binding scores
- Renders each pose in the existing NGL.js viewer with its score
- Shows a docking score badge (in kcal/mol, with explicit "estimate from empirical scoring function" caveat)

No silent "conformer loaded next to protein" pretending to be docking.

**Hard rule 3: license discipline.**
- AutoDock Vina is Apache 2.0 (verify at integration time — license has evolved across Vina versions). Bundling with Edeon is acceptable.
- GNINA is GPL-2.0 / GPL-3.0. Bundling with a commercial closed-source Edeon would create license obligations. GNINA support is therefore **opt-in via user-provided binary path**, not bundled. Document this explicitly.
- Meeko is LGPL-2.1 — acceptable to bundle via Python dependency.
- Open Babel (alternative ligand prep) is GPL-2.0; same concern as GNINA — only invoke if user provides the binary.
- SwissBioisostere data is published under restrictive terms — verify before redistributing. mmpdb-derived transformations from public ChEMBL data are clean.

**Hard rule 4: no fake fallback.**
If Vina is not installed or fails, the docking UI shows an explicit error with installation instructions. It does NOT fall back to the previous conformer-only visualization. The fake-docking liability is removed permanently.

---

## 1. Tech Stack Assumptions

**Bioisostere engine:**
- RDKit (existing dependency) — for SMARTS matching, reaction enumeration via `Chem.AllChem.ReactionFromSmarts`, structure standardisation
- mmpdb ≥ 3.0 (optional) — for matched molecular pair analysis if deriving transformations locally
- pydantic v2 — for transformation rule schema
- SQLite — for the local transformation library

**3D docking:**
- **AutoDock Vina ≥ 1.2.5** — primary docking engine, bundled as platform-specific binary
- **Meeko ≥ 0.5** (`pip install meeko`) — modern Python tool for ligand and receptor preparation to PDBQT format
- **RDKit** — for ligand conformer generation prior to Meeko prep
- **fpocket** (optional) — pocket detection for auto-box mode; bundled binary
- **GNINA ≥ 1.0** — optional, user-provided path

**Frontend:**
- Existing NGL.js viewer in `Viewer3dView`
- Existing React component infrastructure
- New UI: docking dialog (box config, run button, pose list), bioisostere carousel updates

**Cross-platform binary distribution:**
- Linux x86_64: bundled binaries
- macOS arm64 + x86_64: bundled binaries (signed)
- Windows x86_64: bundled binaries

---

## 2. Architectural Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Edeon Frontend                                │
│  ┌─────────────────────────┐   ┌─────────────────────────────────┐  │
│  │ Bioisostere Carousel    │   │ 3D Viewer + Docking Dialog      │  │
│  │ (Inspector right pane)  │   │ (Viewer3dView)                  │  │
│  │  - Pattern matches      │   │  - Box config (auto / manual)   │  │
│  │  - Computed deltas      │   │  - Run docking button           │  │
│  │  - Source provenance    │   │  - Pose list with scores        │  │
│  └─────────────────────────┘   └─────────────────────────────────┘  │
└───────────────┬──────────────────────────────┬──────────────────────┘
                │                              │
                ▼                              ▼
┌─────────────────────────┐    ┌──────────────────────────────────────┐
│  BioisostereEngine      │    │  DockingService                      │
│  (Python service)       │    │  (Python service)                    │
│  - Library load         │    │  - Receptor preparation (Meeko)      │
│  - Pattern matching     │    │  - Ligand preparation (Meeko+RDKit)  │
│  - Reaction enumeration │    │  - Vina subprocess execution         │
│  - Property prediction  │    │  - Pose parsing                      │
│    via T1 backends      │    │  - Optional GNINA invocation         │
└─────────────────────────┘    └──────────────────────────────────────┘
                │                              │
                ▼                              ▼
┌─────────────────────────┐    ┌──────────────────────────────────────┐
│  SQLite Library         │    │  Bundled Binaries                    │
│  bioisostere.db         │    │  src-tauri/resources/                │
│  - Transformations      │    │    vina_<platform>                   │
│  - Source metadata      │    │    fpocket_<platform> (optional)     │
│  - Occurrence counts    │    │                                      │
└─────────────────────────┘    └──────────────────────────────────────┘
                                              │
                                              ▼
                                    ┌──────────────────────────────┐
                                    │  Phase 2-5 BackendRegistry   │
                                    │  Used for property deltas    │
                                    │  on bioisostere candidates    │
                                    └──────────────────────────────┘
```

The bioisostere engine *consumes* the Tier-1 backends from Phases 2–5 to compute property deltas on transformed structures. This is the architectural reason Phase 6 comes last: it leverages everything that came before.

---

## 3. Repository Layout

```
edeon/
├── python/
│   ├── edeon_bioisostere/                       # NEW
│   │   ├── __init__.py
│   │   ├── cli.py
│   │   ├── library_loader.py                    # Loads SQLite transformation DB
│   │   ├── library_builder.py                   # Builds DB from raw sources
│   │   ├── transformation_engine.py             # Apply transformations to query
│   │   ├── property_delta.py                    # Compute deltas via T1 backends
│   │   ├── ranking.py                           # Rank suggestions by criteria
│   │   ├── schema.py                            # Pydantic models
│   │   └── tests/
│   └── edeon_docking/                           # NEW
│       ├── __init__.py
│       ├── cli.py
│       ├── receptor_prep.py                     # PDB → PDBQT
│       ├── ligand_prep.py                       # SMILES → PDBQT via Meeko
│       ├── box_detection.py                     # Auto-box from cocrystal / fpocket
│       ├── vina_runner.py                       # Subprocess wrapper for Vina
│       ├── gnina_runner.py                      # Optional GNINA subprocess
│       ├── pose_parser.py                       # PDBQT output → pose objects
│       ├── schema.py                            # Pydantic models
│       └── tests/
├── data/
│   ├── bioisostere/
│   │   └── v1.0/
│   │       ├── bioisostere.db                   # SQLite transformation library
│   │       ├── manifest.json
│   │       └── source_data/                     # Raw downloads (gitignored)
│   └── docking/
│       └── prepared_receptors/                  # Pre-prepared PDBQT for built-in targets
│           ├── ALS.pdbqt
│           ├── EPSPS.pdbqt
│           └── ... (the 8 preset targets from existing 3D viewer)
├── src-tauri/
│   └── resources/
│       └── bin/
│           ├── vina_linux_x86_64
│           ├── vina_macos_arm64
│           ├── vina_macos_x86_64
│           ├── vina_windows_x86_64.exe
│           ├── fpocket_linux_x86_64             # Optional
│           └── ...
├── src/
│   └── components/
│       ├── bioisostere/                         # MODIFIED
│       │   ├── BioisostereCarousel.tsx          # Replaces hard-coded version
│       │   ├── TransformationCard.tsx
│       │   └── PropertyDeltaTable.tsx
│       └── docking/                             # NEW
│           ├── DockingDialog.tsx
│           ├── BoxConfigPanel.tsx
│           ├── PoseList.tsx
│           └── DockingScoreBadge.tsx
├── docs/
│   ├── PHASE6_NOTES.md
│   ├── PHASE6_BIOISOSTERE_LIBRARY.md            # Methodology + source citations
│   ├── PHASE6_DOCKING_PROTOCOL.md               # Methodology + parameter rationale
│   └── PHASE6_LICENSING_AUDIT.md                # License analysis of all components
└── .github/
    └── workflows/
        └── phase6_smoke.yml
```

---

## 4. Methodology Standards

### 4.1 Bioisostere engine

#### 4.1.1 Transformation rule schema

```python
# python/edeon_bioisostere/schema.py
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Literal


class TransformationRule(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule_id: str = Field(..., description="Stable identifier (e.g. 'sbs_00042')")
    pattern_smarts: str = Field(..., description="SMARTS to match in query molecule")
    replacement_smarts: str = Field(..., description="SMARTS describing the substitution")
    reaction_smarts: str = Field(..., description="Full RDKit reaction SMARTS (pattern>>product)")
    source: Literal["swissbioisostere", "mmpdb_chembl_approved", "manual_curation"] = "swissbioisostere"
    source_reference: Optional[str] = Field(None, description="DOI, URL, or citation")
    context: Optional[str] = Field(None, description="Activity context if known (e.g. 'kinase inhibitors')")
    occurrence_frequency: int = Field(..., description="Count of occurrences in source database")
    occurrence_in_marketed_drugs: Optional[int] = Field(None, description="Count among approved drugs subset")
    direction_notes: Optional[str] = Field(None, description="Free-text directional notes if any")
    synthetic_complexity_delta: Optional[float] = Field(None, description="Expected change in SA score, if known")
```

#### 4.1.2 Library construction sources

Priority order:

**Primary: SwissBioisostere extraction**
- Source: https://www.swissbioisostere.ch/ (verify URL at runtime)
- Format: their published CSV/TSV exports of significant bioisosteric transformations
- License: verify before redistributing — they explicitly state academic use terms; the agent must check whether bundling the *derived rules* (not the raw database) is permitted. If not permissible to bundle, fall back to mmpdb-derived rules and document.

**Fallback / Complement: mmpdb on ChEMBL approved drugs**
- Run `mmpdb` against the public ChEMBL approved drugs subset (~3,000–5,000 compounds)
- Extract matched molecular pairs with significant property shifts
- Filter to transformations occurring ≥ 5 times in the corpus
- This is fully unencumbered (public ChEMBL data + open-source mmpdb)

**Manual curation supplement**
- Classical agrochemistry-relevant bioisosteres from medicinal chemistry literature:
  - CF3 ↔ CHF2 ↔ CCl3
  - Carboxylic acid ↔ tetrazole ↔ acylsulfonamide
  - Amide ↔ retro-amide ↔ urea
  - Phenyl ↔ pyridyl (multiple regioisomers)
  - Aliphatic ↔ alicyclic (cyclopropyl, cyclobutyl)
- Augment with citations to medicinal chemistry textbook chapters

#### 4.1.3 Application pipeline

For a query SMILES:

1. **Parse and standardise** the query molecule (using Phase 1 standardiser).
2. **Pattern matching**: against every rule's `pattern_smarts`, find all matches. Multiple matches per molecule are normal.
3. **Reaction enumeration**: for each match, apply the `reaction_smarts` to generate candidate products. Use `Chem.AllChem.ReactionFromSmarts(...).RunReactants(...)`.
4. **Sanity filtering** on each candidate:
   - Valid molecule (parseable, valences correct)
   - MW within reasonable range (50–1500 Da)
   - Atom allowlist (no exotic atoms introduced)
   - No fragment count change unless rule allows
   - SA score (synthetic accessibility, from RDKit Descriptors) within tolerable range
5. **Property delta computation**: for each surviving candidate, predict via the registered Tier-1 backends:
   - All ecotox endpoints (bee, fish, daphnia, algae, earthworm, bird) — Phase 2
   - Soil fate (Koc, DT50, GUS) — Phase 3
   - Mammalian tox (rat LD50, skin sens, mutagenicity) — Phase 4
   - Physicochemical (LogP, MW, TPSA, etc.) — RDKit direct
   - BCF + photostability class — Phase 5
6. **Ranking** by composite score (Section 4.1.5).
7. **Top-N selection** (default 5–10 transformations) for UI display.

#### 4.1.4 Computed property deltas

For each suggested transformation, the output shows:
- Original property predictions (with CIs from T1 backends)
- Transformed property predictions (with CIs)
- Δ values (computed in log space where applicable to avoid scale artefacts)
- Tier and AD status for both original and transformed compound
- Warning flag if transformed compound is **out of AD** for any backend

The AD warning is particularly important: a bioisostere might push the molecule outside the training distribution, in which case the predicted properties for the transformed compound are unreliable. The UI must surface this clearly.

#### 4.1.5 Ranking

Default scoring criterion: composite that minimises predicted regulatory liabilities while preserving target-relevant properties. For an agrochemistry context:

```python
def score_transformation(
    original_preds: dict[str, Prediction],
    transformed_preds: dict[str, Prediction],
    weights: dict[str, float] = None,
) -> float:
    """Returns a transformation score (higher = better).

    Default weights prioritise: better ecotox profile (lower bee/fish toxicity),
    lower mammalian toxicity, lower environmental persistence, with property
    space staying in pesticide-like range.
    """
    weights = weights or {
        "bee_ld50": +0.20,            # higher LD50 is better → positive delta good
        "fish_lc50": +0.15,
        "rat_oral_ld50": +0.15,
        "mutagenicity_prob": -0.10,   # lower prob is better → negative delta good
        "skin_sens_prob": -0.05,
        "soil_dt50": -0.10,           # lower DT50 (less persistent) is better
        "bcf": -0.10,
        "tice_likeness_violations": -0.15,  # fewer violations better
    }
    # Compute weighted sum of normalized deltas...
```

Make weights user-configurable (per the audit's MPO weights request).

For UI sort: also offer "minimal change" sort by transformation similarity (Tanimoto between original and transformed). Useful for SAR rounds where chemists want minimal scaffold change.

### 4.2 3D docking

#### 4.2.1 Docking pipeline

```
1. Receptor preparation
   Input: Loaded receptor structure (PDB from RCSB or user upload)
   Output: PDBQT file with H, Gasteiger charges, polar H only
   Tool: Meeko's receptor preparation
   Cache: prepared PDBQT cached per receptor + version

2. Ligand preparation
   Input: SMILES from Inspector
   Steps:
     a. Parse with RDKit (Phase 1 standardised)
     b. Generate 3D conformer (ETKDGv3 method) and minimize (MMFF94)
     c. Convert to PDBQT via Meeko, identifying rotatable bonds
   Output: PDBQT with explicit rotamers

3. Box definition
   Three modes:
     a. Auto from cocrystal ligand: if receptor has a HET ligand, center box on it
     b. Auto from pocket: use fpocket to find largest cavity, center box there
     c. Manual: user sets center (X, Y, Z) and size (each axis)
   Default size: 22 Å × 22 Å × 22 Å (typical Vina default)

4. Vina execution
   Command: vina --receptor R.pdbqt --ligand L.pdbqt \
                  --center_x X --center_y Y --center_z Z \
                  --size_x 22 --size_y 22 --size_z 22 \
                  --exhaustiveness 8 --num_modes 9 \
                  --out poses.pdbqt --seed 42
   Default exhaustiveness: 8 (fast, ~20-60s on typical hardware)
   Premium exhaustiveness: 32 (~3-5 min, better accuracy)

5. Pose parsing
   Parse poses.pdbqt: each MODEL block is a pose
   Extract: pose index, Vina score (kcal/mol), heavy atom coordinates
   Compute: RMSD between consecutive poses for diversity assessment

6. Visualization
   Load original receptor in NGL viewer (already done by existing code)
   Add pose as separate component
   Color by score: top pose green, descending to orange for weaker
   Allow user to step through poses with score badges
```

#### 4.2.2 Score interpretation

Vina scores are approximate binding free energy estimates in kcal/mol. Display with clear caveat:

- Score ≤ -10 kcal/mol: "Strong binding (interpret cautiously — empirical estimate)"
- -10 to -8: "Moderate binding"
- -8 to -6: "Weak binding"
- ≥ -6: "Unfavorable"

The caveat must always be visible — Vina scores are *not* experimental K_d / IC50 values and the empirical scoring function has known limitations on metal-containing complexes, highly polarisable systems, and entropy-dominated bindings.

#### 4.2.3 Performance considerations

- Default exhaustiveness 8 gives ~20-60 second turnaround on a modern laptop
- Box size affects runtime: larger box = more orientations to sample
- Provide UI progress indicator with "Estimated time: ~30s" message during run
- Cache prepared receptors aggressively (one prep per receptor × Edeon version)
- Allow the user to cancel a running docking job

#### 4.2.4 GNINA support (optional)

If the user provides a path to a GNINA binary (in settings):

```
gnina --receptor R.pdbqt --ligand L.pdbqt \
       --center_x ... --center_y ... --center_z ... \
       --size_x 22 --size_y 22 --size_z 22 \
       --exhaustiveness 8 --num_modes 9 \
       --cnn_scoring rescore \
       --out poses.sdf
```

GNINA uses CNN-rescored Vina poses. Display both the Vina score and the GNINA CNN score. The CNN score is in arbitrary units (higher = stronger predicted binding in the model's training distribution).

GPL licensing means Edeon does NOT distribute the GNINA binary. The Settings panel has a field "GNINA binary path (optional)" where the user pastes their own install.

---

## 5. Per-Component Specifications

### 5.1 Bioisostere engine

```yaml
# python/edeon_bioisostere/config.yaml
library_path: data/bioisostere/v1.0/bioisostere.db
default_top_n: 8
sources:
  swissbioisostere:
    enabled: true
    weight: 1.0
  mmpdb_chembl_approved:
    enabled: true
    weight: 1.0
  manual_curation:
    enabled: true
    weight: 1.5  # Prefer manually curated rules
property_delta_endpoints:
  - bee_acute_oral_ld50
  - fish_acute_lc50
  - daphnia_acute_ec50
  - rat_acute_oral_ld50
  - skin_sensitization
  - mutagenicity_ames
  - soil_dt50
  - bcf
  - photostability_class
sanity_filters:
  mw_min: 50
  mw_max: 1500
  sa_score_max: 6.0
  max_fragment_count: 1
ranking:
  default_weights:
    bee_acute_oral_ld50: 0.20
    fish_acute_lc50: 0.15
    rat_acute_oral_ld50: 0.15
    mutagenicity_ames: -0.10
    skin_sensitization: -0.05
    soil_dt50: -0.10
    bcf: -0.10
    tice_violations: -0.15
ui_default_sort: composite_score
```

### 5.2 Docking service

```yaml
# python/edeon_docking/config.yaml
vina:
  binary_paths:
    linux_x86_64: src-tauri/resources/bin/vina_linux_x86_64
    macos_arm64: src-tauri/resources/bin/vina_macos_arm64
    macos_x86_64: src-tauri/resources/bin/vina_macos_x86_64
    windows_x86_64: src-tauri/resources/bin/vina_windows_x86_64.exe
  default_exhaustiveness: 8
  premium_exhaustiveness: 32
  default_num_modes: 9
  default_box_size: [22, 22, 22]   # Å per axis
  default_seed: 42
gnina:
  enabled_via_settings: true
  binary_path: null                # User-provided
fpocket:
  binary_paths:
    linux_x86_64: src-tauri/resources/bin/fpocket_linux_x86_64
    # ...
  enabled: optional
prep:
  ligand_engine: meeko
  receptor_engine: meeko
  conformer_method: ETKDGv3
  conformer_optimization: MMFF94
prepared_receptor_cache_dir: data/docking/prepared_receptors
prebuilt_targets:                  # The 8 preset targets in the 3D viewer
  - id: ALS
    pdb_code: 1YHY
    default_box_center: [12.0, 8.5, -3.2]   # Determined from cocrystal
  - id: EPSPS
    pdb_code: 2GG4
    default_box_center: [...]
  # ... 6 more
```

---

## 6. Task Manifest

---

### Group A — Bioisostere Engine

#### Task A1: Project scaffolding
**Depends on:** Phase 2+ complete (need T1 backends available for property deltas).
**Files:** Create `python/edeon_bioisostere/` directory tree from Section 3. Add `pyproject.toml` entry. Define CLI entry point.

**Acceptance:** `python -c "import edeon_bioisostere"` works. `edeon-bioisostere --help` prints usage.

---

#### Task A2: Transformation rule schema
**Depends on:** A1.
**File:** `python/edeon_bioisostere/schema.py`
**Action:** Implement `TransformationRule` from Section 4.1.1. Add `BioisostereSuggestion` (containing original SMILES, transformed SMILES, applied rule, property predictions for both).

**Acceptance:** Round-trip JSON serialisation works.

---

#### Task A3: SwissBioisostere data acquisition
**Depends on:** A1.
**File:** `python/edeon_bioisostere/library_builder.py`
**Action:**
- Implement `acquire_swissbioisostere(output_dir)`: download SwissBioisostere significant transformations dataset. **Verify URL at runtime** — the SwissBioisostere data export interface has changed over years.
- Parse the dataset format (likely TSV or CSV of pattern,replacement pairs with significance metrics).
- Convert each pair to a `TransformationRule` with `source="swissbioisostere"`.
- **Licensing check**: before bundling, verify that derived rules are redistributable. If not, output the raw rules but flag them as "user must download separately."

If access is blocked, document in `PHASE6_NOTES.md` and proceed with mmpdb-derived rules only.

**Acceptance:** Either raw rules downloaded and parsed, OR documented gap with workaround.

---

#### Task A4: mmpdb-derived rules from ChEMBL approved
**Depends on:** A2.
**File:** `python/edeon_bioisostere/library_builder.py` (extend)
**Action:**
- Fetch ChEMBL approved drugs subset (or use a pre-curated list — ~3,500 compounds; available from ChEMBL's REST API filtered on `max_phase=4`)
- Run mmpdb to identify matched molecular pairs:
  ```bash
  mmpdb fragment input.smi -o fragments.dat
  mmpdb index fragments.dat -o pairs.dat
  ```
- Extract transformations occurring ≥ 5 times in the corpus
- Convert each to a `TransformationRule` with `source="mmpdb_chembl_approved"`
- Compute `occurrence_in_marketed_drugs` directly (this is what mmpdb's index gives)

Document the exact ChEMBL release version used.

**Acceptance:** Produces ≥ 200 rules (typical for the 5-occurrence threshold).

---

#### Task A5: Manual curation rules
**Depends on:** A2.
**File:** `python/edeon_bioisostere/library_builder.py` (extend)
**Action:** Author ≥ 25 manually-curated classical bioisosteres with citations. Examples:

```python
MANUAL_RULES = [
    {
        "rule_id": "manual_001_cf3_to_chf2",
        "pattern_smarts": "[CX4](F)(F)F",
        "replacement_smarts": "[CX4](F)(F)[H]",
        "reaction_smarts": "[CX4:1]([F:2])([F:3])[F:4]>>[CX4:1]([F:2])([F:3])[H]",
        "occurrence_frequency": 50,  # Approximate from medchem literature
        "direction_notes": "Reduces LogP by ~0.3, retains H-bond acceptor character",
        "source_reference": "Hagmann WK (2008) J Med Chem 51:4359",
    },
    # ... 24 more
]
```

Cover at least: halogen exchanges, classical heterocycle swaps (phenyl/pyridyl/thiophenyl), carboxylic acid mimics (tetrazole, acylsulfonamide), amide retro-amide, ring-expansion bioisosteres.

**Acceptance:** ≥ 25 rules with citations.

---

#### Task A6: Library SQLite store
**Depends on:** A3, A4, A5.
**File:** `python/edeon_bioisostere/library_builder.py` (extend) + `library_loader.py`
**Action:** Build SQLite database at `data/bioisostere/v1.0/bioisostere.db` with table:

```sql
CREATE TABLE transformations (
    rule_id TEXT PRIMARY KEY,
    pattern_smarts TEXT NOT NULL,
    replacement_smarts TEXT NOT NULL,
    reaction_smarts TEXT NOT NULL,
    source TEXT NOT NULL,
    source_reference TEXT,
    context TEXT,
    occurrence_frequency INTEGER NOT NULL,
    occurrence_in_marketed_drugs INTEGER,
    direction_notes TEXT,
    synthetic_complexity_delta REAL,
    json_blob TEXT NOT NULL    -- Full TransformationRule serialised
);

CREATE INDEX idx_source ON transformations(source);
CREATE INDEX idx_occurrence ON transformations(occurrence_frequency DESC);
```

Provide `load_rules(source_filter=None, min_occurrences=1) -> list[TransformationRule]`.

Generate `data/bioisostere/v1.0/manifest.json` with version, rule counts per source, build date, source provenance.

**Acceptance:** DB built; loader returns valid rules.

---

#### Task A7: Transformation engine
**Depends on:** A6.
**File:** `python/edeon_bioisostere/transformation_engine.py`
**Action:** Core application logic per Section 4.1.3:

```python
class TransformationEngine:
    def __init__(self, library: list[TransformationRule]):
        self._rules = library
        # Precompile SMARTS patterns and reactions
        ...

    def apply_to_query(
        self,
        query_smiles: str,
        max_transformations_per_rule: int = 3,
    ) -> list[CandidateTransformation]:
        """For each matching rule, generate candidate products.
        Apply sanity filters. Return list of (rule, original, candidate)."""
        ...

    def _sanity_filter(self, candidate_mol) -> bool:
        """Apply MW range, atom allowlist, SA score, fragment count checks."""
        ...
```

**Acceptance:** Unit test on imidacloprid SMILES generates ≥ 10 valid candidates that pass sanity filters.

---

#### Task A8: Property delta computation
**Depends on:** A7, Phase 2+ backends registered.
**File:** `python/edeon_bioisostere/property_delta.py`
**Action:**

```python
class PropertyDeltaCalculator:
    """Computes predicted property deltas via the registered Tier-1 backends."""

    def __init__(self, registry: BackendRegistry, endpoints: list[Endpoint]):
        self._registry = registry
        self._endpoints = endpoints

    def predict_both(
        self, original_smiles: str, candidate_smiles: str
    ) -> dict[str, dict[str, Prediction]]:
        """Returns {endpoint: {"original": Prediction, "candidate": Prediction}}.
        Uses each endpoint's T1 backend if registered, else T2."""
        ...

    def compute_deltas(
        self, predictions: dict[str, dict[str, Prediction]]
    ) -> dict[str, dict[str, Any]]:
        """For each endpoint, compute the numeric delta and flag AD status changes."""
        ...
```

The output for each endpoint includes:
- Original value + CI + AD
- Candidate value + CI + AD
- Numeric delta
- AD warning flag if candidate is outside AD when original was in

**Acceptance:** Predicting on a known SAR pair (e.g., imidacloprid → desnitro-imidacloprid) shows expected directional shifts in bee LD50.

---

#### Task A9: Ranking
**Depends on:** A8.
**File:** `python/edeon_bioisostere/ranking.py`
**Action:** Implement per Section 4.1.5. Default composite scoring; provide alternative sorts (minimal-change, by single endpoint improvement, by occurrence frequency).

**Acceptance:** Ranking produces sensible top-N on the imidacloprid test case.

---

#### Task A10: CLI and IPC integration
**Depends on:** A9.
**Files:** `cli.py`, plus extend Phase 0's IPC server to expose:
- `bioisostere_suggest(smiles: str, top_n: int = 8, sort_by: str = "composite") -> list[BioisostereSuggestion]`

CLI exposes `edeon-bioisostere suggest --smiles CCO --top-n 5`.

**Acceptance:** Tauri command `bioisostere_suggest` callable from frontend.

---

### Group B — 3D Docking

#### Task B1: Project scaffolding
**Depends on:** Phase 0 complete.
**Files:** Create `python/edeon_docking/` directory tree. Add to project setup.

**Acceptance:** `python -c "import edeon_docking"` works.

---

#### Task B2: Receptor preparation
**Depends on:** B1.
**File:** `python/edeon_docking/receptor_prep.py`
**Action:**

```python
def prepare_receptor_pdb_to_pdbqt(
    pdb_path: Path,
    output_pdbqt: Path,
    keep_hetatm: bool = False,
    add_hydrogens: bool = True,
) -> dict:
    """Convert PDB → PDBQT using Meeko. Returns metadata dict with chain count,
    residue range, charge sum, prepared atom count."""
```

Use Meeko's receptor preparation API. Handle multi-chain receptors. Strip waters and HETATM by default (unless `keep_hetatm=True` and the user wants cofactors preserved).

**Acceptance:** Preparing a PDB file from the 8 preset targets produces a valid PDBQT loadable by Vina (verify by spawning Vina with `--help` and ensuring no PDBQT parse error).

---

#### Task B3: Ligand preparation
**Depends on:** B1.
**File:** `python/edeon_docking/ligand_prep.py`

```python
def prepare_ligand_smiles_to_pdbqt(
    smiles: str,
    output_pdbqt: Path,
    conformer_method: str = "ETKDGv3",
    optimization: str = "MMFF94",
    embed_attempts: int = 10,
) -> dict:
    """Steps:
    1. Parse SMILES with RDKit
    2. Add hydrogens (Chem.AddHs)
    3. Embed 3D conformer with ETKDGv3
    4. Optimize with MMFF94
    5. Hand off to Meeko's MoleculePreparation for PDBQT conversion
    Returns metadata (rotatable bond count, charge, etc.)
    """
```

Handle failure modes:
- Conformer embedding failure: retry up to `embed_attempts`; if all fail, raise
- Force-field optimisation failure: log warning, proceed with embedded conformer
- Meeko prep failure: log error, raise

**Acceptance:** Preparing imidacloprid SMILES produces a valid PDBQT with the expected rotatable bond count.

---

#### Task B4: Box detection
**Depends on:** B1.
**File:** `python/edeon_docking/box_detection.py`

```python
def detect_box_from_cocrystal_ligand(
    pdb_path: Path,
    hetatm_residue_name: Optional[str] = None,
    padding: float = 5.0,
) -> dict:
    """If receptor has a cocrystal ligand, center box on it.
    Returns {center: [x, y, z], size: [sx, sy, sz]}"""

def detect_box_from_fpocket(
    pdb_path: Path,
    fpocket_binary: Path,
    pocket_rank: int = 1,
) -> dict:
    """Run fpocket and use the highest-ranked pocket centroid."""

def auto_detect_box(
    pdb_path: Path,
    fpocket_binary: Optional[Path] = None,
) -> dict:
    """Try cocrystal ligand first, fall back to fpocket, fall back to receptor centroid."""
```

**Acceptance:** Detecting box on a preset target (e.g., HPPD with cocrystal mesotrione) returns plausible center coordinates.

---

#### Task B5: Vina runner
**Depends on:** B2, B3, B4.
**File:** `python/edeon_docking/vina_runner.py`

```python
class VinaRunner:
    def __init__(self, vina_binary: Path):
        self._binary = vina_binary

    def run(
        self,
        receptor_pdbqt: Path,
        ligand_pdbqt: Path,
        center: tuple[float, float, float],
        size: tuple[float, float, float] = (22.0, 22.0, 22.0),
        exhaustiveness: int = 8,
        num_modes: int = 9,
        seed: int = 42,
        output_pdbqt: Optional[Path] = None,
        timeout_sec: int = 300,
    ) -> VinaResult:
        """Run Vina via subprocess. Returns VinaResult with poses and scores."""
```

`VinaResult` contains:
- List of poses (each with score, RMSD to top pose, PDBQT block)
- Vina version string
- Command line used
- Elapsed time
- Any stderr warnings

Handle subprocess timeout, Vina binary not found, Vina segfault.

**Acceptance:** Running Vina on a preset target × imidacloprid produces ≥ 1 pose with a sensible score (typically -5 to -10 kcal/mol).

---

#### Task B6: Pose parser
**Depends on:** B5.
**File:** `python/edeon_docking/pose_parser.py`

```python
def parse_vina_output_pdbqt(pdbqt_path: Path) -> list[DockedPose]:
    """Parse Vina's multi-model PDBQT output.
    Each MODEL block is one pose. Extract score from REMARK lines."""

@dataclass
class DockedPose:
    pose_index: int
    score_kcal_per_mol: float
    rmsd_lb: Optional[float]  # Vina's internal RMSD bounds
    rmsd_ub: Optional[float]
    pdbqt_block: str
    sdf_representation: Optional[str]  # For viewer convenience
```

Convert PDBQT to SDF for visualization (via Meeko or Open Babel if available).

**Acceptance:** Parsing the test Vina output produces a list of DockedPose with valid scores.

---

#### Task B7: GNINA runner (optional)
**Depends on:** B6.
**File:** `python/edeon_docking/gnina_runner.py`
**Action:** Similar to VinaRunner but invokes GNINA. Disabled unless user provides binary path in settings. CNN rescoring mode.

**Acceptance:** When GNINA binary is provided, produces poses with both Vina and CNN scores. When absent, runner is gracefully unavailable.

---

#### Task B8: IPC integration
**Depends on:** B5, B6.
**Action:** Extend Phase 0 IPC server with:
- `docking_run(receptor_path: str, smiles: str, box_config: dict, options: dict) -> DockingResult`
- `docking_auto_box(receptor_path: str) -> dict`

Add corresponding Tauri commands.

**Acceptance:** Tauri command runs end-to-end against a preset target.

---

#### Task B9: Bundle Vina binaries
**Depends on:** B5.
**Files:** `src-tauri/resources/bin/` + Tauri build config
**Action:**
- Download Vina 1.2.5 (or newer) precompiled binaries for each target platform
- Place in `src-tauri/resources/bin/`
- Update `tauri.conf.json` to include them as resources
- At first run, verify binary executable and version match the expected hash
- Add license file at `src-tauri/resources/bin/LICENSE-VINA.txt`

**Acceptance:** Built Tauri app on each platform includes the binary at the expected path.

---

#### Task B10: Pre-prepare receptors for preset targets
**Depends on:** B2, B9.
**Action:** For each of the 8 preset targets in the existing 3D viewer (ALS, EPSPS, HPPD, GS, ACCase, PPO, PSII, SDH), run receptor preparation once at build time. Commit the prepared PDBQT files to `data/docking/prepared_receptors/`. Also commit the per-target default box centers (Section 5.2 config).

**Acceptance:** All 8 preset targets have prepared PDBQT and default boxes.

---

### Group C-bio — Bioisostere Frontend

#### Task C-bio-1: Replace BioisostereCarousel
**Depends on:** A10.
**File:** Locate existing bioisostere carousel component (`Inspector.tsx` or a sub-component). Replace contents with a new version using IPC backend:

For each suggestion:
- 2D structure of original vs. transformed (RDKit render)
- Source tag (SwissBioisostere / mmpdb / manual)
- Occurrence count badge
- Compact property delta table: each row shows Endpoint | Original (T1 value + CI) | Transformed (T1 value + CI) | Δ | AD warning if applicable
- "View full details" expander
- "Compare with original" toggle that re-renders the Inspector preview with the candidate molecule

**Acceptance:** Carousel works end-to-end: input SMILES → top-N suggestions with computed property deltas.

---

#### Task C-bio-2: Ranking controls
**Depends on:** C-bio-1.
**Action:** Add sort dropdown: "Composite score" (default), "Minimal change", "By endpoint improvement" (with sub-dropdown for which endpoint). Add an "Adjust weights" expander revealing a sliders panel for the composite score weights (analogous to the MPO weights feature from the audit's recommendations).

**Acceptance:** Sorting and weight adjustment work; visible ordering changes accordingly.

---

### Group C-dock — Docking Frontend

#### Task C-dock-1: Docking dialog component
**Depends on:** B8.
**File:** `src/components/docking/DockingDialog.tsx`

Layout:
- Header: "Dock ligand into [Receptor name]"
- Ligand source: "Current Inspector compound" (default) or "Custom SMILES"
- Box configuration panel:
  - Mode toggle: Auto (cocrystal/fpocket) | Manual
  - If Manual: 6 sliders (center X, Y, Z; size X, Y, Z) with current values
  - Visual indicator on the 3D viewer showing the box
- Run options:
  - Exhaustiveness slider: Fast (4) | Default (8) | Premium (32)
  - Number of poses dropdown: 1, 3, 5, 9 (default), 15
  - Optional GNINA toggle (if binary available)
- Run button: "Dock" (changes to "Cancel" during run)
- Progress indicator with elapsed time estimate

**Acceptance:** Dialog renders correctly; "Dock" button triggers backend run.

---

#### Task C-dock-2: Pose list and viewer integration
**Depends on:** C-dock-1.
**File:** `src/components/docking/PoseList.tsx` + extend existing viewer

After docking completes:
- Show ranked list of poses with score badges (kcal/mol)
- Selecting a pose loads it into the existing NGL viewer alongside the receptor
- Compare mode: toggle between two poses with side-by-side or overlay rendering
- Score interpretation caveat tooltip on every score badge

Add a "Vina score interpretation" info panel that explains:
- What Vina scores mean
- That they're empirical estimates, not measured K_d
- Score ranges (strong / moderate / weak / unfavorable)
- Known limitations

**Acceptance:** Selecting poses updates the viewer; score caveats visible.

---

#### Task C-dock-3: Remove fake-docking remnants
**Depends on:** C-dock-2.
**Action:** Locate and remove the existing "load conformer into the same viewport" code path. Ensure no UI element still implies docking outside the real workflow. Update the 3D viewer's tooltips and help text.

**Acceptance:** No remaining UI surface presents conformer-loading as docking.

---

### Group D — Validation, CI, Documentation

#### Task D1: Bioisostere smoke test
**Depends on:** A10.
**File:** `python/edeon_bioisostere/tests/test_smoke.py`
**Action:** Test that:
- Library loads with at least 100 rules
- Imidacloprid query produces ≥ 5 valid suggestions
- All suggestions have valid 2D depictions
- All suggestions have at least 3 endpoint deltas computed
- Top suggestion is recommended consistently across repeated invocations (deterministic)

**Acceptance:** Test passes.

---

#### Task D2: Docking smoke test
**Depends on:** B10.
**File:** `python/edeon_docking/tests/test_smoke.py`
**Action:** Test that:
- Vina binary is present and executable
- Preparing a preset target's prebuilt PDBQT loads successfully
- Preparing imidacloprid SMILES produces valid PDBQT
- Docking imidacloprid against ALS produces ≥ 1 pose with score in [-12, 0] kcal/mol
- Box detection on a preset target returns valid coordinates

**Acceptance:** Test passes. Document any platform-specific failures in PHASE6_NOTES.

---

#### Task D3: Phase 6 CI workflow
**Depends on:** D1, D2.
**File:** `.github/workflows/phase6_smoke.yml`

```yaml
name: Phase 6 Engineering Smoke
on: [push, pull_request]
jobs:
  phase6:
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: |
          pip install -e ./python/edeon_bioisostere
          pip install -e ./python/edeon_docking
          pip install meeko rdkit pytest
      - name: Verify bundled binaries
        run: python scripts/verify_phase6_binaries.py
      - name: Run bioisostere smoke
        run: pytest python/edeon_bioisostere/tests/ -v
      - name: Run docking smoke
        run: pytest python/edeon_docking/tests/ -v
```

**Acceptance:** CI passes on all three platforms.

---

#### Task D4: Documentation
**Depends on:** A10, B10.
**Files:**
- `docs/PHASE6_BIOISOSTERE_LIBRARY.md` — methodology, sources, citations, license discussion
- `docs/PHASE6_DOCKING_PROTOCOL.md` — Vina parameters, score interpretation, known limitations
- `docs/PHASE6_LICENSING_AUDIT.md` — full license analysis for every bundled component

**Acceptance:** All three documents committed.

---

#### Task D5: End-to-end integration test
**Depends on:** all previous.
**File:** `tests/integration/test_phase6_e2e.py`
**Action:** End-to-end test exercising the full Tauri command path:
- Bioisostere suggest → returns valid suggestions with computed property deltas via T1 backends
- Docking run on a preset target → returns valid poses with scores
- GNINA path absent → docking still works (Vina-only path)

**Acceptance:** Test passes.

---

## 7. Acceptance Criteria for Phase 6 Complete

Phase 6 is complete when ALL of the following hold:

1. **Bioisostere engine:**
   - Library SQLite DB at `data/bioisostere/v1.0/bioisostere.db` contains ≥ 200 rules across multiple sources.
   - Transformation engine generates valid suggestions with sanity filtering.
   - Property deltas computed via the deployed T1 backends with CIs and AD warnings.
   - Frontend carousel shows suggestions with full property comparison.
   - Ranking controls work; weights adjustable.

2. **3D docking:**
   - Vina binaries bundled for all three platforms; verified at runtime.
   - All 8 preset receptors have prepared PDBQT and default boxes.
   - Docking dialog UI complete with all three box modes.
   - Pose list integrates with NGL viewer.
   - All fake-docking code paths removed.
   - GNINA opt-in via settings works when binary is provided.

3. **Documentation:** PHASE6_BIOISOSTERE_LIBRARY.md, PHASE6_DOCKING_PROTOCOL.md, PHASE6_LICENSING_AUDIT.md, PHASE6_NOTES.md populated.

4. **CI:** Phase 6 smoke workflow passes on Linux, macOS, Windows.

5. **License compliance:** Bundled binaries comply with their respective licenses (Vina Apache 2.0). GNINA never bundled. SwissBioisostere data either properly licensed for redistribution or accessed via documented user download.

---

## 8. Out of Scope (for Phase 6)

Do **not** in Phase 6:

- Train any ML models or update any Tier-1 backends.
- Implement FEP+ or other rigorous free-energy methods.
- Build a covalent docking workflow (Vina supports it; out of scope for v1).
- Implement protein flexibility (sidechain or backbone) during docking.
- Build retrosynthesis or reaction prediction features.
- Implement quantum-chemical optimization (DFT/semi-empirical) of ligands beyond MMFF94.
- Add ensemble docking against multiple receptor conformations.
- Modify any Phase 0-5 model backends or curated datasets.

If the agent identifies that Phase 6 cannot be completed without one of the above, document in `PHASE6_NOTES.md` and stop.

---

## 9. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| SwissBioisostere data is no longer redistributable | Fall back to mmpdb + manual rules. ~250 rules from mmpdb + 25 manual is enough for a defensible launch. |
| mmpdb running on full ChEMBL approved is slow | Pre-compute at build time, ship the DB. Document the ChEMBL release used. |
| Vina binary version differs across platforms | Pin specific Vina version (1.2.5+); verify with `vina --version` at first run; show error if mismatched. |
| Meeko fails on unusual ligand structures (organometallic, fragments) | Document supported structure classes. Fail gracefully with clear error message. |
| fpocket binary not available on all target platforms | fpocket is optional; box auto-detection falls back to cocrystal ligand or receptor centroid. |
| GNINA binary path is user-provided and could be arbitrary | Validate signature / sanity-check before subprocess invocation (run `--version` first); log all command lines. |
| Docking takes too long for interactive UX | Default exhaustiveness=8 gives ~30-60s; provide visible progress; allow cancellation. |
| Cross-platform binary signing for macOS | Macos arm64 + x86_64 builds need to be signed and notarized for Gatekeeper. Document the signing process for production builds. |
| Bioisostere suggestions trip AD warnings on most candidates | Expected — bioisosteres often push molecules toward novel chemical space. The AD warning is correct, not a bug. UI must communicate clearly. |
| Phase 6 work blocks on a Phase 2-5 backend issue | Phase 6 is the last phase; document any T1 backend bugs found and fix in a separate maintenance pass. |

---

## 10. Conventions

- Random seeds: Vina default seed 42. Ligand conformer embedding: ETKDGv3 with seed 42.
- License files: every bundled binary or data source has a `LICENSE-<name>.txt` adjacent to the artifact.
- Naming: `snake_case` Python, `PascalCase` React components, `kebab-case` CLI commands.
- Logging: `edeon_bioisostere` and `edeon_docking` loggers; structured JSON to stderr in subprocess wrappers.

---

## 11. Handoff Notes

Phase 6 completion means:

- **Every actively-displayed prediction or interactive feature in Edeon is now scientifically defensible.** No fake docking, no hard-coded bioisostere suggestions, no LogP-heuristic predictions in any default display.
- **Commercial pitch is complete.** The product story end-to-end: "Trained Tier-1 models with calibrated UQ for every regulatory endpoint, qualitative alerts (with citations) where prediction is genuinely impossible, real AutoDock Vina docking for binding analysis, and a SwissBioisostere/mmpdb-backed bioisostere engine with computed property deltas via the deployed models." That story has no asterisks.
- **Subjective credibility moves from ~8.5/10 to ~9.5/10.** The remaining gap is just routine product maturity (more endpoints, more receptors, more rule library curation) rather than any structural credibility issue.
- **Paper 3** can ship independently of Phase 6 — the docking and bioisostere features are product capabilities, not benchmark contributions.
- **Future work** (Phase 7+) becomes about ecosystem expansion: more bioisostere sources, GPU-accelerated docking via Uni-Mol or DiffDock as T3 options, multi-ligand docking, formulation/synergy modules, etc.

---

## 12. Deviation Log

Maintain `docs/PHASE6_NOTES.md` with:
- Vina version actually bundled per platform.
- SwissBioisostere licensing resolution (bundled / user-download).
- mmpdb / ChEMBL version used to derive rules.
- fpocket availability per platform.
- Cross-platform binary signing status.
- Final bioisostere rule count by source.
- Any preset receptors where prep failed or required manual intervention.
- Manual curation list — which rules were added and citations.

---

**End of Phase 6 Specification.**
