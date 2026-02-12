# Edeon Desktop — Codebase Analysis

> Auto-generated: 2026-07-13 (updated with full FOSS feature completion)
> Analysis covers the full stack: React/TypeScript frontend (NGL 3D, Recharts, TMAP Canvas), Rust/Tauri v2 backend (rusqlite SQLite with v24 schema migrations, printpdf PDF), Python scientific engine (RDKit, scikit-learn, XGBoost, LightGBM, Optuna, imbalanced-learn, shap, Chemprop, AutoDock Vina/GNINA, CReM, Dimorphite-DL, pkasolver, AiZynthFinder, RAscore, BR-SAScore, SyGma, mmpdb, TMAP, espsim, BoTorch, GPyTorch).

---

## 1. Project Overview

**Edeon Desktop** is a local-first agrochemical lead optimization platform targeting commercial agchem buyers (Syngenta, BASF, FMC, Corteva, etc.). The killer feature is **cross-species selectivity analysis** — estimating how a herbicide candidate affects pest vs. crop vs. pollinator vs. mammal, as well as modeling environmental fate (DT50, Koc, BCF, GUS leaching index), tracking transformation pathways with closed-loop rescoring of metabolites, structure-based docking, generative molecular design, bioisostere replacement, reaction combinatorial enumeration, retrosynthesis gating, matched molecular pair SAR, 2D/3D chemical space cartography, 3D shape/electrostatic screening, Bayesian-optimization active learning, and a full regulatory/verification report suite.

The application processes compound libraries through an expandable multi-stage analytical workflow, supports an extensive interactive QSAR Modeling Studio, provides interactive WebGL 3D molecular visualisation and interactive TMAP chemical-space tree rendering, and displays results in a polished, responsive desktop UI.

### 1.1 Tech Stack

| Layer | Technology |
|-------|-----------|
| Desktop shell | Tauri v2 (Rust) |
| Frontend | React 19 + TypeScript + Zustand + NGL (WebGL 3D) + Recharts + TMAP Canvas |
| Cheminformatics | Python 3.10+ + RDKit (sidecar process) |
| Parallelization | Multi-threaded parallel processing via Python's `joblib` (releasing RDKit GIL) and per-cpu worker configuration |
| Machine Learning | scikit-learn, XGBoost, LightGBM, Optuna, imbalanced-learn, Chemprop (via `edeon_train`), conformal prediction, heteroscedastic regression, BoTorch / GPyTorch Gaussian Process surrogates |
| 3D / Docking | NGL, AutoDock Vina/GNINA, pocket detection, pose clustering, 2D interaction maps |
| Generative design & Reaction Enum | CReM + easydock / crem_dock, scaffold hopping, bioisostere replacement, SMARTS combinatorial reaction enumeration |
| Speciation, Retro & SAR | Dimorphite-DL, pkasolver, AiZynthFinder, RAscore, BR-SAScore, mmpdb + RDKit Matched Molecular Pairs & Free-Wilson regression |
| Cartography & 3D Shape | TMAP (LSH Forest + Minimum Spanning Tree), Faerun, Open3DAlign, `espsim` partial charge similarity |
| Database | SQLite (via rusqlite, bundled, WAL mode + 24 schema migrations) |
| PDF Export | printpdf (native Rust) |
| Build | Vite 6, Cargo 2021 edition |

### 1.2 Key Numbers

| Metric | Value |
|--------|-------|
| TypeScript (`.ts` + `.tsx`) | **~38,200 lines** across **98 files** |
| Rust (`.rs`) | **~7,450 lines** across **27 files** |
| Python (all packages) | **~52,400 lines** across **345 files** |
| Python `edeon_engine` | **13,850 lines** across **85 files** |
| CSS | **~6,435 lines** across **9 files** |
| Rust command modules | 18 command files exposing ~125+ IPC handlers |
| SQLite Migrations | 24 version migrations (v1–v24) |
| Frontend views | 11 primary views |
| Zustand stores | 17 stores |
| Python workflow templates | 8 named workflows (`w1`–`w8`) |
| Curated eco-toxicology endpoints | fish, daphnia, algae, bee (oral/contact), bird, earthworm, rat LD50, skin sensitization, BCF, soil DT50, soil Koc |
| Tier-1 model cards | 9 endpoints with verification/calibration reports |
| Automated Python test suite | **47 passing unit & integration tests** |

---

## 2. Repository Layout

```
Edeon/
├── src/                          # React / TypeScript frontend
│   ├── App.tsx                   # Shell layout & view router
│   ├── main.tsx                  # React root entry
│   ├── views/                    # 11 top-level view components
│   ├── components/               # Domain-specific UI components
│   │   ├── al/                   # Active learning UI components (ActiveLearningPanel)
│   │   ├── bioisostere/          # Bioisostere carousel components
│   │   ├── cartography/          # Chemical space cartography canvas (TmapCanvas)
│   │   ├── design/               # De novo workbench panels (AnalogGrid, ReactionEnumPanel)
│   │   ├── docking/              # Docking setup dialogs
│   │   ├── fate/                 # Transformation pathway trees & fate cards
│   │   ├── knowledge/            # QA chat panel
│   │   ├── layout/               # Header, Sidebar, Inspector, StatusBar
│   │   ├── library/              # Add/Import compound dialogs
│   │   ├── models/               # Model cards, featurizer panels, Arena displays
│   │   ├── regulatory/           # Scorecards & registration risk panels
│   │   ├── sar/                  # MMP transform table & Free-Wilson panels
│   │   ├── shape/                # 3D shape & electrostatic similarity panels
│   │   ├── shared/               # Risk badges, empty states, progress bars
│   │   ├── uq/                   # Interval bars & UQ badges
│   │   ├── viewer3d/             # NGL WebGL outliner & controllers
│   │   └── workflow/             # Stage connectors, results tables, selectivity charts
│   ├── store/                    # 17 Zustand stores
│   ├── hooks/                    # Global React hooks
│   ├── shell/                    # App-level UI shells/overlays
│   ├── styles/                   # CSS tokens, themes, layout, components
│   ├── types/                    # Shared TypeScript types
│   ├── data/                     # Mock/static data + reaction SMARTS templates
│   └── content/                  # Onboarding + help content
├── src-tauri/                    # Rust/Tauri backend
│   ├── src/
│   │   ├── lib.rs                # Tauri builder + AppState + command registration
│   │   ├── main.rs               # Binary entry point
│   │   ├── db.rs                 # SQLite init + 24 schema migrations
│   │   ├── python.rs             # Python sidecar spawn + JSON-RPC manager
│   │   ├── models.rs             # Shared data model DTOs
│   │   ├── commands/             # 18 IPC command modules (project, compound, workflow, sar, cartography, shape, active_learning, retro, etc.)
│   │   └── models/               # Internal preference/proxy/type structs
│   ├── Cargo.toml                # Rust dependencies
│   ├── tauri.conf.json           # Tauri configuration
│   ├── resources/                # Bundled binaries (Vina cross-platform)
│   └── capabilities/             # Tauri capability definitions
├── python/                       # Python scientific ecosystem
│   ├── edeon_engine/             # Primary JSON-RPC sidecar
│   ├── edeon_data/               # Data acquisition + curation
│   ├── edeon_models/             # Model serving registry + backends
│   ├── edeon_train/              # Training pipeline + Chemprop wrapper
│   ├── edeon_docking/            # Vina/GNINA docking services
│   ├── edeon_generation/         # CReM / easydock generative design
│   ├── edeon_bioisostere/        # Bioisostere replacement library
│   ├── edeon_knowledge/          # Knowledge Hub RAG + embeddings
│   ├── edeon_app_meta/           # App metadata, citations, first-launch state
│   ├── edeon_retro/              # Retrosynthesis & synthesis feasibility gating
│   ├── edeon_sar/                # Matched Molecular Pairs & Free-Wilson SAR engine
│   ├── edeon_cartography/        # TMAP LSH Forest + MST cartography engine
│   ├── edeon_shape/              # Open3DAlign + espsim 3D shape similarity engine
│   ├── edeon_active_learning/    # Gaussian Process BO surrogate & acquisition engine
│   ├── pyproject.toml            # Package metadata & optional extras
│   └── requirements.txt          # Runtime dependencies
├── data/                         # Curated datasets, checkpoints, demos, docking cache, reactions.json
├── tests/                        # Integration + regression + verification tests
├── scripts/                      # Build/prepare/verification helper scripts
└── docs/                         # Design, implementation, model cards, licensing audits, verification
```

---

## 3. Frontend (React + TypeScript)

### 3.1 Entry Point: `index.html` → `src/main.tsx` → `App.tsx`

`App.tsx` renders the shell layout as a CSS Grid:
- **Header** (48px)
- **Sidebar** (220px left)
- **Main Content** (flex 1 center)
- **Inspector** (260px right, collapsible, hidden automatically in Settings, 3D/viewer3d, and Verification Report views)
- **StatusBar** (24px bottom)

View routing is done via `useUIStore.activeView` and a switch statement in `App.tsx`.

### 3.2 State Management: Zustand (17 stores)

| Store | File | Responsibility |
|-------|------|----------------|
| `projectStore` | `src/store/projectStore.ts` | Project CRUD synced with Tauri IPC |
| `compoundStore` | `src/store/compoundStore.ts` | Compound table with pagination/search/sort; batch CSV/SDF import |
| `workflowStore` | `src/store/workflowStore.ts` | Multi-stage workflow execution, progress streaming, chunking |
| `uiStore` | `src/store/uiStore.ts` | Shared UI states, selected compound details, MCS, export to De Novo |
| `settingsStore` | `src/store/settingsStore.ts` | Theme, preferences, DB dir, Python engine diagnostics |
| `modelStore` | `src/store/modelStore.ts` | QSAR Modeling Studio state, training jobs, Arena |
| `knowledgeStore` | `src/store/knowledgeStore.ts` | Offline DB searches, QA conversations |
| `fateStore` | `src/store/fateStore.ts` | Environmental fate endpoints, soil microbial metabolism, liabilities |
| `designStore` | `src/store/designStore.ts` | Generative design, CReM, combinatorial reaction enumeration |
| `regulatoryStore` | `src/store/regulatoryStore.ts` | Registration risk assessments, scorecards |
| `retroStore` | `src/store/retroStore.ts` | Retrosynthesis route search, synthesizability gating, stock imports |
| `sarStore` | `src/store/sarStore.ts` | Matched Molecular Pair indexing, selectivity transforms, Free-Wilson regression |
| `cartographyStore` | `src/store/cartographyStore.ts` | TMAP LSH MST tree rendering, node coordinates, cluster selection |
| `shapeStore` | `src/store/shapeStore.ts` | 3D shape alignment, electrostatic field calculation, ComboScore ranking |
| `activeLearningStore` | `src/store/activeLearningStore.ts` | Bayesian optimization, GP surrogate modeling, EI/UCB/TS batch selection |
| `tourStore` | `src/store/tourStore.ts` | Onboarding tour progress |
| `shortcutsRegistry` | `src/store/shortcutsRegistry.ts` | Command-palette & keyboard shortcut registry |

---

## 4. Tauri Backend (Rust)

### 4.1 SQLite Schema Migrations (`src-tauri/src/db.rs`)

SQLite database running in WAL journal mode with 24 incremental migrations:

- `v1`–`v17`: Projects, compounds, workflows, results, settings, saved_models, arena_runs, transformation_products, docking_jobs, generation_jobs, knowledge_conversations.
- `v18`: `synthesis_routes`, `stock_reagents` (Retrosynthesis Feasibility Gating).
- `v19`: `job_kind` column in `generation_jobs` (Combinatorial Reaction Enumeration).
- `v20`: `source` & `liability_flag` in `transformation_products` (Soil Microbial Metabolism Expansion).
- `v21`: `mmp_transforms`, `free_wilson_models` (Matched Molecular Pairs & Free-Wilson SAR).
- `v22`: `tmap_layouts` (Chemical Space Cartography).
- `v23`: `shape_screenings` (3D Shape & Electrostatic Similarity).
- `v24`: `active_learning_campaigns` (Bayesian-Optimization Active-Learning Loop).

### 4.2 Command Modules (18 total)

Exposes ~125+ IPC handlers across:
`project`, `compound`, `workflow`, `models`, `knowledge`, `settings`, `export`, `design`, `docking`, `fate`, `regulatory`, `reference`, `app_meta`, `speciation`, `mobility`, `retro`, `sar`, `cartography`, `shape`, `active_learning`.

---

## 5. Scientific Features & Roadmap Completion Summary

| Phase | Feature ID & Description | Core Algorithms & Libraries | Status |
|-------|--------------------------|-----------------------------|--------|
| **Phase G** | **G1: Retrosynthesis Feasibility Gating** | BR-SAScore, AiZynthFinder, RAscore | ✅ **Completed & Verified** |
| **Phase I** | **I9: Reaction Combinatorial Enumeration** | Reaction SMARTS templates (Amide, Suzuki, SNAr, etc.) | ✅ **Completed & Verified** |
| **Phase I** | **I6: Environmental Metabolism Expansion** | Soil microbial & photolysis SMIRKS rules | ✅ **Completed & Verified** |
| **Phase H** | **H2: Matched Molecular Pairs & Free-Wilson SAR** | `mmpdb` single-bond cuts, selectivity delta, Ridge regression | ✅ **Completed & Verified** |
| **Phase J** | **J7: Chemical-Space Cartography** | TMAP (LSH Forest + Minimum Spanning Tree), Faerun canvas | ✅ **Completed & Verified** |
| **Phase I** | **I4: 3D Shape & Electrostatic Similarity** | Open3DAlign ($S_{\text{shape}}$) + `espsim` ($S_{\text{electrostatic}}$) ComboScore | ✅ **Completed & Verified** |
| **Phase K** | **K10: Bayesian Active-Learning Loop** | BoTorch / GPyTorch GP surrogates, EI / UCB / TS acquisition | ✅ **Completed & Verified** |

---

## 6. Testing & Validation

All scientific engines and Rust command bindings are verified via unit and integration tests:

- **Python Pytest Suite**: **47/47 passing tests** across `test_speciation.py`, `test_mobility.py`, `test_retro.py`, `test_reaction_enum.py`, `test_env_metabolism.py`, `test_sar_mmp.py`, `test_tmap_cartography.py`, `test_shape_screening.py`, `test_active_learning.py`, `test_bottleneck.py`, `test_journal_payload.py`, `test_decision_journal.py`.
- **Rust Compiler Verification**: `cargo check --no-default-features` passes with **0 errors and 0 warnings**.
