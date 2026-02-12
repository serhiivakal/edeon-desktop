# Edeon Docking Workbench — GUI & Automation Implementation Specification

**Audience:** coding agent.
**Goal:** transform the existing 3D viewer (`Viewer3dView`) from a passive structural viewer with fake "docking" into a full **Docking Workbench**: a guided workflow with automatic receptor preparation, HET atom curation, visual binding-pocket configuration, automated ligand preparation, real AutoDock Vina docking, pose analysis with automatic interaction detection, and job management.

This spec supersedes the docking-side tasks in the previous Phase 6 spec (Groups B and C-dock) and replaces them with a more comprehensive workbench design. The bioisostere side of Phase 6 (Group A + C-bio) is unaffected.

**Inputs:**
- Phase 0 architecture (ModelBackend interface, IPC infrastructure).
- Existing 3D viewer code in `Viewer3dView` using NGL.js.
- Existing preset receptor library (ALS, EPSPS, HPPD, GS, ACCase, PPO, PSII, SDH).
- Phase 6 backend modules (`edeon_docking/`) if already built — extend rather than replace.

**Outputs:** a full docking workbench replacing the current `Viewer3dView`, backed by automated preparation and analysis services, with persistent job history.

---

## 0. Context and Hard Rules

**Hard rule 1: no fake docking under any circumstance.**
The current "load a conformer into the same viewport" code path must be removed. If Vina is unavailable or fails, the workbench shows an explicit error with installation guidance — it does NOT silently fall back to conformer-only visualization.

**Hard rule 2: every operation that takes more than 2 seconds must be visible.**
Receptor preparation, ligand preparation, pocket detection, and docking all qualify. Each shows progress indication, estimated time, and a cancel button. Long-running operations run in worker threads/subprocesses, not on the UI thread.

**Hard rule 3: caching is mandatory.**
Prepared receptors are cached per receptor × preparation-settings hash. Pocket detection results are cached per receptor. Docking results are cached per job (receptor × ligand × box × options hash). The user pays the preparation cost once, not on every interaction.

**Hard rule 4: Vina scores carry explicit caveats, always.**
Every place a Vina score is displayed, it carries either a permanent "kcal/mol — empirical estimate" label or a tooltip explaining that scores are not measured K_d values. Section 4.6 specifies the exact text.

**Hard rule 5: licensing discipline.**
- AutoDock Vina (Apache 2.0) — bundled per platform
- Meeko (LGPL-2.1) — Python dependency
- fpocket (MIT) — bundled per platform, optional
- PLIP (GPL-2.0) — for interaction detection. **Cannot bundle in a closed-source product.** Use an MIT/BSD-licensed alternative: implement interaction detection using RDKit + custom geometry checks (Section 4.7), OR use ProLIF (Apache 2.0) which is MIT-licensed and pip-installable.
- GNINA (GPL) — never bundled; user-provided binary path via Settings

---

## 1. Tech Stack Assumptions

**Backend (Python):**
- AutoDock Vina ≥ 1.2.5 (bundled binary)
- Meeko ≥ 0.5 (receptor + ligand PDBQT preparation)
- RDKit (existing; for conformer generation, structure standardisation)
- fpocket ≥ 4.0 (bundled binary, optional pocket detection)
- ProLIF ≥ 2.0 (MIT-licensed protein-ligand interaction analysis) — install via pip
- Biopython ≥ 1.83 (PDB parsing, structure manipulation)
- pdb2pqr ≥ 3.6 (optional, for advanced H-addition with PROPKA) — fallback to RDKit if not available

**Backend (Rust/Tauri):**
- Existing IPC infrastructure
- Tokio for async background tasks
- Tauri's resource bundling for the binaries

**Frontend (TypeScript/React):**
- NGL.js (existing) for 3D rendering
- React (existing component library)
- shadcn/ui (or existing component library)
- Three.js (potentially via NGL's underlying renderer) for box overlay rendering

---

## 2. Architectural Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                  Docking Workbench (Frontend)                        │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ Left panel: Receptor & Pocket                                  │ │
│  │  - Receptor selector (preset / PDB code / AF / upload)         │ │
│  │  - Prep status                                                 │ │
│  │  - HET atom list with keep/strip toggles                       │ │
│  │  - Pocket detection: cocrystal | fpocket | manual              │ │
│  │  - Box configuration (visual + numeric)                        │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ Center: 3D viewer (NGL.js)                                     │ │
│  │  - Receptor cartoon                                            │ │
│  │  - Pocket surface (when detected)                              │ │
│  │  - Box wireframe overlay                                       │ │
│  │  - Docked pose (when selected)                                 │ │
│  │  - Interaction lines (H-bonds, hydrophobic)                    │ │
│  │  - Distance measurements                                       │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ Right panel: Ligand & Results                                  │ │
│  │  - Ligand source (Inspector / SMILES / file)                   │ │
│  │  - Prep status                                                 │ │
│  │  - Docking options (exhaustiveness, num_modes)                 │ │
│  │  - Run / Cancel button                                         │ │
│  │  - Pose list with scores                                       │ │
│  │  - Interaction fingerprint per selected pose                   │ │
│  │  - Export controls                                             │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ Bottom: Job history (collapsible)                              │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                              │ (Tauri IPC)
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       Backend Services                               │
│                                                                      │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────┐ │
│  │ ReceptorSvc    │  │ LigandSvc      │  │ PocketSvc              │ │
│  │ - load         │  │ - prepare      │  │ - detect cocrystal     │ │
│  │ - prepare      │  │   PDBQT        │  │ - run fpocket          │ │
│  │ - cache        │  │ - cache        │  │ - rank pockets         │ │
│  │ - HET parse    │  │                │  │                        │ │
│  └────────────────┘  └────────────────┘  └────────────────────────┘ │
│                                                                      │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────┐ │
│  │ DockingSvc     │  │ AnalysisSvc    │  │ JobHistorySvc          │ │
│  │ - run Vina     │  │ - ProLIF       │  │ - persist to SQLite    │ │
│  │ - parse poses  │  │   interactions │  │ - list/filter/restore  │ │
│  │ - cache        │  │ - distances    │  │                        │ │
│  └────────────────┘  └────────────────┘  └────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Bundled binaries + cached artifacts                                 │
│  src-tauri/resources/bin/{vina,fpocket}_<platform>                  │
│  data/docking/cache/                                                 │
│    receptors/<receptor_hash>/prepared.pdbqt                          │
│    pockets/<receptor_hash>/pockets.json                              │
│    jobs/<job_hash>/...                                               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Repository Layout

```
edeon/
├── python/
│   └── edeon_docking/
│       ├── __init__.py
│       ├── services/                              # NEW — service layer
│       │   ├── __init__.py
│       │   ├── receptor_service.py
│       │   ├── ligand_service.py
│       │   ├── pocket_service.py
│       │   ├── docking_service.py
│       │   ├── analysis_service.py
│       │   └── job_history_service.py
│       ├── prep/                                  # Existing or new
│       │   ├── receptor_prep.py
│       │   ├── ligand_prep.py
│       │   └── het_parser.py                      # NEW
│       ├── detection/                             # NEW
│       │   ├── cocrystal_detection.py
│       │   ├── fpocket_runner.py
│       │   └── pocket_ranker.py
│       ├── runners/
│       │   ├── vina_runner.py
│       │   └── gnina_runner.py
│       ├── analysis/                              # NEW
│       │   ├── interactions.py                    # ProLIF wrapper
│       │   ├── distance_calc.py
│       │   └── pose_clustering.py
│       ├── cache/                                 # NEW
│       │   ├── __init__.py
│       │   ├── receptor_cache.py
│       │   ├── pocket_cache.py
│       │   └── job_cache.py
│       ├── schema.py                              # All pydantic models
│       └── ipc_handlers.py                        # Tauri IPC command handlers
├── src-tauri/
│   ├── src/
│   │   └── commands/
│   │       └── docking.rs                         # NEW — Tauri command registrations
│   └── resources/
│       └── bin/
│           ├── vina_<platform>
│           └── fpocket_<platform>
├── src/
│   ├── views/
│   │   └── DockingWorkbenchView.tsx               # NEW — replaces Viewer3dView for docking
│   └── components/
│       └── docking/                               # NEW
│           ├── ReceptorPanel.tsx
│           ├── ReceptorSelector.tsx               # Preset/PDB/AF/upload
│           ├── HetAtomList.tsx                    # Keep/strip toggles
│           ├── PocketPanel.tsx
│           ├── BoxConfigPanel.tsx
│           ├── BoxOverlay3D.tsx                   # NGL-integrated box rendering
│           ├── LigandPanel.tsx
│           ├── DockingControlPanel.tsx
│           ├── PoseListPanel.tsx
│           ├── PoseScoreBadge.tsx
│           ├── InteractionFingerprintPanel.tsx
│           ├── DistanceMeasureTool.tsx
│           ├── ViewerControlsPanel.tsx
│           ├── JobHistoryPanel.tsx
│           ├── ScoreInterpretationTooltip.tsx
│           └── DockingProgressBar.tsx
├── data/
│   └── docking/
│       ├── prepared_receptors/                    # Pre-prepared presets
│       │   ├── ALS/
│       │   ├── EPSPS/
│       │   └── ...
│       ├── preset_default_boxes.yaml              # Default box centers per preset
│       └── cache/                                 # Runtime cache (gitignored)
│           ├── receptors/
│           ├── pockets/
│           └── jobs/
├── docs/
│   ├── DOCKING_WORKBENCH_GUIDE.md                 # User-facing docs
│   ├── DOCKING_WORKBENCH_ARCHITECTURE.md          # Developer docs
│   └── DOCKING_WORKBENCH_NOTES.md                 # Deviation log
└── .github/
    └── workflows/
        └── docking_workbench_smoke.yml
```

---

## 4. Methodology and Service Specifications

### 4.1 Receptor Service

#### 4.1.1 Responsibilities
- Load receptor from one of four sources (preset / PDB code / AlphaFold / upload)
- Parse all HET (non-standard) residues with type detection
- Apply preparation pipeline → PDBQT
- Cache prepared receptors

#### 4.1.2 Sources

| Source | Behavior |
|---|---|
| Preset | Load pre-bundled PDB + pre-prepared PDBQT from `data/docking/prepared_receptors/<preset_id>/` |
| PDB code | Fetch from RCSB via `https://files.rcsb.org/download/<code>.pdb`; cache raw PDB locally |
| AlphaFold | Fetch from AlphaFold DB via `https://alphafold.ebi.ac.uk/files/AF-<uniprot>-F1-model_v4.pdb` (verify the v4 version is still current at runtime); show pLDDT-aware warning |
| Upload | User-provided local PDB/CIF file |

#### 4.1.3 HET atom parser

```python
class HetEntry(BaseModel):
    residue_name: str           # e.g. "HOH", "HEM", "NAG", "IMD"
    chain_id: str
    residue_number: int
    atom_count: int
    type_classification: Literal["water", "ion", "cofactor", "cocrystal_ligand",
                                  "modified_residue", "buffer", "unknown"]
    default_action: Literal["strip", "keep"]
    user_action: Literal["strip", "keep"]   # Initially = default_action
```

Classification rules (in `het_parser.py`):
- `HOH`, `H2O` → water → default strip
- Single-atom residues with element ∈ {Na, K, Mg, Ca, Zn, Fe, Cu, Mn} → ion → default keep if in known cofactor list, else strip
- Known cofactors (whitelist): HEM, HEC, FAD, FMN, NAD, NAP, NDP, ATP, ADP, SAM, CLA, BCL, PLP → cofactor → default keep
- Modified amino acids (residue name matching standard modifications) → modified residue → default keep
- Common crystallographic additives: SO4, PO4, GOL (glycerol), EDO (ethylene glycol), PEG-like → buffer → default strip
- Anything else with > 8 atoms and not in standard amino acids → cocrystal_ligand → default strip (it's not part of the receptor) but available as box anchor
- Anything else → unknown → default strip with prominent warning

The user can override each via the HetAtomList UI.

#### 4.1.4 Preparation pipeline

```python
class ReceptorPreparationParams(BaseModel):
    keep_water: bool = False
    keep_ions: bool = False                # Override default keep for ions
    keep_cofactors: bool = True
    keep_cocrystal_ligands: bool = False   # Strip for clean docking
    custom_het_actions: dict[str, str] = {}  # residue_name → "strip"/"keep"
    add_hydrogens: bool = True
    ph: float = 7.4                        # For PROPKA-based H-addition if available
    method: Literal["meeko", "meeko_propka"] = "meeko"
```

Pipeline:
1. Load PDB via Biopython
2. Apply HET actions (strip/keep per residue)
3. Strip chains that are duplicates (for multi-chain crystals; keep the first by default; user-configurable)
4. Add hydrogens via Meeko (default) or pdb2pqr+PROPKA if available
5. Assign Gasteiger charges via Meeko
6. Convert to PDBQT
7. Compute receptor hash = SHA-256(canonical_PDB_bytes + params_canonical_json)
8. Cache result at `data/docking/cache/receptors/<receptor_hash>/prepared.pdbqt`
9. Also cache metadata: chain count, residue count, charge sum, HET actions taken

```python
class PreparedReceptor(BaseModel):
    receptor_hash: str
    pdb_source: str                # URL or file path
    pdbqt_path: Path
    raw_pdb_path: Path
    preparation_params: ReceptorPreparationParams
    metadata: dict[str, Any]       # chain_count, residue_count, charge_sum, etc.
    het_entries: list[HetEntry]
    cocrystal_ligands: list[dict]  # Each: residue_name, chain, centroid_xyz, residue_count
    prepared_at: datetime
```

#### 4.1.5 Cocrystal ligand metadata

For each cocrystal ligand parsed during HET classification:
- Compute centroid (X, Y, Z) of all atoms in the ligand
- Compute bounding box (min/max per axis + 5 Å padding)
- Make this available for "use as box anchor" UI

### 4.2 Ligand Service

#### 4.2.1 Responsibilities
- Accept SMILES (most common) or SDF/MOL file
- Standardise the structure (Phase 1 pipeline)
- Generate 3D conformer
- Minimize
- Convert to PDBQT
- Cache per ligand SMILES + params hash

#### 4.2.2 Pipeline

```python
class LigandPreparationParams(BaseModel):
    conformer_method: Literal["ETKDGv3", "ETKDGv2", "ETDG"] = "ETKDGv3"
    optimization: Literal["MMFF94", "MMFF94s", "UFF", "none"] = "MMFF94"
    embed_attempts: int = 10
    add_hydrogens: bool = True
    pH: float = 7.4              # For protonation state
    deprotonate_acids: bool = True   # COOH → COO⁻
    protonate_bases: bool = True     # amines → ammoniums
```

Pipeline:
1. Parse SMILES with RDKit
2. Apply Phase 1 standardisation if available; otherwise basic cleanup
3. Adjust protonation state for physiological pH (handle acids/bases per params)
4. Add explicit hydrogens
5. Generate 3D conformer using ETKDGv3 with `embed_attempts` retries
6. Optimize with MMFF94 (or chosen force field)
7. Convert to PDBQT via Meeko's MoleculePreparation
8. Hash ligand = SHA-256(canonical_SMILES + params_canonical_json)
9. Cache at `data/docking/cache/ligands/<ligand_hash>/prepared.pdbqt`

```python
class PreparedLigand(BaseModel):
    ligand_hash: str
    source_smiles: str
    canonical_smiles: str
    pdbqt_path: Path
    preparation_params: LigandPreparationParams
    metadata: dict[str, Any]    # rotatable_bonds, formal_charge, atom_count, etc.
    prepared_at: datetime
```

### 4.3 Pocket Service

#### 4.3.1 Detection modes

| Mode | Algorithm | When to use |
|---|---|---|
| `cocrystal` | Use centroid of identified cocrystal ligand | Receptor has a HET ligand and user wants to dock there |
| `fpocket` | Run fpocket, return top N pockets ranked by druggability | No cocrystal ligand or user wants alternative pockets |
| `residue_centroid` | User-provided list of residue IDs; compute centroid | Expert mode: user knows the key residues |
| `manual` | User-provided center coordinates | Power-user override |

#### 4.3.2 fpocket integration

```python
class FpocketResult(BaseModel):
    pocket_id: int
    rank: int                      # 1 = top pocket
    druggability_score: float
    volume_angstrom_cubed: float
    centroid: tuple[float, float, float]
    pocket_residues: list[str]     # e.g. ["A:HIS-440", "A:GLU-327"]
    bounding_box: dict             # min/max per axis


def run_fpocket(receptor_pdbqt_path: Path, fpocket_binary: Path,
                output_dir: Path) -> list[FpocketResult]:
    """Run fpocket and parse the output. Returns top 5 pockets."""
```

fpocket output parsing: process the `pockets_info.txt` or per-pocket `pocket1_atm.pdb` files to extract druggability score, volume, and pocket-lining residues. Sort by druggability descending; return top 5.

#### 4.3.3 Pocket caching

```python
class PocketDetectionResult(BaseModel):
    receptor_hash: str
    fpocket_results: list[FpocketResult]
    cocrystal_pockets: list[dict]  # From receptor's cocrystal ligands
    detected_at: datetime


# Cache at data/docking/cache/pockets/<receptor_hash>/pockets.json
```

#### 4.3.4 Visual highlighting

For each detected pocket, generate a pocket surface mesh (using fpocket's `pocket1_vert.pqr` output or compute via Biopython + scipy as needed). The frontend renders these as semi-transparent colored surfaces; clicking a pocket sets the box center.

### 4.4 Docking Service

#### 4.4.1 Job specification

```python
class DockingJobSpec(BaseModel):
    job_id: str                          # SHA-256 of canonical job parameters
    receptor_hash: str
    ligand_hash: str
    box_center: tuple[float, float, float]
    box_size: tuple[float, float, float]
    exhaustiveness: int = 8
    num_modes: int = 9
    seed: int = 42
    engine: Literal["vina", "gnina"] = "vina"
    gnina_binary_path: Optional[Path] = None
    created_at: datetime


class DockedPose(BaseModel):
    pose_index: int                      # 1-based ranking
    score_kcal_per_mol: float
    rmsd_to_top: Optional[float]
    rmsd_to_prev: Optional[float]
    pdbqt_block: str
    sdf_block: Optional[str]             # For viewer convenience
    gnina_cnn_score: Optional[float]


class DockingJobResult(BaseModel):
    job_id: str
    spec: DockingJobSpec
    poses: list[DockedPose]
    elapsed_seconds: float
    engine_version: str
    command_line: str
    warnings: list[str]
    completed_at: datetime
```

#### 4.4.2 Execution

```python
async def run_docking_job(spec: DockingJobSpec) -> DockingJobResult:
    """
    1. Check cache: data/docking/cache/jobs/<job_id>/result.json
       If exists and valid, return cached
    2. Resolve receptor PDBQT and ligand PDBQT from caches
    3. Construct Vina command with all parameters
    4. Run subprocess with timeout (default 300s, configurable)
    5. Parse output PDBQT poses
    6. Optionally run GNINA for CNN rescoring (per spec.engine)
    7. Cache result
    8. Return
    """
```

Subprocess management: use `asyncio.create_subprocess_exec` so the UI can show progress and the user can cancel. Reading Vina's stderr provides progress percentage on some Vina versions.

### 4.5 Analysis Service

#### 4.5.1 Interaction detection via ProLIF

```python
class InteractionFingerprint(BaseModel):
    pose_index: int
    hbond_donor: list[dict]          # ligand_atom, residue, distance
    hbond_acceptor: list[dict]
    hydrophobic: list[dict]
    pi_stacking: list[dict]
    pi_cation: list[dict]
    salt_bridge: list[dict]
    halogen_bond: list[dict]
    metal_coordination: list[dict]


def analyze_interactions(
    receptor_pdb: Path,
    pose_sdf: str,
    cutoffs: Optional[dict] = None,
) -> InteractionFingerprint:
    """Use ProLIF to compute the interaction fingerprint for a pose."""
```

ProLIF (Apache 2.0) is a Python library for protein-ligand interaction fingerprinting using MDTraj or Biopython. Install via pip. Wraps the seven major interaction types listed above.

If ProLIF fails to install or runs into issues with novel chemistry, provide a custom fallback using RDKit + Biopython that detects H-bonds (geometric criteria), hydrophobic contacts (heavy atom < 4.5 Å), and π-stacking (aromatic ring centroids < 5.5 Å with favorable orientation). Document the fallback in `DOCKING_WORKBENCH_NOTES.md`.

#### 4.5.2 Distance measurements

```python
def measure_distance(
    pose_sdf: str,
    receptor_pdb: Path,
    atom1_selector: str,   # e.g. "ligand:atom_3"
    atom2_selector: str,   # e.g. "A:HIS-440:NE2"
) -> float:
    """Compute Euclidean distance between two atom selections."""
```

Selectors support: ligand atom index, residue selection (chain:resname:resnum:atomname).

#### 4.5.3 Pose clustering

```python
def cluster_poses_by_rmsd(
    poses: list[DockedPose],
    rmsd_cutoff: float = 2.0,
) -> list[list[int]]:
    """Returns list of clusters, each a list of pose indices."""
```

Use heavy-atom RMSD via RDKit. Hierarchical clustering with the cutoff. Useful for collapsing redundant poses in the UI.

### 4.6 Score Interpretation

Wherever a Vina score is displayed, the UI must show or link to:

> Vina's score is an empirical estimate of binding free energy in kcal/mol. It is not a measured K_d or IC50. The scoring function has known limitations on metal complexes, highly polarisable systems, and entropy-driven binding. Use scores for **relative** comparison of poses or compounds, not absolute affinity.

Score-to-category mapping for visual cues:
- ≤ -10.0 kcal/mol: "Strong" — green badge with caveat
- -10.0 to -8.0: "Moderate" — yellow badge
- -8.0 to -6.0: "Weak" — orange badge
- > -6.0: "Unfavorable" — red badge

These categories are *guides*, not regulatory thresholds. The categorisation must be documented in the UI tooltip.

### 4.7 Job History

```python
class JobHistoryEntry(BaseModel):
    job_id: str
    receptor_id: str                # Preset ID or PDB code or hash
    receptor_display_name: str
    ligand_smiles: str
    ligand_display_name: Optional[str]
    box_center: tuple[float, float, float]
    box_size: tuple[float, float, float]
    top_score: float
    num_poses: int
    elapsed_seconds: float
    completed_at: datetime
    starred: bool = False           # User can star jobs to keep
```

SQLite table:

```sql
CREATE TABLE docking_jobs (
    job_id TEXT PRIMARY KEY,
    receptor_id TEXT NOT NULL,
    receptor_display_name TEXT,
    ligand_smiles TEXT NOT NULL,
    ligand_display_name TEXT,
    box_center_x REAL, box_center_y REAL, box_center_z REAL,
    box_size_x REAL, box_size_y REAL, box_size_z REAL,
    top_score REAL,
    num_poses INTEGER,
    elapsed_seconds REAL,
    completed_at TEXT NOT NULL,
    starred INTEGER DEFAULT 0,
    job_spec_json TEXT NOT NULL,
    result_path TEXT NOT NULL
);
CREATE INDEX idx_jobs_receptor ON docking_jobs(receptor_id);
CREATE INDEX idx_jobs_completed ON docking_jobs(completed_at DESC);
```

History panel shows recent jobs (default last 50, paginated), filterable by receptor, by ligand SMILES match, or starred. Click an entry to re-load the docking results without re-running.

---

## 5. Frontend Design

### 5.1 Layout

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Top bar: receptor name, "Save as preset", "Export report"                │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│ ┌────────────┐  ┌────────────────────────────────┐  ┌─────────────────┐ │
│ │ Receptor   │  │                                │  │ Ligand          │ │
│ │ & Pocket   │  │                                │  │ & Docking       │ │
│ │            │  │                                │  │                 │ │
│ │ [Selector] │  │     3D Viewer (NGL.js)         │  │ [SMILES input]  │ │
│ │ [Prep ✓]   │  │                                │  │ [Prep status]   │ │
│ │ [HET list] │  │                                │  │                 │ │
│ │ [Pockets]  │  │                                │  │ Options:        │ │
│ │ [Box cfg]  │  │                                │  │  Exhaustiveness │ │
│ │            │  │                                │  │  Num poses      │ │
│ │            │  │                                │  │                 │ │
│ │            │  │                                │  │ [Dock] button   │ │
│ │            │  │                                │  │                 │ │
│ │            │  │                                │  │ Pose list:      │ │
│ │            │  │                                │  │  1. -9.4  [view]│ │
│ │            │  │                                │  │  2. -8.7  [view]│ │
│ │            │  │                                │  │  ...            │ │
│ │            │  │                                │  │                 │ │
│ │            │  │                                │  │ Interactions:   │ │
│ │            │  │                                │  │  HBond: 3       │ │
│ │            │  │                                │  │  Hydrophobic: 5 │ │
│ │            │  │                                │  │  ...            │ │
│ └────────────┘  └────────────────────────────────┘  └─────────────────┘ │
│                                                                           │
├──────────────────────────────────────────────────────────────────────────┤
│ Bottom: Job history (collapsible)                                        │
└──────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Receptor & Pocket panel components

**`ReceptorSelector.tsx`**:
- Tabs: Presets | PDB Code | AlphaFold | Upload
- Presets: thumbnail grid of the 8 (with future extensibility)
- PDB Code: 4-char input + fetch button + recently-fetched dropdown
- AlphaFold: UniProt ID input + fetch button + organism preset (e.g., human, A. thaliana)
- Upload: file picker accepting .pdb, .cif

On receptor change: invalidate downstream UI (HET list, pockets, box, ligand), show "Preparing receptor..." progress, call `receptor_prepare` IPC, update HET list and metadata.

**`HetAtomList.tsx`**:
- Sectioned list (water / ions / cofactors / cocrystal ligands / other)
- Each entry: residue name + chain + ID, atom count, type classification badge, keep/strip toggle
- Bulk actions: "Strip all waters", "Keep all cofactors", "Reset to defaults"
- Changes trigger receptor re-preparation (debounced — only after user clicks "Apply" or after 2 seconds of inactivity)
- Visual: cocrystal ligands clickable → highlights in 3D viewer + offers "Use as box anchor"

**`PocketPanel.tsx`**:
- Mode selector: "From cocrystal ligand" (if available) | "Auto-detect pockets" (fpocket) | "Specify residues" | "Manual coordinates"
- For "Auto-detect": "Run fpocket" button (or auto-run on receptor change); progress indicator; result list of top 5 pockets with druggability scores
- Clicking a pocket: sets the box, highlights pocket surface in viewer
- For "Specify residues": multi-residue picker (text input with autocomplete)
- For "Manual": exposes box coords directly

**`BoxConfigPanel.tsx`**:
- 6 numeric inputs: center X/Y/Z, size X/Y/Z
- Linked sliders (size sliders link/unlink to maintain aspect ratio)
- "Pad ±N Å" quick controls
- "Reset to default for this receptor" button
- Real-time preview: box overlay updates as values change

**`BoxOverlay3D.tsx`** (NGL integration):
- Renders a wireframe box at the configured coordinates
- Editable handles on each face (for drag-to-resize) — optional v2; v1 uses numeric inputs only
- Color: semi-transparent blue (configurable)

### 5.3 Ligand & Docking panel components

**`LigandPanel.tsx`**:
- Source toggle: "Current Inspector compound" (default) | "Custom SMILES" | "Upload SDF"
- 2D structure preview (RDKit render)
- Prep status: "Preparing ligand..." or "Ready" with rotatable bond count
- Prep options (collapsed by default): protonation, force field
- "Use protonation state at pH ___" input

**`DockingControlPanel.tsx`**:
- Exhaustiveness: Fast (4) / Default (8) / Premium (32) — radio buttons, not slider
- Num poses: dropdown (1, 3, 5, 9, 15)
- "Use GNINA rescoring" (if binary configured in Settings; otherwise disabled with tooltip)
- "Estimated time: ~30s" indicator (computed from exhaustiveness × box_size)
- Run button: large, prominent, "Dock"
- When running: shows progress bar, elapsed time, cancel button

**`PoseListPanel.tsx`**:
- Ranked list with score badge per pose
- Click pose → loads in viewer
- "View all" → cycles through with prev/next buttons in viewer
- "Compare 1 vs 2" → side-by-side or overlay
- Cluster indicator: poses within 2 Å heavy-atom RMSD show as a group with collapse control

**`InteractionFingerprintPanel.tsx`**:
- For the currently-selected pose:
- Summary stats: count per interaction type
- Detail accordion per type: list of contacts with residue + ligand atom + distance
- Click a contact → highlight in viewer (residue + ligand atom + dashed line)
- "Show interactions of type" toggles in viewer

**`DistanceMeasureTool.tsx`**:
- Click "Measure" mode toggle
- Click two atoms in viewer
- Distance displayed
- Persistent measurements list (up to 5); clear button

### 5.4 Job history

**`JobHistoryPanel.tsx`**:
- Collapsible bottom bar (default collapsed)
- Filter: by receptor, by ligand match (SMILES substring), starred only
- Sort: by date (default), by top score, by elapsed time
- Each entry: receptor name, ligand 2D preview, top score, date, "Reload" + "Star" + "Delete" actions
- Reload re-loads the docking result without re-running (uses cached result)

### 5.5 Viewer controls

**`ViewerControlsPanel.tsx`** (separate from receptor/pocket panel):
- Representation: cartoon (default), surface, sticks, hide for receptor
- Pocket residues: "Show residues within ___ Å of ligand" toggle + slider
- Ligand: sticks, ball-and-stick, lines
- Background: light, dark, transparent
- Quality: low / medium / high (affects responsiveness)
- "Center on ligand" button
- "Save screenshot" button (PNG export)

---

## 6. Task Manifest

---

### Group A — Backend Services

#### Task A1: Project scaffolding and schema
**Depends on:** Phase 0.
**Files:** Create `python/edeon_docking/services/` directory; populate `schema.py` with all pydantic models from Sections 4.1.3, 4.2.2, 4.3.1, 4.4.1, 4.5.1, 4.7. Set up logger `edeon_docking`.

**Acceptance:** All models import; round-trip JSON serialisation works.

---

#### Task A2: HET parser
**Depends on:** A1.
**File:** `python/edeon_docking/prep/het_parser.py`
**Action:** Implement per Section 4.1.3 classification rules. Parse a PDB file via Biopython, return a `list[HetEntry]`.

The cofactor allowlist should be a configurable YAML file under `data/docking/cofactor_allowlist.yaml` to allow extension without code change.

**Acceptance:** Tested against the 8 preset receptors — correctly identifies all known cofactors as `keep` and waters as `strip` by default.

---

#### Task A3: Receptor service
**Depends on:** A2.
**File:** `python/edeon_docking/services/receptor_service.py`
**Action:** Implement load (4 sources), HET parsing, preparation pipeline (Section 4.1.4), caching keyed by `receptor_hash`. Use Meeko for PDBQT conversion. Optional pdb2pqr+PROPKA path.

The service exposes:

```python
class ReceptorService:
    async def load_from_source(self, source: ReceptorSource) -> PreparedReceptor: ...
    async def prepare(self, raw_pdb_path: Path, params: ReceptorPreparationParams) -> PreparedReceptor: ...
    def get_cached(self, receptor_hash: str) -> Optional[PreparedReceptor]: ...
```

**Acceptance:** Loading "1YHY" (an ALS structure) downloads, parses HET, prepares with defaults, caches; second load returns from cache without re-download.

---

#### Task A4: Ligand service
**Depends on:** A1.
**File:** `python/edeon_docking/services/ligand_service.py`
**Action:** Implement per Section 4.2.2. Caching keyed by `ligand_hash`.

**Acceptance:** Preparing imidacloprid SMILES three times: first ~3s (real prep), second/third <100ms (cached).

---

#### Task A5: Pocket service
**Depends on:** A3.
**File:** `python/edeon_docking/services/pocket_service.py`
**Action:** Implement per Section 4.3. fpocket integration via subprocess; result parsing; cocrystal-ligand-based detection from receptor metadata.

**Acceptance:** On the ALS preset (with cocrystal sulfonylurea), cocrystal-based detection returns the correct centroid; fpocket on the same returns the same pocket as rank-1.

---

#### Task A6: Docking service
**Depends on:** A3, A4.
**File:** `python/edeon_docking/services/docking_service.py`
**Action:** Vina subprocess execution per Section 4.4. Caching keyed by `job_id`. Async with cancellation support.

```python
class DockingService:
    async def run(self, spec: DockingJobSpec, cancel_event: Optional[asyncio.Event] = None
                  ) -> DockingJobResult: ...
    def get_cached(self, job_id: str) -> Optional[DockingJobResult]: ...
```

Cancel via setting `cancel_event` → service kills the Vina subprocess and cleans up temp files.

**Acceptance:** End-to-end docking of imidacloprid against ALS produces ≥ 5 poses in <90s at default exhaustiveness. Cancellation works (subprocess killed within 2s).

---

#### Task A7: Analysis service
**Depends on:** A6.
**File:** `python/edeon_docking/services/analysis_service.py`
**Action:** ProLIF wrapper for interaction fingerprint; distance measurements; pose clustering. Implement custom RDKit fallback for interactions if ProLIF unavailable.

**Acceptance:** Analyzing a docked pose against ALS returns ≥ 3 detected interactions with named residues.

---

#### Task A8: Job history service
**Depends on:** A6.
**File:** `python/edeon_docking/services/job_history_service.py`
**Action:** SQLite-backed CRUD per Section 4.7. Integrate with the existing project database (add the table to the migration tree).

**Acceptance:** Running 3 dockings produces 3 history entries; loading one returns the cached result.

---

#### Task A9: IPC command handlers
**Depends on:** A3-A8.
**File:** `python/edeon_docking/ipc_handlers.py`
**Action:** Wire up Tauri IPC commands for every user-facing service operation:

- `receptor_load_from_source(source: ReceptorSource) -> PreparedReceptor`
- `receptor_get_het_list(receptor_hash: str) -> list[HetEntry]`
- `receptor_reprepare(receptor_hash: str, params: ReceptorPreparationParams) -> PreparedReceptor`
- `ligand_prepare(smiles: str, params: LigandPreparationParams) -> PreparedLigand`
- `pocket_detect(receptor_hash: str, mode: str) -> PocketDetectionResult`
- `docking_run(spec: DockingJobSpec) -> DockingJobResult` (async with progress events)
- `docking_cancel(job_id: str) -> bool`
- `analysis_interactions(job_id: str, pose_index: int) -> InteractionFingerprint`
- `analysis_distance(job_id: str, pose_index: int, sel1: str, sel2: str) -> float`
- `history_list(filters: dict) -> list[JobHistoryEntry]`
- `history_load(job_id: str) -> DockingJobResult`
- `history_star(job_id: str, starred: bool) -> bool`

Progress events for long operations emit Tauri events: `receptor-prep-progress`, `docking-progress`, `pocket-detect-progress`.

**Acceptance:** All commands callable from frontend; events fire for progress.

---

#### Task A10: Bundle binaries and presets
**Depends on:** A6.
**Action:**
- Bundle Vina ≥ 1.2.5 binaries for Linux/macOS/Windows in `src-tauri/resources/bin/`
- Bundle fpocket ≥ 4.0 binaries (optional; if not available for a platform, document)
- Pre-prepare all 8 preset receptors at build time; commit prepared PDBQT to `data/docking/prepared_receptors/<preset>/`
- Author `data/docking/preset_default_boxes.yaml` with default box centers for each preset (derived from cocrystal ligands or known active sites)
- Bundle the cofactor allowlist YAML

**Acceptance:** Built Tauri app on each platform has working Vina; presets load without runtime preparation.

---

### Group B — Frontend (Receptor & Pocket)

#### Task B1: DockingWorkbenchView shell
**Depends on:** A9.
**File:** `src/views/DockingWorkbenchView.tsx`
**Action:** Three-pane layout per Section 5.1, with the existing NGL viewer in the center pane. Replace whatever the current `Viewer3dView` does as the entry point for the "Viewer" section in the app navigation.

Add app-level state (Zustand or Redux, matching project convention) for:
- Current receptor (PreparedReceptor)
- Current HET state
- Current pocket detection result
- Current box config
- Current ligand
- Current docking result
- Selected pose

**Acceptance:** View renders. State management hooks in place.

---

#### Task B2: ReceptorSelector
**Depends on:** B1.
**File:** `src/components/docking/ReceptorSelector.tsx`
**Action:** Four-tab selector per Section 5.2. Calls `receptor_load_from_source` IPC.

**Acceptance:** Each source loads a receptor; preset selection is instant (cached); PDB code fetch shows progress; AlphaFold fetch shows pLDDT-aware warning.

---

#### Task B3: HetAtomList
**Depends on:** B2.
**File:** `src/components/docking/HetAtomList.tsx`
**Action:** Per Section 5.2. On change, debounce and call `receptor_reprepare`. Click on a cocrystal ligand entry highlights it in the viewer (via NGL atom selection).

**Acceptance:** Toggling waters and re-preparing works; cocrystal ligand click triggers viewer highlight.

---

#### Task B4: BoxOverlay3D
**Depends on:** B1.
**File:** `src/components/docking/BoxOverlay3D.tsx`
**Action:** Integrate with NGL.js to render a wireframe cube at the configured coords. NGL supports custom shape components — use `Shape.addBox(...)` or build with three.js primitives integrated into NGL's stage.

**Acceptance:** Box renders. Updating center/size props re-renders.

---

#### Task B5: PocketPanel
**Depends on:** B2, B4.
**File:** `src/components/docking/PocketPanel.tsx`
**Action:** Per Section 5.2. Calls `pocket_detect`. Renders pocket list. Clicking a pocket sets the box center and triggers viewer pocket-surface rendering.

For pocket surface visualization: NGL can render any PDB residue selection as a surface. For each detected pocket, build a residue selection string from its lining residues and render.

**Acceptance:** Auto-detect finds pockets; clicking sets box; pocket surfaces render distinctively.

---

#### Task B6: BoxConfigPanel
**Depends on:** B4.
**File:** `src/components/docking/BoxConfigPanel.tsx`
**Action:** Numeric inputs + linked sliders per Section 5.2. Real-time update of `BoxOverlay3D` props.

**Acceptance:** Adjusting any value updates the overlay immediately.

---

### Group C — Frontend (Ligand & Docking)

#### Task C1: LigandPanel
**Depends on:** B1.
**File:** `src/components/docking/LigandPanel.tsx`
**Action:** Per Section 5.3. Default to Inspector compound. Calls `ligand_prepare` IPC.

**Acceptance:** Three input modes work; 2D preview renders; prep status updates.

---

#### Task C2: DockingControlPanel
**Depends on:** C1, B6.
**File:** `src/components/docking/DockingControlPanel.tsx`
**Action:** Per Section 5.3. "Estimated time" computed from exhaustiveness × box_size heuristic (e.g., `time_sec ≈ exhaustiveness × (box_volume / 10000) × 1.2`). Run button calls `docking_run`. Listens for `docking-progress` events.

**Acceptance:** Dock button triggers job; progress bar updates; cancel button works.

---

#### Task C3: PoseListPanel
**Depends on:** C2.
**File:** `src/components/docking/PoseListPanel.tsx`
**Action:** Per Section 5.3. Each pose shows a `PoseScoreBadge` (Section C4 below). Click loads pose in viewer via NGL component addition. Cluster collapsing.

**Acceptance:** Poses listed; click loads in viewer.

---

#### Task C4: ScoreInterpretationTooltip + PoseScoreBadge
**Depends on:** none (utility components).
**Files:** `src/components/docking/ScoreInterpretationTooltip.tsx`, `PoseScoreBadge.tsx`
**Action:** Per Section 4.6. Color-coded badges with hover tooltip explaining Vina score interpretation.

**Acceptance:** Badges color correctly per category; tooltip shows.

---

#### Task C5: InteractionFingerprintPanel
**Depends on:** C3.
**File:** `src/components/docking/InteractionFingerprintPanel.tsx`
**Action:** Per Section 5.3. On pose change, call `analysis_interactions`. Each interaction click highlights residue + ligand atom + dashed line in viewer.

**Acceptance:** Interactions display per pose; clicking highlights in viewer.

---

#### Task C6: DistanceMeasureTool
**Depends on:** C3.
**File:** `src/components/docking/DistanceMeasureTool.tsx`
**Action:** Per Section 5.3. Toggle "Measure mode" → next two atom clicks become measurement. Display measurement persistently. Clear button.

**Acceptance:** Distance measurement works for atom pairs.

---

#### Task C7: ViewerControlsPanel
**Depends on:** B1.
**File:** `src/components/docking/ViewerControlsPanel.tsx`
**Action:** Per Section 5.5. Toggles for representations, surface options, "Center on ligand", screenshot export.

**Acceptance:** All controls function.

---

#### Task C8: JobHistoryPanel
**Depends on:** A8, C2.
**File:** `src/components/docking/JobHistoryPanel.tsx`
**Action:** Per Section 5.4. Calls `history_list`, `history_load`, `history_star`. Reload button loads the full state from the cached job result without re-running.

**Acceptance:** Job history persists; reload works.

---

### Group D — Polish & Integration

#### Task D1: Auto-progression flow
**Depends on:** All B + C tasks.
**Action:** When the user selects a receptor, automatically:
1. Trigger preparation
2. On prep complete, auto-run cocrystal-ligand-based pocket detection
3. If a single cocrystal ligand is found, auto-set the box centered on it
4. Otherwise, auto-run fpocket and present pockets for user selection

This creates a "zero-click setup" for the common case of preset receptors with known binding sites.

**Acceptance:** Clicking a preset → box configured automatically within 2 seconds.

---

#### Task D2: Settings integration
**Depends on:** All A tasks.
**Action:** In the existing Settings view, add a "Docking" section:
- Vina binary path (read-only; shows bundled path)
- fpocket binary path (optional; user can override)
- GNINA binary path (optional; user enters path)
- Default exhaustiveness (Fast/Default/Premium)
- Default num_modes
- Cache directory (read-only)
- "Clear all caches" button

**Acceptance:** Settings render; GNINA path entry enables CNN rescoring option in DockingControlPanel.

---

#### Task D3: Export
**Depends on:** C3.
**Action:** Add export buttons:
- Save current pose as SDF
- Save full job (receptor PDBQT + all poses + parameters) as ZIP
- Save screenshot as PNG
- Save interaction fingerprint table as CSV
- Save full docking report as PDF (template with summary, parameters, pose list, top-pose interactions, screenshot)

**Acceptance:** All exports produce valid files openable in the expected applications.

---

#### Task D4: Documentation
**Depends on:** all of A+B+C+D.
**Files:**
- `docs/DOCKING_WORKBENCH_GUIDE.md` — user-facing tutorial with screenshots
- `docs/DOCKING_WORKBENCH_ARCHITECTURE.md` — developer architecture overview
- `docs/DOCKING_WORKBENCH_NOTES.md` — agent deviation log

**Acceptance:** All documents committed.

---

#### Task D5: Smoke and integration tests
**Depends on:** all.
**Files:**
- `python/edeon_docking/tests/test_workbench_smoke.py` — backend service tests
- `tests/integration/test_docking_workbench_e2e.py` — full pipeline test:
   1. Load ALS preset
   2. Verify auto-prep + auto-pocket + auto-box
   3. Set ligand to imidacloprid
   4. Run docking
   5. Verify ≥ 5 poses with sensible scores
   6. Verify interaction fingerprint contains expected contacts
   7. Save to history; reload; verify identical result

**Acceptance:** Both test files pass.

---

#### Task D6: CI workflow
**Depends on:** D5.
**File:** `.github/workflows/docking_workbench_smoke.yml`
**Action:** Multi-platform smoke (Linux/macOS/Windows) running backend tests. Frontend E2E test optional (gated on Playwright availability).

**Acceptance:** CI passes on all platforms.

---

## 7. Acceptance Criteria for Workbench Complete

The Docking Workbench is complete when:

1. **Backend services**:
   - Receptor service handles all 4 sources, prepares with HET classification, caches
   - Ligand service prepares SMILES → PDBQT with caching
   - Pocket service detects via cocrystal and fpocket modes
   - Docking service runs Vina end-to-end with cancellation
   - Analysis service produces interaction fingerprints
   - Job history persists across app restarts

2. **Frontend**:
   - Three-pane layout renders cleanly
   - Receptor selector loads from all 4 sources
   - HET atom list shows correctly; toggling triggers re-preparation
   - Pocket detection (auto or manual) sets box
   - Box overlay renders and updates in real-time
   - Ligand panel handles all 3 input modes
   - Docking runs with progress, cancel works
   - Pose list with score badges; clicking loads in viewer
   - Interaction fingerprint displays per pose
   - Distance measurement tool works
   - Viewer controls function (representations, screenshot)
   - Job history shows and reloads jobs

3. **Auto-progression**: selecting a preset auto-prepares, auto-detects, auto-sets box within 2 seconds.

4. **Score caveats** visible on every score display.

5. **Cross-platform**: works on Linux, macOS, Windows. CI smoke passes.

6. **Cache invalidation**: changing HET, changing receptor source, changing ligand SMILES correctly invalidates downstream cached state.

7. **No fake-docking remnants**: the previous "conformer-in-viewport" code path is removed.

8. **Documentation** complete: user guide, architecture doc, deviation log.

---

## 8. Out of Scope

Explicitly **do not**:

- Implement covalent docking
- Implement flexible sidechain docking (Vina supports it; defer to v2)
- Implement multiple-receptor docking (one receptor per session)
- Implement true MD-based ensemble docking
- Add ligand drawing tool (ChemDraw-like)
- Implement multi-ligand batch docking (deferred to v2)
- Add target-target comparison features (also v2)
- Integrate non-AutoDock engines beyond Vina + optional GNINA
- Replace NGL.js with a different viewer
- Train any ML scoring functions
- Modify Phase 0–6 backends or curated datasets

---

## 9. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Vina binary fails on novel platform | Bundle multiple versions; document; allow user binary override in Settings |
| ProLIF installation fails (compiles RDKit bindings on some platforms) | Implement RDKit-only fallback for interaction detection; toggle automatically |
| AlphaFold fetch returns low-quality model | Display pLDDT info; warn for models with mean pLDDT < 70; allow user to proceed |
| Pocket detection misses the active site | Always show cocrystal-ligand-based option as primary; fpocket as fallback; manual override available |
| Receptor preparation fails on unusual structures (DNA, glycoproteins) | Detect and present clear error message; do not crash |
| Job cache grows unbounded | Settings includes cache size monitor; "Clear caches" button; automatic eviction of oldest entries when cache > 5GB |
| GNINA path is malicious binary | Sanity-check (run --version with timeout); log invocations; document risk in Settings tooltip |
| Box config slider precision insufficient | Add numeric input alongside sliders for precise values |
| User selects wrong receptor chain (multimer) | Show chain count; allow chain selection per receptor; default to chain A |
| Cancellation race: Vina finishes between cancel-press and signal | Tolerate; report job completed but unflagged for caching |

---

## 10. Conventions

- Random seeds: 42 for ligand conformer generation, Vina seed, RDKit operations
- Caching: SHA-256 hashes; canonical JSON for params hashing (deterministic key ordering)
- Logging: structured JSON to `logs/docking.log` rotated daily
- Subprocess timeouts: receptor prep 60s, ligand prep 30s, fpocket 60s, Vina 300s (configurable)
- Naming: `snake_case` Python, `PascalCase` React, `kebab-case` CLI commands

---

## 11. Future Work (v2+)

Document in `DOCKING_WORKBENCH_NOTES.md` as a "Future Enhancements" section:
- Batch docking (multiple ligands)
- Pose comparison across multiple jobs
- Covalent docking
- Flexible sidechains
- Ensemble docking (multiple receptor conformations)
- Pharmacophore-based scoring/ranking
- Drag-to-resize box handles in 3D viewer
- Surface coloring options (hydrophobicity, electrostatic, conservation)
- ChemDraw-like ligand drawing
- Cloud docking offload (for premium users with API key)
- DiffDock or other ML docking as alternative engine
- Integration with the bioisostere engine (dock each suggested bioisostere and rank by binding score)

---

## 12. Deviation Log

Maintain `docs/DOCKING_WORKBENCH_NOTES.md` recording:
- Vina version actually bundled per platform
- fpocket bundling status per platform
- ProLIF vs. RDKit fallback usage
- Cofactor allowlist additions
- Performance benchmarks: median time for receptor prep, ligand prep, fpocket, Vina (default exhaustiveness) on a reference system
- Cases where AlphaFold model quality was problematic
- Any preset receptor where prep required manual intervention
- Cache hit rates from CI tests

---

**End of Docking Workbench Specification.**
