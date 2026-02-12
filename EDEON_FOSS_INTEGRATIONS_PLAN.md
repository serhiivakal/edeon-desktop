# Edeon Desktop — Implementation Plan: FOSS Tool Integrations (Phases G–K)

> Target executor: coding agent (Claude Code / equivalent), grounded against the current Edeon codebase.
> Scope: 8 features. Excludes the previously-discussed xtb/GFN2-xTB descriptor item by request.
> Author intent: each feature spec below is self-contained and can be lifted out as a standalone agent prompt.

---

## 0. How to use this document (agent instructions)

1. **Read Section 1 (Global context) before any feature.** It defines the IPC contract, error envelope, install/extras strategy, and UQ-propagation rules every feature must respect.
2. **Respect the dependency gates in Section 2.** Do not start a gated feature until its upstream gate's acceptance criteria pass.
3. **Each feature section is structured identically:** Context → License & deps → Python layout + JSON-RPC → Rust commands → SQLite migration → Zustand deltas → UI surface → Acceptance criteria → Ordered task list.
4. **License-audit tasks are real tasks, not commentary.** Where a license is marked `VERIFY`, the audit task is a hard gate: implementation behind that gate must not be merged into the default build until the audit task is signed off. Place audit findings in `docs/PHASE*_LICENSING_AUDIT.md` following the existing Phase 6 precedent.
5. **Heavy dependencies are optional extras**, never added to the base install (see §1.2). The base app must build, launch, and pass the existing test suite with none of these extras present.
6. **Every new JSON-RPC handler must be registered** in `edeon_engine/__main__.py`'s dispatch table (or the owning package's `ipc_handlers.py` / `ipc/server.py`), every Rust command in `src-tauri/src/lib.rs`'s `invoke_handler`, and every capability in `src-tauri/capabilities/`.
7. **Do not regress the "base build has zero heavy deps" invariant.** If a feature's Python module is imported at sidecar startup, its heavy imports must be lazy (import inside the handler, not at module top level), so a missing extra degrades to a clean `feature_unavailable` error rather than crashing the sidecar.

---

## 1. Global context

### 1.1 Architecture recap (integration points this plan touches)

- **Sidecar dispatch:** `python/edeon_engine/__main__.py` reads newline-delimited JSON-RPC from stdin, dispatches by `method`, writes JSON to stdout. Long-running work streams `[TRIAL_RESULT]`-style progress lines consumed by `src-tauri/src/python.rs::send_request_with_app`, which re-emits Tauri events.
- **Rust IPC:** commands live in `src-tauri/src/commands/*.rs`, are registered in `lib.rs`, call `state.get_python_engine()?.send_request(method, params)` (or the streaming variant), and return DTOs from `models.rs`.
- **Frontend:** Zustand stores in `src/store/*.ts` call `invoke('<command>', {...})`; views in `src/views/`, components in `src/components/<domain>/`.
- **DB:** `src-tauri/src/db.rs` runs incremental migrations on a WAL-mode SQLite connection. Add new migrations append-only with a bumped `user_version`.
- **UQ/AD contract:** every prediction surfaced in the UI carries `{value, interval?, ad_status, tier}` and renders through `UqBadge`/`IntervalBar`/`ADWarning`. New predictive features MUST conform.

### 1.2 Dependency & install strategy

Add a layered extras structure to `python/pyproject.toml`. Base install stays lean; heavy/optional scientific stacks gate behind extras and a runtime capability probe.

```toml
[project.optional-dependencies]
# light extras — acceptable to include in default desktop bundle
speciation = ["dimorphite-dl"]
shape      = ["espsim"]            # RDKit O3A already present via rdkit
sar        = ["mmpdb"]            # VERIFY license before default-bundling
# heavy extras — NEVER in default bundle; user opt-in install
retro      = ["aizynthfinder", "onnxruntime"]   # + RAscore (separate vcs install)
cartography= ["tmap", "faerun"]
optimize   = ["botorch", "gpytorch", "torch"]
```

**Capability probe.** Add `edeon_app_meta/system_status.py::feature_capabilities()` returning a map `{feature: {"available": bool, "missing": [pkg,...]}}`. The frontend reads this once at startup (extend the existing first-launch/system-info flow) and disables/relabels UI affordances for unavailable features instead of letting calls fail opaquely. Every JSON-RPC handler for a heavy feature returns a structured `feature_unavailable` error (see §1.3) when its import probe fails.

**Sidecar safety.** Heavy imports are performed lazily inside handlers, never at module import time. Module top-level imports are restricted to stdlib + rdkit + numpy.

### 1.3 Error envelope (uniform across new handlers)

```json
{ "ok": false,
  "error": { "code": "feature_unavailable | invalid_input | compute_error | license_gated",
             "message": "human-readable",
             "feature": "retro",
             "missing": ["aizynthfinder"] } }
```

Rust maps `feature_unavailable`/`license_gated` to a typed error the frontend renders as a non-blocking banner (reuse `EmptyState` + a "How to enable" link), not a crash toast.

### 1.4 License posture summary

| # | Feature | Primary FOSS tool | Stated license | Posture | Audit gate |
|---|---------|-------------------|----------------|---------|------------|
| 1 | Retrosynthesis + synth gating | AiZynthFinder; RAscore | MIT (both, expected) | Bundle-safe if confirmed | `G1-AUDIT` |
| 2 | MMP + Free-Wilson | mmpdb; RDKit | `VERIFY` (mmpdb) / BSD (RDKit) | Hold default-bundle until verified | `H2-AUDIT` |
| 4 | Shape + ESP similarity | espsim; RDKit O3A | MIT / BSD | Bundle-safe | `I4-AUDIT` |
| 5 | pH speciation | Dimorphite-DL; (pkasolver) | Apache-2.0 / `VERIFY` | Dimorphite bundle-safe; pkasolver optional | `G5-AUDIT` |
| 6 | Env/microbial metabolism | curated SMIRKS (own); BioTransformer = **reference only** | own work / **restrictive** | **Do NOT bundle BioTransformer**; ship own rules | `I6-AUDIT` |
| 7 | Chemical-space cartography | TMAP; Faerun | MIT | Bundle-safe (heavy) | `J7-AUDIT` |
| 8 | Mechanistic systemic mobility | Kleier / Bromilow models | literature, no code license | Bundle-safe (own implementation) | none |
| 10| Bayesian-opt active learning | BoTorch / GPyTorch | MIT | Bundle-safe (heavy) | `K10-AUDIT` |

> Numbering preserves the ideation list (3 omitted). Treat every `VERIFY`/restrictive row's audit task as a blocking gate per §0.4.

---

## 2. Dependency graph & phasing

```
        ┌─────────────────────────────────────────────┐
Phase G │  (G5) Speciation primitive  ──┐              │  foundational
        │  (G1) Retro engine (independent)             │
        └───────────────┬───────────────┬─────────────┘
                        │               │
Phase H │  (H2) MMP/Free-Wilson         │              │  SAR + synth "wow"
        └───────────────┼───────────────┼─────────────┘
                        │               │
Phase I │  (I9) Reaction enum ◀── needs G1                          design expansion
        │  (I4) Shape/ESP (independent)
        │  (I6) Metabolism ext ◀── needs G5
        └───────────────┬─────────────────────────────┘
                        │
Phase J │  (J8) Systemic mobility ◀── needs G5                      mechanistic + viz
        │  (J7) TMAP cartography (independent)
        └───────────────┬─────────────────────────────┘
                        │
Phase K │  (K10) Bayesian-opt loop ◀── benefits from G1,H2 outputs as objectives
        └─────────────────────────────────────────────┘
```

**Gates (hard):**
- `GATE-G5`: speciation `speciation.enumerate` returns deterministic microspecies + dominant species at pH for the 5 demo compounds → unblocks I6, J8, and pH-aware docking ligand prep.
- `GATE-G1`: `retro.route_search` returns a route tree + feasibility score for ≥3 demo compounds → unblocks I9; feeds K10 objective.
- `GATE-H2`: MMP index builds over a demo library and `sar.predict_transform` returns a property delta → unblocks the SAR panel and K10 "MMP-aware" proposals.
- `GATE-AUDIT`: each `*-AUDIT` task signed off before its feature merges to the default build.

---

## 3. Phase G — Foundational chemistry primitives

### 3.1 Feature G5 — pH-dependent speciation

**Context.** Soil pH (≈4–8) governs ionization, which governs Koc, leaching (GUS), and phloem mobility. Edeon currently predicts on the neutral/input form. This feature computes pKa-resolved microspecies and the dominant species at a user-selected pH, then feeds the *correct* protonation state into fate, mobility (J8), and docking ligand prep. It is a shared primitive: ship it first.

**License & deps.** Dimorphite-DL (Apache-2.0, enumerates protonation states across a pH window). Optional pkasolver (MIT `VERIFY`) for numeric pKa values; if absent, fall back to Dimorphite-DL's empirical enumeration + a coarse acid/base classification. Audit task `G5-AUDIT`.

**Python layout.** New module group `edeon_engine/speciation/`:
- `enumerate.py` — Dimorphite-DL wrapper: enumerate protonation states over `[ph_min, ph_max]`.
- `microspecies.py` — build microspecies set, assign fractional populations via Henderson–Hasselbalch from pKa set; select dominant species at target pH.
- `pka.py` — optional pkasolver bridge with empirical fallback.
- `cache.py` — read/write `speciation_cache`.

**JSON-RPC methods** (registered in `__main__.py`):

```
speciation.enumerate
  params:  { "smiles": str, "ph_min": 4.0, "ph_max": 8.0, "ph_target": 6.5,
             "max_variants": 8 }
  returns: { "ok": true,
             "input_inchikey": str,
             "microspecies": [ { "smiles": str, "charge": int,
                                 "fraction_at_target": float,
                                 "dominant": bool } ],
             "pka_values": [float] | null,
             "method": "pkasolver | dimorphite_empirical" }

speciation.dominant_at_ph
  params:  { "smiles": str, "ph": 6.5 }
  returns: { "ok": true, "smiles": str, "charge": int, "fraction": float }

speciation.profile_curve
  params:  { "smiles": str, "ph_min": 4.0, "ph_max": 9.0, "steps": 26 }
  returns: { "ok": true, "series": [ { "ph": float,
              "species": [ {"smiles": str, "fraction": float} ] } ] }
```

**Rust commands** (`src-tauri/src/commands/speciation.rs`, new):
- `speciation_enumerate(smiles, ph_min, ph_max, ph_target, max_variants) -> SpeciationResult`
- `speciation_dominant_at_ph(smiles, ph) -> DominantSpecies`
- `speciation_profile_curve(smiles, ph_min, ph_max, steps) -> SpeciationCurve`

Register module in `lib.rs`; add DTOs to `models.rs`; add capability in `capabilities/`.

**SQLite migration** (bump `user_version`):
```sql
CREATE TABLE IF NOT EXISTS speciation_cache (
  input_inchikey TEXT NOT NULL,
  ph_target      REAL NOT NULL,
  payload_json   TEXT NOT NULL,   -- full SpeciationResult
  created_at     TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (input_inchikey, ph_target)
);
```

**Zustand deltas.** Extend `fateStore`:
- state: `phTarget: number` (default 6.5), `speciation: Record<inchikey, SpeciationResult>`, `speciationCurve?`.
- actions: `setPhTarget(ph)`, `loadSpeciation(smiles)`, `loadSpeciationCurve(smiles)`.
- On `phTarget` change, fate cards (Koc/GUS) recompute against the dominant species (wire in I-phase fate work; in G just expose the value).

**UI surface.**
- `src/components/speciation/SpeciesBadge.tsx` — charge + dominant-species pill, rendered in the `Inspector` properties card.
- `src/components/speciation/SpeciationCurve.tsx` — Recharts area chart of fractional population vs pH, surfaced in `FateView` behind a "Speciation" tab.
- Global pH slider control in `FateView` header bound to `fateStore.phTarget`.

**Acceptance criteria.**
- For the 5 demo compounds, `speciation.enumerate` returns ≥1 microspecies with `dominant=true` summing fractions ≈1.0 (±0.02).
- pH slider in `FateView` updates `SpeciesBadge` and `SpeciationCurve` reactively.
- With `dimorphite-dl` absent, handler returns `feature_unavailable` (not a crash); UI shows the enable banner.
- Results cached: a repeat call for same `(inchikey, ph_target)` hits `speciation_cache`.

**Task list.**
1. `G5-AUDIT` — confirm Dimorphite-DL Apache-2.0 + pkasolver license; record in `docs/PHASEG_LICENSING_AUDIT.md`. *(gate)*
2. Add `speciation` + `pkasolver`(optional) extras to `pyproject.toml`; capability probe entry.
3. Implement `edeon_engine/speciation/*`; lazy imports.
4. Register 3 JSON-RPC handlers + unit tests over demo compounds (`python/edeon_engine/tests/test_speciation.py`).
5. Add migration + `speciation_cache` read/write.
6. Rust `speciation.rs` commands + DTOs + `lib.rs` registration + capability.
7. `fateStore` deltas; `SpeciesBadge`, `SpeciationCurve`, pH slider.
8. Integration test: `tests/integration/test_speciation_flow.py`. **Close `GATE-G5`.**

---

### 3.2 Feature G1 — Retrosynthesis + synthesizability gating

**Context.** Closes the generative loop: CReM/crem_dock produce valid-but-often-unmakeable molecules with no synthesizability filter today. Add a fast learned proxy (RAscore) as a cheap gate, then full template-based MCTS route search (AiZynthFinder) on survivors. Surface route depth, building-block availability, and a feasibility score as a ranking column in `AnalogGrid` and `ResultsTable`. For agrochem, synthesis cost is frequently the kill criterion.

**License & deps.** AiZynthFinder (MIT expected — confirm), RAscore (MolecularAI, MIT expected — confirm), `onnxruntime` for portable policy-model inference. Heavy extra `retro`; never in base bundle. Audit task `G1-AUDIT`.

**Data assets** (under `data/retro/`, downloaded on first opt-in, not committed):
- `policy/` — expansion + filter policy models (ONNX-converted).
- `templates/` — reaction template library.
- `stock/agrochem_stock.hdf5` — curated building-block catalog biased toward common, cheap reagents (ship a small default; allow user-supplied stock files).
- `config.yml` — AiZynthFinder run config templated by the wrapper.

**Python layout.** New package `python/edeon_retro/`:
- `rascore.py` — RAscore fast gate (single + batch).
- `aizynth_runner.py` — AiZynthFinder wrapper; loads config, runs `TreeSearch`, extracts top route, computes feasibility metrics (solved?, route depth, #steps, fraction of leaves in stock).
- `feasibility.py` — combine RAscore + route metrics → composite `feasibility_score ∈ [0,1]` + `tier` (`green/amber/red`).
- `stock.py` — build/load building-block stock; user stock import.
- `ipc_handlers.py` — JSON-RPC handlers (heavy imports lazy).
- `schema.py` — typed result models.

**JSON-RPC methods:**

```
retro.rascore                       (fast, synchronous, batchable)
  params:  { "smiles": [str] }
  returns: { "ok": true, "scores": [ {"smiles": str, "ra_score": float} ] }

retro.route_search                  (slow → streams progress via app_handle)
  params:  { "smiles": str, "time_limit_s": 60, "max_routes": 5,
             "stock_id": "agrochem_default" }
  emits:   event "retro://progress" { "smiles": str, "iterations": int,
                                      "best_solved": bool }
  returns: { "ok": true,
             "solved": bool,
             "feasibility_score": float, "tier": "green|amber|red",
             "n_steps": int, "route_depth": int,
             "leaves_in_stock_frac": float,
             "route_tree": { ...nested reaction/molecule nodes... },
             "building_blocks": [ {"smiles": str, "in_stock": bool} ] }

retro.gate_batch                    (RAscore gate → optional route_search on survivors)
  params:  { "smiles": [str], "ra_threshold": 0.5, "route_search_top_k": 10,
             "time_limit_s": 30 }
  returns: { "ok": true, "results": [ { "smiles": str, "ra_score": float,
             "feasibility_score": float|null, "tier": str } ] }

retro.import_stock
  params:  { "path": str, "name": str }            # SMILES/SDF → hdf5 stock
  returns: { "ok": true, "stock_id": str, "n_blocks": int }
```

**Rust commands** (`commands/retro.rs`, new):
- `retro_rascore(smiles: Vec<String>) -> Vec<RaScore>`
- `retro_route_search(smiles, time_limit_s, max_routes, stock_id, app: AppHandle) -> RetroRoute` (streaming variant)
- `retro_gate_batch(...) -> Vec<RetroGateResult>`
- `retro_import_stock(path, name) -> StockRef`
- `retro_list_stocks() -> Vec<StockRef>`

**SQLite migration:**
```sql
CREATE TABLE IF NOT EXISTS retro_routes (
  inchikey       TEXT NOT NULL,
  stock_id       TEXT NOT NULL,
  params_hash    TEXT NOT NULL,   -- hash of search params
  solved         INTEGER NOT NULL,
  feasibility    REAL,
  tier           TEXT,
  route_json     TEXT NOT NULL,
  created_at     TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (inchikey, stock_id, params_hash)
);
CREATE TABLE IF NOT EXISTS retro_stocks (
  stock_id TEXT PRIMARY KEY,
  name     TEXT NOT NULL,
  n_blocks INTEGER NOT NULL,
  path     TEXT NOT NULL
);
```

**Zustand deltas.** New `src/store/retroStore.ts`:
- state: `routes: Record<inchikey, RetroRoute>`, `gating: Record<inchikey, RetroGateResult>`, `stocks: StockRef[]`, `activeStockId`, `searchProgress`.
- actions: `rascore(smiles[])`, `routeSearch(smiles)`, `gateBatch(smiles[], opts)`, `importStock(path,name)`, listen to `retro://progress`.
Extend `designStore`: when a CReM batch completes, auto-call `retro.gate_batch` and attach `feasibility_score/tier` to each analog. Add a `synthesizable_only` toggle that filters `AnalogGrid`.

**UI surface.**
- `src/components/retro/RouteTree.tsx` — collapsible retrosynthetic tree (reuse the Bezier-curve SVG approach from `PathwayTree.tsx`); leaf nodes flagged in-stock/out-of-stock.
- `src/components/retro/FeasibilityBadge.tsx` — green/amber/red pill with score; embed in `AnalogGrid` and `ResultsTable` as a "Makeability" column.
- Route panel opens from `GenerationWorkbenchView` and from a "Retrosynthesis" action in `CompoundDetailModal`.
- Stock manager in `SettingsView` (import/list user stock files).

**Acceptance criteria.**
- `retro.rascore` returns scores for a 100-compound batch in <2 s (proxy is fast).
- `retro.route_search` on ≥3 demo compounds returns `solved=true` with a non-empty `route_tree` and `leaves_in_stock_frac` populated; progress events arrive during search.
- `AnalogGrid` shows a sortable Makeability column; `synthesizable_only` filter hides `tier=red`.
- With `retro` extra absent: capability probe reports unavailable, UI disables retro actions with the enable banner, sidecar does not crash.
- Results cached in `retro_routes` by `(inchikey, stock_id, params_hash)`.

**Task list.**
1. `G1-AUDIT` — confirm AiZynthFinder + RAscore licenses; model/template redistribution terms; record in audit doc. *(gate)*
2. `retro` extra + capability probe + first-run asset download helper in `scripts/`.
3. `edeon_retro/rascore.py` + `retro.rascore` handler + tests.
4. `aizynth_runner.py` + `feasibility.py` + `retro.route_search` (streaming) + `retro.gate_batch`.
5. `stock.py` + default `agrochem_stock.hdf5` builder + `retro.import_stock`.
6. Migration + caching.
7. Rust `retro.rs` (incl. streaming command) + DTOs + registration + capability.
8. `retroStore` + `designStore` integration + `RouteTree`, `FeasibilityBadge`, stock manager.
9. Integration test `tests/integration/test_retro_gate.py`. **Close `GATE-G1`.**

---

## 4. Phase H — SAR & synthesizability "wow"

### 4.1 Feature H2 — Matched molecular pairs + Free-Wilson SAR

**Context.** mmpdb builds a transformation database from the user's *own* curated libraries and predicts property deltas for a substitution — rare in a GUI. Surface "transformations seen in your data and their typical effect" on any compound, and specifically rank MMP transforms that *widen* the pest/pollinator selectivity gap. Add classic Free-Wilson regression for congeneric series (R-group contribution panel).

**License & deps.** mmpdb (`VERIFY` — do not default-bundle until cleared), RDKit (BSD). Audit task `H2-AUDIT`. Until cleared, ship behind the `sar` extra and the capability gate.

**Python layout.** New package `python/edeon_sar/`:
- `mmp_index.py` — fragment + index a compound set into an mmpdb database (one DB file per index, stored under `data/sar/<index_id>.mmpdb`).
- `mmp_predict.py` — given a query compound + property, return observed transforms and predicted deltas with N and stddev.
- `selectivity_transforms.py` — filter/rank transforms by their effect on the selectivity window (uses existing `selectivity.py` endpoints as the property axes).
- `free_wilson.py` — RDKit R-group decomposition over a congeneric series → linear contribution model (statsmodels/sklearn) with per-substituent coefficients + CIs.
- `ipc_handlers.py`, `schema.py`.

**JSON-RPC methods:**

```
sar.mmp_build_index             (slow → streams progress)
  params:  { "compounds": [ {"smiles": str, "id": str,
                             "properties": {prop: value} } ],
             "index_name": str }
  returns: { "ok": true, "index_id": str, "n_pairs": int, "n_transforms": int }

sar.mmp_predict
  params:  { "index_id": str, "smiles": str, "property": "dt50|bee_oral|...",
             "max_results": 25 }
  returns: { "ok": true, "predictions": [ { "transform": str,
             "from_frag": str, "to_frag": str, "product_smiles": str,
             "delta_mean": float, "delta_std": float, "n": int } ] }

sar.selectivity_transforms
  params:  { "index_id": str, "smiles": str,
             "pest_endpoint": str, "nontarget_endpoint": str,
             "max_results": 25 }
  returns: { "ok": true, "transforms": [ { "product_smiles": str,
             "pest_delta": float, "nontarget_delta": float,
             "window_gain": float } ] }   # window_gain = improvement in gap

sar.free_wilson
  params:  { "series": [ {"smiles": str, "activity": float} ],
             "core_smarts": str|null }
  returns: { "ok": true, "r2": float, "q2": float,
             "contributions": [ { "position": int, "substituent": str,
                                  "coef": float, "ci_low": float, "ci_high": float } ],
             "n_compounds": int }
```

**Rust commands** (`commands/sar.rs`, new): `sar_mmp_build_index` (streaming), `sar_mmp_predict`, `sar_selectivity_transforms`, `sar_free_wilson`, `sar_list_indexes`, `sar_delete_index`.

**SQLite migration** (metadata only — mmpdb manages its own DB files):
```sql
CREATE TABLE IF NOT EXISTS mmp_indexes (
  index_id   TEXT PRIMARY KEY,
  name       TEXT NOT NULL,
  db_path    TEXT NOT NULL,
  n_pairs    INTEGER, n_transforms INTEGER,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**Zustand deltas.** New `src/store/sarStore.ts`: `indexes`, `predictions`, `selectivityTransforms`, `freeWilson`; actions `buildIndex`, `predict`, `selectivityTransforms`, `freeWilson`, `deleteIndex`.

**UI surface.**
- New tab in `ModelsView` (or a sibling view `SarView.tsx`) — "SAR / MMP".
- `src/components/sar/TransformTable.tsx` — sortable transforms with Δ + N + stddev; "apply transform → register product" action that pipes `product_smiles` into the library.
- `src/components/sar/SelectivityTransformChart.tsx` — Recharts quadrant (pest Δ vs non-target Δ); upper-left quadrant = window-widening, highlighted.
- `src/components/sar/FreeWilsonPanel.tsx` — bar chart of substituent contributions with CI whiskers.
- Index manager (build/delete) reachable from `SettingsView` or the SAR view header.

**Acceptance criteria.**
- Building an index over a ≥50-compound demo set yields `n_transforms > 0`; metadata row written.
- `sar.mmp_predict` for a query in-domain returns ≥1 transform with `n ≥ 2`.
- `sar.selectivity_transforms` returns transforms sorted by `window_gain` desc; the quadrant chart highlights window-widening transforms.
- `sar.free_wilson` on a congeneric demo series returns `r2`, `q2`, and per-substituent coefficients with CIs.
- "Apply transform" registers the product compound in the library and it appears in `LibraryView`.
- `sar` extra absent → capability gate, no crash.

**Task list.**
1. `H2-AUDIT` — mmpdb license + redistribution; if unfavorable, scope a pure-RDKit MMP fallback (fragment-on-bonds + pair-mining) and re-plan. *(gate)*
2. `sar` extra + capability probe.
3. `mmp_index.py` + `sar.mmp_build_index` (streaming) + metadata table + tests.
4. `mmp_predict.py` + `sar.mmp_predict`.
5. `selectivity_transforms.py` (consumes `selectivity.py`) + handler.
6. `free_wilson.py` + handler + tests.
7. Rust `sar.rs` + DTOs + registration + capability.
8. `sarStore` + SAR view/tab + `TransformTable`, `SelectivityTransformChart`, `FreeWilsonPanel` + apply-transform → library.
9. Integration test `tests/integration/test_sar_mmp.py`. **Close `GATE-H2`.**

---

## 5. Phase I — Design expansion

### 5.1 Feature I9 — Reaction-based combinatorial enumeration

**Gate:** requires `GATE-G1` (route-search confirmation step).

**Context.** Complements CReM: enumerate analogs from real reaction SMARTS + local building-block catalogs, then gate through G1 retrosynthesis. Provides a "design only what's synthesizable" mode beside exploratory graph mutation.

**License & deps.** RDKit reaction SMARTS only (BSD). No new heavy dep.

**Data assets** (`data/reactions/`): curated reaction template file `reactions.smarts` (amide coupling, SNAr, Suzuki, reductive amination, etc.) + reagent catalogs (`reagents_*.smi`, agrochem-relevant). Committable (small, own-authored).

**Python layout.** `python/edeon_generation/reaction_enum.py` (extends existing package):
- load reaction templates + reagent catalogs;
- enumerate products for a chosen core + reaction + reagent set;
- apply property/Tice/AD filters via existing engine modules;
- optionally pipe survivors to `retro.gate_batch`.

**JSON-RPC methods:**
```
gen.reaction_list_templates
  returns: { "ok": true, "templates": [ {"id": str, "name": str, "smarts": str,
             "n_reagent_slots": int} ] }

gen.reaction_enumerate           (slow → streams progress)
  params:  { "core_smiles": str|null, "template_id": str,
             "reagent_catalogs": [str], "max_products": 2000,
             "apply_filters": {"tice": true, "ad": true, "pains": true},
             "retro_gate": {"enabled": true, "ra_threshold": 0.5} }
  returns: { "ok": true, "products": [ { "smiles": str, "passed_filters": bool,
             "feasibility_score": float|null, "tier": str|null } ],
             "n_generated": int, "n_passed": int }
```

**Rust commands** (`commands/design.rs`, extend): `gen_reaction_list_templates`, `gen_reaction_enumerate` (streaming).

**SQLite migration:** reuse existing `generation_jobs` table; add column `job_kind TEXT DEFAULT 'crem'` and write `'reaction'` for these runs (append-only `ALTER TABLE` migration).

**Zustand deltas.** Extend `designStore`: `reactionTemplates`, `reactionJobs`, actions `listReactionTemplates`, `enumerateReaction`. Reuse the existing `synthesizable_only` toggle.

**UI surface.** New mode toggle in `GenerationWorkbenchView` ("Mutate (CReM) | Enumerate (Reactions)"). Template/reagent picker component `src/components/design/ReactionEnumPanel.tsx`; results flow into the existing `AnalogGrid` with the G1 Makeability column.

**Acceptance criteria.**
- `gen.reaction_list_templates` returns the shipped templates.
- Enumerating a core + Suzuki template + aryl-halide catalog yields valid products; filters reduce the set; with `retro_gate.enabled`, products carry `feasibility_score`.
- Mode toggle in the workbench switches cleanly between CReM and reaction enumeration.

**Task list.**
1. Author `reactions.smarts` + reagent catalogs; `I9` review of template chemistry validity.
2. `reaction_enum.py` + 2 handlers (streaming) + tests over a known core.
3. `generation_jobs.job_kind` migration.
4. Rust handlers + registration.
5. `designStore` deltas + `ReactionEnumPanel` + workbench toggle + AnalogGrid reuse.
6. Integration test `tests/integration/test_reaction_enum.py`.

---

### 5.2 Feature I4 — 3D shape + electrostatic similarity screening

**Context.** A fully permissive ROCS-style replacement (normally OpenEye territory): RDKit Open3DAlign for shape overlay + espsim for electrostatic similarity. Rank a library/generated set against a reference active by shape + ESP for scaffold hopping where 2D fingerprints fail. Strong synergy with the bioisostere carousel and `w8_scaffold_hop`.

**License & deps.** espsim (MIT), RDKit O3A (BSD, already present). Light extra `shape`. **Explicitly avoid** Silicos Align-it/Shape-it (GPL-3.0). Audit task `I4-AUDIT` (light).

**Python layout.** `python/edeon_engine/shape/`:
- `align.py` — ETKDG conformer gen (RDKit) → O3A alignment to reference.
- `espsim_score.py` — shape (Tanimoto-shape) + ESP similarity via espsim.
- `screen.py` — batch screen library vs reference; rank by combined score.

**JSON-RPC methods:**
```
shape.align_pair
  params:  { "ref_smiles": str, "query_smiles": str, "n_confs": 10 }
  returns: { "ok": true, "shape_sim": float, "esp_sim": float,
             "combined": float, "aligned_query_molblock": str }

shape.screen                     (slow → streams progress)
  params:  { "ref_smiles": str, "library": [ {"smiles": str, "id": str} ],
             "n_confs": 5, "weight_shape": 0.5, "weight_esp": 0.5,
             "top_k": 100 }
  returns: { "ok": true, "hits": [ { "id": str, "smiles": str,
             "shape_sim": float, "esp_sim": float, "combined": float } ] }
```

**Rust commands** (`commands/docking.rs` extend, or new `shape.rs`): `shape_align_pair`, `shape_screen` (streaming).

**SQLite migration:**
```sql
CREATE TABLE IF NOT EXISTS shape_alignments (
  ref_inchikey   TEXT NOT NULL,
  query_inchikey TEXT NOT NULL,
  shape_sim REAL, esp_sim REAL, combined REAL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (ref_inchikey, query_inchikey)
);
```

**Zustand deltas.** New `src/store/shapeStore.ts`: `refSmiles`, `hits`, `weights`, actions `alignPair`, `screen`. Add a "Shape/ESP screen" entry point from `w8_scaffold_hop` results and `BioisostereCarousel`.

**UI surface.**
- `src/components/shape/ShapeScreenPanel.tsx` — reference picker + weight sliders + ranked hit table.
- `src/components/shape/OverlayViewer.tsx` — reuse NGL to render `aligned_query_molblock` overlaid on the reference.
- "Send to Shape screen" action in scaffold-hop and bioisostere UIs.

**Acceptance criteria.**
- `shape.align_pair` returns shape & ESP sims in [0,1] and a valid aligned molblock that renders in NGL.
- `shape.screen` ranks a demo library; top hits are scaffold-distinct but shape-similar to the reference (spot-check).
- Weight sliders re-rank without recompute (combined score recomputed client-side or cheaply server-side).
- `shape` extra absent → capability gate.

**Task list.**
1. `I4-AUDIT` — confirm espsim MIT; confirm no GPL transitive deps pulled. *(gate, light)*
2. `shape` extra + probe.
3. `align.py` + `espsim_score.py` + `screen.py` + tests.
4. Handlers (incl. streaming screen).
5. Migration + caching.
6. Rust commands + registration.
7. `shapeStore` + `ShapeScreenPanel` + `OverlayViewer` + entry points from scaffold-hop/bioisostere.
8. Integration test `tests/integration/test_shape_screen.py`.

---

### 5.3 Feature I6 — Environmental / microbial metabolism expansion

**Gate:** requires `GATE-G5` (microspecies feed correct protonation to TP prediction & rescoring).

**Context.** Existing SyGMa pathway is mammalian-flavored. Registration-critical agrochem question is *soil microbial + abiotic/photo* transformation. Extend the **own** SMIRKS rule set with curated soil-microbial, photolysis, and hydrolysis rules; run each transformation product back through the full ecotox + fate stack (metabolite rescoring already exists). **BioTransformer is reference-only** — do not bundle or call it; its commercial terms are the blocker (same caution as the enviPath flag).

**License & deps.** Own SMIRKS authoring (extends `transformation/rules.txt`). No new code dep. Audit task `I6-AUDIT` documents the BioTransformer exclusion decision and the provenance of new rules.

**Python layout.** Extend `edeon_engine/transformation/`:
- `rules.txt` / `rules.py` — add tagged rule blocks: `# CLASS: soil_microbial | photolysis | hydrolysis | abiotic`.
- `pathway.py` — accept a `sources: [str]` param to select rule classes; tag each generated TP with its `source`.
- `environmental.py` (new) — orchestrate environmental-mode expansion: enumerate TPs by selected classes, dedupe, rescore through ecotox + `parent_fate`, flag TPs more persistent/toxic than parent ("TP liability" flags).

**JSON-RPC methods** (extend `fate.*`):
```
fate.predict_transformation_products      (extend existing)
  params:  { "smiles": str, "sources": ["soil_microbial","photolysis","hydrolysis"],
             "max_generations": 2, "ph": 6.5 }
  returns: { "ok": true, "nodes": [ { "smiles": str, "source": str,
             "generation": int, "parent_idx": int|null,
             "rescored": { ecotox+fate summary }, "liability_flag": bool } ],
             "edges": [ {"from": int, "to": int, "rule_name": str} ] }
```

**Rust commands** (`commands/fate.rs` extend): add `sources`, `ph` params to the existing transformation-product command; widen the DTO.

**SQLite migration:** `ALTER TABLE transformation_products ADD COLUMN source TEXT DEFAULT 'sygma';` + `ADD COLUMN liability_flag INTEGER DEFAULT 0;`

**Zustand deltas.** Extend `fateStore`: `tpSources: string[]` (selectable classes), reflect `source` + `liability_flag` in the pathway graph state.

**UI surface.** Extend `PathwayTree.tsx`: color/icon edges by rule class; badge liability TPs (reuse `RiskBadge`). Add a source-class multiselect in `FateView`. The pH slider (G5) feeds hydrolysis-relevant enumeration.

**Acceptance criteria.**
- Selecting `soil_microbial + hydrolysis` for a demo parent yields TPs tagged by `source`; ≥1 hydrolysis TP depends on the G5 dominant species.
- Rescored TPs surface in `PathwayTree`; any TP with worse persistence/tox than parent carries `liability_flag` + a visible badge.
- Default behavior (no `sources` given) reproduces prior SyGMa output (no regression).

**Task list.**
1. `I6-AUDIT` — document BioTransformer exclusion; cite literature provenance for each new SMIRKS class in `docs/PHASEI_METABOLISM_RULES.md`. *(gate)*
2. Author + validate new SMIRKS classes (chemistry review).
3. `pathway.py` source selection + tagging; `environmental.py` orchestration + rescoring; tests.
4. Extend `fate.predict_transformation_products` handler.
5. Migration (`source`, `liability_flag`).
6. Rust DTO/command extension + registration.
7. `fateStore` + `PathwayTree` coloring + liability badges + source multiselect.
8. Integration test `tests/integration/test_env_metabolism.py`.

---

## 6. Phase J — Mechanistic + cartography

### 6.1 Feature J8 — Mechanistic systemic-mobility model

**Gate:** requires `GATE-G5` (pKa/logP/microspecies inputs).

**Context.** Upgrade `workflows/systemicity.py` from heuristic to published ion-trap mechanistic models: Kleier permeability model + Bromilow weak-acid phloem-trapping relationships. Predict xylem vs phloem mobility and ambimobility from pKa + logP + microspecies. Crop-protection-specific, rarely in any software; makes the "will this be systemic in the crop" story mechanistic.

**License & deps.** Literature models, own implementation. No license constraint. No new dep.

**Python layout.** `edeon_engine/mobility/`:
- `kleier.py` — Kleier permeability/accumulation model.
- `bromilow.py` — weak-acid phloem-mobility relationships (concentration-factor vs pKa/logKow).
- `classify.py` — combine → mobility class (`xylem | phloem | ambimobile | immobile`) + numeric mobility indices + confidence band.
- Refactor `workflows/systemicity.py` to call `mobility.classify` (keep the heuristic as a labeled fallback when inputs are out of model domain).

**JSON-RPC methods:**
```
mobility.predict
  params:  { "smiles": str, "ph_apoplast": 5.5, "ph_phloem": 8.0 }
  returns: { "ok": true,
             "class": "xylem|phloem|ambimobile|immobile",
             "phloem_concentration_factor": float,
             "xylem_index": float, "phloem_index": float,
             "drivers": { "pka": [float], "logkow": float,
                          "dominant_charge_apoplast": int },
             "confidence": "in_domain|edge|out_of_domain" }
```

**Rust commands** (`commands/fate.rs` extend or new `mobility.rs`): `mobility_predict`.

**SQLite migration:**
```sql
CREATE TABLE IF NOT EXISTS mobility_predictions (
  inchikey TEXT PRIMARY KEY,
  class TEXT, phloem_cf REAL, xylem_index REAL, phloem_index REAL,
  confidence TEXT, payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**Zustand deltas.** Extend `fateStore` (or `workflowStore` where systemicity is surfaced): `mobility: Record<inchikey, MobilityResult>`; action `predictMobility`.

**UI surface.**
- `src/components/fate/MobilityCard.tsx` — class badge + Kleier/Bromilow indices + driver readout + confidence chip.
- Embed in `FateView` and in `Inspector` selectivity/resistance area. Add to the Environmental Fate Dossier PDF export (`commands/export.rs`).

**Acceptance criteria.**
- For a weak-acid demo (e.g. a phenoxy-type acid) `mobility.predict` returns `class=phloem` or `ambimobile` with a phloem CF > 1; for a neutral lipophile, `xylem`/`immobile` as appropriate.
- Out-of-domain inputs return `confidence=out_of_domain` and the UI labels the heuristic fallback.
- Mobility appears in the Environmental Fate Dossier export.

**Task list.**
1. Implement `kleier.py`, `bromilow.py`, `classify.py` with unit tests against published reference values (cite in `docs/MOBILITY_MODEL.md`).
2. Refactor `systemicity.py` to delegate; keep heuristic fallback.
3. `mobility.predict` handler.
4. Migration + caching.
5. Rust command + DTO + registration + dossier export wiring.
6. `MobilityCard` + store + Inspector/FateView embedding.
7. Integration test `tests/integration/test_mobility.py`.

---

### 6.2 Feature J7 — Chemical-space cartography (TMAP)

**Context.** TMAP builds MST-based maps that scale beyond t-SNE/UMAP. Project a library, color by predicted endpoint / AD coverage / selectivity window / cluster; lasso-select straight into a workflow. Doubles as gap-analysis ("where is my selectivity window unexplored?") and as EuroQSAR demo eye-candy.

**License & deps.** TMAP + Faerun (MIT). Heavy extra `cartography`. Audit task `J7-AUDIT`.

**Python layout.** `python/edeon_cartography/`:
- `project.py` — MHFP fingerprints → LSH forest → TMAP layout (x,y + edge list).
- `color.py` — compute color channels from endpoint predictions / AD status / selectivity window / cluster id.
- `ipc_handlers.py`, `schema.py`.

**JSON-RPC methods:**
```
carto.project                    (slow → streams progress)
  params:  { "library": [ {"smiles": str, "id": str} ],
             "color_by": "endpoint:dt50 | ad_status | selectivity_window | cluster" }
  emits:   "carto://progress" { "stage": str, "pct": float }
  returns: { "ok": true, "map_id": str,
             "nodes": [ { "id": str, "x": float, "y": float,
                          "color_value": float|str } ],
             "edges": [ [int, int] ] }

carto.recolor
  params:  { "map_id": str, "color_by": str }
  returns: { "ok": true, "nodes": [ {"id": str, "color_value": float|str} ] }
```

**Rust commands** (`commands/` new `cartography.rs`): `carto_project` (streaming), `carto_recolor`, `carto_list_maps`, `carto_delete_map`.

**SQLite migration:**
```sql
CREATE TABLE IF NOT EXISTS cartography_maps (
  map_id TEXT PRIMARY KEY,
  name TEXT, n_nodes INTEGER,
  layout_json TEXT NOT NULL,        -- nodes+edges
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**Zustand deltas.** New `src/store/cartographyStore.ts`: `maps`, `activeMap`, `colorBy`, `selection`, actions `project`, `recolor`, `selectNodes`, `sendSelectionToWorkflow`.

**UI surface.**
- New view `src/views/CartographyView.tsx` (+ `ViewId: 'cartography'`, sidebar entry, route in `App.tsx`).
- `src/components/cartography/TmapCanvas.tsx` — WebGL/canvas renderer (deck.gl or a lightweight canvas; reuse Faerun's HTML export only as a fallback). Lasso select → `compoundStore` subset → "Send selection to workflow" (reuse the existing Send-to-VS transfer pattern).
- Color-by selector + legend.

**Acceptance criteria.**
- `carto.project` over a ≥500-compound library returns nodes + MST edges; progress events stream.
- Recoloring by each `color_by` channel updates the canvas without recomputing layout.
- Lasso selection transfers the chosen compounds into a workflow run.
- `cartography` extra absent → capability gate; view shows enable banner.

**Task list.**
1. `J7-AUDIT` — confirm TMAP + Faerun MIT. *(gate)*
2. `cartography` extra + probe.
3. `project.py` + `color.py` + handlers (streaming) + tests.
4. Migration + map persistence.
5. Rust `cartography.rs` + registration + capability.
6. `cartographyStore` + `CartographyView` + `TmapCanvas` + lasso→workflow transfer.
7. Integration test `tests/integration/test_cartography.py`.

---

## 7. Phase K — Orchestration

### 7.1 Feature K10 — Bayesian-optimization active-learning loop

**Gate:** benefits from `GATE-G1` (synthesizability objective) and `GATE-H2` (MMP-aware proposals); requires functioning UQ from existing models.

**Context.** Turn the existing `active_learning` workflow into a proper multi-objective BO loop: GP surrogate over existing descriptors, existing UQ as the acquisition signal, iteratively proposing the next batch trading off selectivity × fate × tox (× synthesizability). Converts Edeon from a scoring tool into a *campaign* tool.

**License & deps.** BoTorch + GPyTorch + torch (MIT). Heavy extra `optimize`. Lighter fallback: scikit-optimize (BSD) single-objective if torch is unwanted. Audit task `K10-AUDIT`.

**Python layout.** `python/edeon_optimize/`:
- `surrogate.py` — GP surrogate (BoTorch SingleTaskGP / ModelListGP for multi-objective) over a chosen featurizer block.
- `acquisition.py` — qNEHVI (multi-objective) / qEI (single); incorporate model UQ.
- `campaign.py` — campaign state machine: init from labeled set → propose batch → ingest results → re-fit → repeat; persist iterations.
- `objectives.py` — adapter mapping Edeon endpoints (selectivity window, DT50, bee LD50, feasibility_score) to maximize/minimize objectives with reference points.
- `ipc_handlers.py`, `schema.py`.

**JSON-RPC methods:**
```
opt.campaign_create
  params:  { "name": str, "featurizer": "morgan|2d|...",
             "objectives": [ {"endpoint": str, "direction": "max|min",
                              "weight": float} ],
             "candidate_pool": [ {"smiles": str, "id": str} ],
             "initial_labeled": [ {"id": str, "values": {endpoint: float}} ],
             "batch_size": 8 }
  returns: { "ok": true, "campaign_id": str }

opt.propose_batch              (slow → streams fit/acq progress)
  params:  { "campaign_id": str }
  returns: { "ok": true, "iteration": int,
             "proposals": [ { "id": str, "smiles": str,
                              "acq_value": float,
                              "predicted": {endpoint: {mean, std}} } ] }

opt.ingest_results
  params:  { "campaign_id": str,
             "results": [ {"id": str, "values": {endpoint: float}} ] }
  returns: { "ok": true, "iteration": int, "n_labeled": int,
             "hypervolume": float|null }

opt.campaign_state
  params:  { "campaign_id": str }
  returns: { "ok": true, "iteration": int, "labeled": int,
             "pareto_front": [ {"id": str, "values": {...}} ],
             "hv_history": [float] }
```

**Rust commands** (`commands/` new `optimize.rs`): `opt_campaign_create`, `opt_propose_batch` (streaming), `opt_ingest_results`, `opt_campaign_state`, `opt_list_campaigns`, `opt_delete_campaign`.

**SQLite migration:**
```sql
CREATE TABLE IF NOT EXISTS optimization_campaigns (
  campaign_id TEXT PRIMARY KEY,
  name TEXT, featurizer TEXT, objectives_json TEXT NOT NULL,
  batch_size INTEGER, created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS optimization_iterations (
  campaign_id TEXT NOT NULL,
  iteration   INTEGER NOT NULL,
  proposals_json TEXT, results_json TEXT,
  hypervolume REAL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (campaign_id, iteration)
);
```

**Zustand deltas.** New `src/store/optimizeStore.ts`: `campaigns`, `activeCampaign`, `proposals`, `paretoFront`, `hvHistory`, actions `createCampaign`, `proposeBatch`, `ingestResults`, `loadState`. Tie into `workflowStore` so a campaign can pull its candidate pool from a prepared library.

**UI surface.**
- New view `src/views/OptimizationView.tsx` (`ViewId: 'optimization'`, sidebar + route).
- `src/components/optimize/CampaignSetup.tsx` — objective builder (endpoint, direction, weight), featurizer + batch size.
- `src/components/optimize/ProposalGrid.tsx` — proposed batch with predicted endpoints + UQ (reuse `UqBadge`/`IntervalBar`); "register results" entry for measured/simulated values.
- `src/components/optimize/ParetoChart.tsx` — 2D/3D Pareto front + `HvHistory` convergence line (Recharts).
- "Start BO campaign" entry from `ResultsTable` (seed pool from a prepared library).

**Acceptance criteria.**
- A multi-objective campaign (e.g. maximize selectivity window, minimize DT50) initializes, proposes a batch sized `batch_size`, and each proposal carries per-objective mean+std.
- `opt.ingest_results` advances the iteration, re-fits, and hypervolume is non-decreasing across iterations on a synthetic benchmark.
- Pareto front + HV history render and update each iteration.
- `optimize` extra absent → capability gate; single-objective scikit-optimize fallback usable if configured.

**Task list.**
1. `K10-AUDIT` — confirm BoTorch/GPyTorch/torch MIT + acceptable bundle/footprint; decide default vs opt-in heavy install. *(gate)*
2. `optimize` extra + probe; optional scikit-optimize fallback path.
3. `surrogate.py` + `acquisition.py` + `objectives.py` + `campaign.py` + unit tests on a synthetic 2-objective problem (verify HV monotonicity).
4. 4 handlers (propose streaming).
5. Migrations (campaigns + iterations).
6. Rust `optimize.rs` + registration + capability.
7. `optimizeStore` + `OptimizationView` + `CampaignSetup`/`ProposalGrid`/`ParetoChart` + seed-from-library entry.
8. Integration test `tests/integration/test_bo_campaign.py`.

---

## 8. Master task manifest (ordered, with gates)

| Order | Task ID | Phase | Blocking gate(s) | Notes |
|------:|---------|-------|------------------|-------|
| 1 | G5-AUDIT | G | — | Dimorphite Apache-2.0; pkasolver verify |
| 2 | G5-IMPL | G | G5-AUDIT | speciation primitive → **GATE-G5** |
| 3 | G1-AUDIT | G | — | AiZynthFinder + RAscore licenses |
| 4 | G1-IMPL | G | G1-AUDIT | retro engine → **GATE-G1** |
| 5 | H2-AUDIT | H | — | mmpdb license (or RDKit fallback) |
| 6 | H2-IMPL | H | H2-AUDIT | MMP + Free-Wilson → **GATE-H2** |
| 7 | I9-IMPL | I | GATE-G1 | reaction enumeration |
| 8 | I4-AUDIT | I | — | espsim MIT + no GPL transitive |
| 9 | I4-IMPL | I | I4-AUDIT | shape/ESP screening |
| 10 | I6-AUDIT | I | — | BioTransformer exclusion + rule provenance |
| 11 | I6-IMPL | I | GATE-G5, I6-AUDIT | env/microbial metabolism |
| 12 | J8-IMPL | J | GATE-G5 | systemic mobility |
| 13 | J7-AUDIT | J | — | TMAP/Faerun MIT |
| 14 | J7-IMPL | J | J7-AUDIT | cartography |
| 15 | K10-AUDIT | K | — | BoTorch/GPyTorch footprint |
| 16 | K10-IMPL | K | GATE-G1, GATE-H2, K10-AUDIT | Bayesian-opt loop |

**Cross-cutting tasks (apply once, early):**
- `XC-1` pyproject extras + `feature_capabilities()` probe + frontend startup wiring + `feature_unavailable` error envelope (do before any heavy feature).
- `XC-2` shared migration helper convention check (append-only, `user_version` bump) — verify before first new migration.
- `XC-3` extend `EmptyState`/banner pattern for `feature_unavailable`/`license_gated`.
- `XC-4` add new `ViewId`s, sidebar entries, and routes for `cartography` and `optimization` views in one pass.

**Definition of done (per feature):** handlers registered + unit tests green; Rust command + DTO + capability; store + UI wired; integration test green; base build (no extras) still launches and passes existing suite; capability gate verified by removing the extra; audit doc updated if applicable.

---

## 9. Open verification items (carry into audits — not asserted here)

These are flagged rather than assumed, consistent with the per-component audit discipline; confirm against current upstream before default-bundling:
- mmpdb exact license + redistribution terms (`H2-AUDIT`).
- pkasolver license (`G5-AUDIT`); Dimorphite-DL Apache-2.0 is expected but reconfirm version.
- AiZynthFinder + RAscore licenses **and** redistribution terms for their model/template assets (`G1-AUDIT`).
- espsim transitive dependency tree for any GPL pull-in (`I4-AUDIT`).
- BioTransformer commercial terms — kept **excluded**; document the decision (`I6-AUDIT`).
- torch/BoTorch bundle-footprint vs scikit-optimize fallback decision (`K10-AUDIT`).
