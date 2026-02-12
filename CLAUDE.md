# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development
```bash
# First time: install system deps, Rust, npm packages
./setup.sh

# Start Tauri dev (Vite frontend + Tauri window together)
npm run tauri dev

# Frontend only (no Tauri window, for UI iteration)
npm run dev

# Production build
npm run tauri build
```

### Rust backend
```bash
cd src-tauri
cargo build                  # compile
cargo test                   # run all tests
cargo check                  # fast type-check without linking
```

### Python engine (standalone test)
```bash
cd python
python3 -m edeon_engine
# Then type JSON-RPC requests:
# {"id": 1, "method": "ping", "params": {}}
# {"id": 1, "method": "compute_properties", "params": {"smiles": ["CC(=O)O"]}}
```

### Python deps
```bash
pip install rdkit-pypi        # sole Python dependency
```

---

## Architecture

Three loosely-coupled layers communicate at runtime:

```
React frontend  ──IPC invoke/events──▶  Rust (Tauri)  ──stdin/stdout JSON-RPC──▶  Python engine
     ▲                                       │
     └──── Zustand stores ◀── Tauri events ──┘
```

### Rust layer (`src-tauri/src/`)

- **`lib.rs`** — app entry point; registers all IPC handlers; manages `AppState { db: Mutex<Connection>, python: Mutex<Option<PythonEngine>> }`
- **`db.rs`** — SQLite init (WAL mode, FK enforcement), schema creation. DB file lives in Tauri's `app_data_dir()`
- **`python.rs`** — `PythonEngine` struct: spawns `python3 -m edeon_engine`, communicates via newline-delimited JSON-RPC over stdin/stdout. Lazily spawned on first workflow run.
- **`models.rs`** — shared `Serialize/Deserialize` structs used by both DB layer and IPC commands. Uses snake_case to match Tauri's serde serialization to TypeScript.
- **`commands/`** — IPC command modules registered in `lib.rs`:
  - `project.rs` — project CRUD + `settings` table (active project)
  - `compound.rs` — paginated compound list, CSV import, add/delete
  - `workflow.rs` — 6-stage pipeline execution (synchronous), progress events, depiction, MCS

The workflow pipeline in `commands/workflow.rs` runs synchronously on the Tauri command thread. Each stage calls `python_engine.send_request(method, params)`, emits a `workflow://progress` Tauri event, then proceeds. Results are written to `workflow_results` table with `stage = "mpo"` as the final record.

### Python engine (`python/edeon_engine/`)

JSON-RPC server over stdin/stdout. `__main__.py` is the dispatcher. Each module (`standardize.py`, `properties.py`, `tice_rules.py`, `selectivity.py`, `resistance.py`, `scoring.py`, `depict.py`, `mcs.py`) exposes a `*_batch()` function taking lists and returning lists. All cheminformatics uses RDKit.

Current science status: `selectivity.py`, `resistance.py`, and `scoring.py` use **heuristic formulas**, not validated QSAR models. No `.pkl` ML model files exist yet.

### React frontend (`src/`)

- View routing via `uiStore.activeView` switch in `App.tsx` — no URL router
- Four Zustand stores: `projectStore`, `compoundStore`, `workflowStore`, `uiStore`
- All Tauri calls go through `invoke<T>()` directly in store actions (no custom hook wrapper)
- Types in `src/types/index.ts` have two layers: mock-era types (camelCase) and backend-synced types (snake_case matching Rust serde)
- `WorkflowView` and `LibraryView` are complete; `KnowledgeView`, `ModelsView`, `ReportsView` are placeholders

### SQLite schema

Five tables: `projects`, `compounds`, `workflows`, `workflow_results`, `settings`. Each compound row stores flat properties (mol_weight, logp, tpsa, hbd, hba, rotatable_bonds) plus a `properties_json` blob. Workflow results store one row per compound with `results_json` containing the full nested result from Python.

---

## Current Phase

**Phase 4 in progress.** Phases 1–3 are complete (shell, SQLite data layer, Python sidecar + 6-stage workflow). Phase 4 targets validated science models. Phase 5 adds knowledge browser and PDF export. Phase 6 is license management and distribution.

The cross-species selectivity feature (`selectivity.py`) is the commercial differentiator — it must reach validated quality before any commercial pitch.
