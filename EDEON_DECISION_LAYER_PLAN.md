# Edeon Desktop — Implementation Plan: Decision Layer (Phases L & M)

> Target executor: coding agent (Claude Code / equivalent), grounded against the current Edeon codebase.
> Scope: two features — **L1 Bottleneck Analyzer** and **M1 Decision Journal**.
> Companion to `EDEON_FOSS_INTEGRATIONS_PLAN.md` (Phases G–K). Same conventions apply; §1 of that document (IPC contract, error envelope, extras strategy, UQ propagation rules) is **normative here** and is not restated.
> Design posture: these features give the expert user better inputs to *their* decisions. They do **not** make decisions autonomously, and they introduce **no LLM/agent orchestration layer**. No new third-party dependency, therefore **no license gate**.

---

## 0. How to use this document (agent instructions)

1. Read §1 of `EDEON_FOSS_INTEGRATIONS_PLAN.md` first. Error envelope, migration convention (append-only, bump `user_version`), lazy-import discipline, and the `{value, interval, ad_status, tier}` UQ contract all carry over unchanged.
2. Both features are **pure-Python + existing deps** (numpy, scipy, pandas, RDKit). No `pyproject.toml` extras, no capability probe entries, no audit tasks.
3. **Phase M's journal writer is cross-cutting infrastructure.** Build `M1-CORE` (schema + Rust `JournalWriter`) before instrumenting any call site. L1 is one of the call sites.
4. Two hard invariants, violated at your peril:
   - **INV-1 (atomicity).** A journal entry and the state change it describes commit in the **same SQLite transaction**, written from Rust. Python never writes to the journal.
   - **INV-2 (append-only).** Journal rows are immutable. Corrections are new rows linked by `supersedes_id`. There is no `UPDATE` or `DELETE` path on `decision_journal` other than whole-project deletion cascade.
5. Statistical honesty is a functional requirement, not a nicety. Every leverage/bottleneck number ships with an uncertainty band and a small-n guard (§2.6). A confident-looking bottleneck computed from 12 compounds is a bug.

---

## 1. Dependency graph

```
Phase M (core)  ──►  M1-CORE: schema + Rust JournalWriter + provenance hashing
                          │
                          ├──►  Phase L: L1 Bottleneck Analyzer  ──┐
                          │        (emits bottleneck_identified)   │
                          │                                        │
                          └──►  M1-HOOKS: instrument existing      │
                                 call sites (workflow, models,     │
                                 design, fate, optimize)  ◄────────┘
                                        │
                                 M1-UI: Journal view, lineage,
                                 override analytics, dossier export
```

**Gates:**
- `GATE-M-CORE`: `journal_append` writes an immutable row inside a caller-supplied transaction; a forced rollback of the caller leaves **no** journal row. → unblocks L1 emission and all hooks.
- `GATE-L1`: `bottleneck.analyze` returns a ranked, uncertainty-banded bottleneck list for a demo compound set, with `kind` correctly separating chemical from epistemic on a synthetic fixture. → unblocks K10 objective seeding and the Bottleneck card.

**Upstream (optional, degrade gracefully):**
- H2 (MMP index) — if present, supplies *achievability* evidence and antagonism direction (§2.4). If absent, L1 falls back to distribution-based achievability and reports `achievability_source: "spread"`.
- K10 (BO campaigns) — if present, L1 seeds objective weights and K10 emits journal entries. If absent, both features function standalone.

---

## 2. Phase L — Bottleneck Analyzer

### 2.1 Context and intent

Given a compound set and its full endpoint profile (ecotox, fate, selectivity, mobility, synthesizability), identify **which property is the binding constraint on program viability** — i.e. the endpoint where a unit of improvement buys the most aggregate progress, accounting for how much improvement is actually reachable and how confident we are in the estimate.

This replaces a manual expert scan across a dozen endpoint columns. It is a *sensitivity analysis over the existing MPO/scorecard*, not a new model.

Three questions it answers:
1. **Where is the constraint?** (ranked leverage over endpoints)
2. **Is it chemistry or ignorance?** (`kind: chemical | epistemic`)
3. **What will it cost me elsewhere?** (antagonism / trade-off surface)

### 2.2 Method — leverage by counterfactual substitution

Deliberately **aggregation-function-agnostic**: no closed-form gradient, so it works for arithmetic MPO, geometric MPO, or the regulatory scorecard without re-derivation.

For a compound set `C` and endpoint set `E`:

1. **Desirability.** For each compound `c` and endpoint `i`, map the raw prediction to `d_i(c) ∈ [0,1]` via a desirability curve. **Reuse `edeon_engine/regulatory/cutoffs.py`** — regulatory thresholds are the natural breakpoints. Curve types: `higher_better`, `lower_better`, `target_window`, `step` (hard regulatory cut). Config lives in `data/desirability/<profile>.json`; ship an agrochem default profile.
2. **Aggregate.** `S(c) = agg(d(c), w)` where `agg` is the existing MPO/scorecard function (`scoring.py`). Do not reimplement it — call it.
3. **Achievable target.** For each endpoint, estimate `d_i*` — the desirability reachable by chemistry the program already demonstrates:
   - `spread` (default): the q90 of `d_i` over the in-AD subset of `C`. "What the good compounds in this set already achieve."
   - `mmp` (if H2 index available): `d_i` after applying the best single observed transform delta from the MMP index. Causal-flavoured, not just distributional.
   - `expert`: user-supplied target in the desirability profile.
4. **Leverage.** Counterfactual substitution — recompute the aggregate with endpoint `i` lifted to its achievable target, everything else held:
   ```
   ΔS_i(c) = agg(d(c) with d_i := max(d_i(c), d_i*), w) − S(c)
   leverage_i = mean_over_C( ΔS_i(c) )
   ```
   Numeric, robust, needs no derivative, and honours hard gates (a step-function cutoff shows enormous leverage precisely when it is the thing failing — which is correct).
5. **Rank.** Sort endpoints by `leverage_i` descending. The top entry is the bottleneck.

`headroom_i = mean(d_i* − d_i(c))` is reported alongside: high headroom + low leverage means "lots of room, doesn't matter" (a *distractor* endpoint — worth surfacing explicitly, it is exactly where teams waste effort).

### 2.3 Chemical vs epistemic bottleneck

The distinction that makes this feature worth building.

Propagate prediction uncertainty through the leverage ranking:
- For each compound × endpoint, sample `N = 500` draws from the predictive distribution implied by the existing UQ (conformal interval or heteroscedastic σ — reuse `edeon_train/shared/mc_propagation.py`).
- Out-of-AD predictions get an inflated/uninformative distribution (widen to the endpoint's marginal spread; do **not** silently treat an out-of-AD point estimate as reliable).
- Recompute the full leverage ranking per draw → distribution over ranks.
- Report `rank_stability_i` = fraction of draws in which endpoint `i` holds its point-estimate rank, and a bootstrap CI on `leverage_i`.

Classification:
- `kind = "chemical"` — leverage is high **and** rank is stable (`rank_stability ≥ 0.6`) **and** the endpoint's mean interval width is below a configurable fraction of its dynamic range. The molecules are genuinely bad on this endpoint. Action: optimize chemistry.
- `kind = "epistemic"` — leverage is high but rank is unstable, **or** the endpoint is dominated by out-of-AD / wide-interval predictions. You cannot tell whether it is a bottleneck. Action: **measure it, or improve the model** — do not spend synthesis slots.

`recommended_action` is a short enum + templated string (`optimize_chemistry`, `measure_endpoint`, `improve_model`, `expand_ad`, `no_action_distractor`), **not** free-form generated prose.

### 2.4 Antagonism / trade-off surface

Improving the bottleneck often regresses something else. Two evidence sources, reported separately (never merged into one number):

- **Correlational** (always available): Spearman ρ between endpoints across the compound set, computed on **desirability**, not raw values, so sign is interpretable. `ρ < −0.3` between two desirabilities ⇒ candidate antagonistic pair. Report ρ with its CI and `n`. Label plainly as correlational — this is co-occurrence in the current set, not causation.
- **Transform-based** (requires H2): from the MMP index, the mean paired Δd for both endpoints over the same transforms. A transform set that consistently raises `d_A` and lowers `d_B` is directional evidence of a real trade-off. Report `n_transforms` supporting it.

Output: a `tradeoffs` list, plus a 2-endpoint scatter for the UI (desirability A vs desirability B, Pareto front overlaid).

### 2.5 Set-level gate attrition (empirical bottleneck)

Independent of the model-based leverage: **which gate actually kills the most compounds?** Reuse the data already behind `AttritionWaterfall`. For a workflow run, report per-stage/per-filter kill counts and the fraction of the original library removed. This is the empirical, assumption-free bottleneck view and it acts as a sanity check on the leverage ranking. If they disagree, that disagreement is itself informative and should be surfaced, not hidden.

### 2.6 Small-n guard (mandatory)

- `n < 15` in-AD compounds for an endpoint → that endpoint's leverage is returned with `reliability: "insufficient_data"` and is **excluded from the bottleneck ranking** (still listed, greyed in UI).
- `n < 30` → `reliability: "low"`, CI displayed prominently, UI shows a caution chip.
- Bootstrap CIs (`n_boot = 1000`, percentile) on every `leverage_i` and every ρ.
- If the top-2 leverage CIs overlap by more than 50%, the response sets `bottleneck_ambiguous: true` and the UI presents them as co-equal rather than ranked. Do not manufacture a false winner.

### 2.7 Python layout

New package `python/edeon_bottleneck/`:

| Module | Purpose |
|--------|---------|
| `desirability.py` | Desirability curves; loads profile JSON; reuses `regulatory/cutoffs.py` thresholds |
| `leverage.py` | Counterfactual substitution, headroom, achievability estimators (`spread` / `mmp` / `expert`) |
| `uncertainty.py` | MC propagation through the ranking (wraps `edeon_train/shared/mc_propagation.py`), rank stability, bootstrap CIs |
| `classify.py` | chemical vs epistemic; `recommended_action` enum |
| `antagonism.py` | Spearman trade-off surface + optional MMP transform evidence |
| `attrition.py` | Gate-attrition bottleneck from workflow run data |
| `weights.py` | Emit suggested K10 objective weights from the leverage profile |
| `ipc_handlers.py`, `schema.py` | JSON-RPC surface + typed results |

Also ship `data/desirability/agrochem_default.json` (committed; small, own-authored) covering: fish, daphnia, algae, bee_oral, bee_contact, bird, earthworm, rat_ld50, skin_sens, bcf, koc, dt50, gus, selectivity_window, mobility_class, feasibility_score.

### 2.8 JSON-RPC methods

```
bottleneck.analyze                              (moderate cost → streams progress)
  params:  { "compounds": [ { "id": str, "smiles": str,
                              "endpoints": { <endpoint>: { "value": float,
                                                           "interval": [lo,hi] | null,
                                                           "ad_status": "in|edge|out" } } } ],
             "profile": "agrochem_default",
             "weights": { <endpoint>: float } | null,      # null → profile defaults
             "achievability": "spread | mmp | expert",
             "mmp_index_id": str | null,
             "n_mc": 500, "n_boot": 1000 }
  emits:   "bottleneck://progress" { "stage": "desirability|leverage|uncertainty|antagonism",
                                     "pct": float }
  returns: { "ok": true,
             "bottleneck_ambiguous": bool,
             "achievability_source": "spread|mmp|expert",
             "ranking": [ { "endpoint": str,
                            "leverage": float,
                            "leverage_ci": [lo, hi],
                            "headroom": float,
                            "mean_desirability": float,
                            "rank_stability": float,
                            "kind": "chemical|epistemic|distractor",
                            "reliability": "ok|low|insufficient_data",
                            "n_in_ad": int,
                            "recommended_action": "optimize_chemistry|measure_endpoint|improve_model|expand_ad|no_action_distractor" } ],
             "tradeoffs": [ { "endpoint_a": str, "endpoint_b": str,
                              "spearman_rho": float, "rho_ci": [lo,hi], "n": int,
                              "mmp_evidence": { "delta_a": float, "delta_b": float,
                                                "n_transforms": int } | null } ] }

bottleneck.compound                              (single-compound weakest link)
  params:  { "compound": { ...as above... }, "profile": str, "weights": {...}|null }
  returns: { "ok": true,
             "weakest_link": str,
             "ranking": [ { "endpoint": str, "desirability": float,
                            "delta_if_fixed": float, "kind": str } ] }

bottleneck.attrition
  params:  { "workflow_id": str }
  returns: { "ok": true,
             "stages": [ { "stage": str, "filter": str,
                           "n_in": int, "n_out": int, "n_killed": int,
                           "frac_of_library": float } ],
             "dominant_gate": str }

bottleneck.suggest_weights                       (seeds a K10 campaign)
  params:  { "analysis_id": str }
  returns: { "ok": true,
             "objectives": [ { "endpoint": str, "direction": "max|min",
                               "weight": float, "rationale": str } ] }

bottleneck.list_profiles
  returns: { "ok": true, "profiles": [ {"id": str, "name": str, "n_endpoints": int} ] }
```

### 2.9 Rust commands

New `src-tauri/src/commands/bottleneck.rs`:
- `bottleneck_analyze(...) -> BottleneckAnalysis` (streaming variant, `send_request_with_app`)
- `bottleneck_compound(...) -> CompoundBottleneck`
- `bottleneck_attrition(workflow_id) -> AttritionAnalysis`
- `bottleneck_suggest_weights(analysis_id) -> Vec<ObjectiveSeed>`
- `bottleneck_list_profiles() -> Vec<ProfileRef>`

Register in `lib.rs`; DTOs in `models.rs`; capability entry in `capabilities/`.
**On successful `bottleneck_analyze`, the command writes a `bottleneck_identified` journal entry in the same transaction as the analysis persist** (see §3, INV-1).

### 2.10 SQLite migration

```sql
CREATE TABLE IF NOT EXISTS bottleneck_analyses (
  analysis_id   TEXT PRIMARY KEY,
  project_id    TEXT NOT NULL,
  workflow_id   TEXT,                       -- nullable: may run on an ad-hoc set
  profile       TEXT NOT NULL,
  n_compounds   INTEGER NOT NULL,
  top_endpoint  TEXT,
  top_kind      TEXT,                       -- chemical | epistemic | distractor
  ambiguous     INTEGER NOT NULL DEFAULT 0,
  payload_json  TEXT NOT NULL,              -- full BottleneckAnalysis
  params_hash   TEXT NOT NULL,              -- provenance
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_bottleneck_project ON bottleneck_analyses(project_id, created_at DESC);
```

### 2.11 Zustand deltas

New `src/store/bottleneckStore.ts`:
- state: `analyses: Record<analysisId, BottleneckAnalysis>`, `activeAnalysisId`, `profiles`, `progress`, `compoundBottleneck: Record<compoundId, CompoundBottleneck>`
- actions: `analyze(compounds, opts)`, `analyzeCompound(id)`, `attrition(workflowId)`, `suggestWeights(analysisId)`, `listProfiles()`; subscribe to `bottleneck://progress`.
- Cross-store: `optimizeStore.createCampaign` accepts a `seedFromAnalysisId` to prefill objectives (K10 integration, no-op if K10 absent).

### 2.12 UI surface

| Component | File | Purpose |
|-----------|------|---------|
| `BottleneckCard` | `src/components/bottleneck/BottleneckCard.tsx` | Headline card in `WorkflowView`: top bottleneck, `kind` chip (chemical/epistemic), leverage bar + CI whisker, recommended action, reliability caution chip. Renders co-equal top-2 when `bottleneck_ambiguous`. |
| `LeverageChart` | `src/components/bottleneck/LeverageChart.tsx` | Recharts horizontal bars: leverage per endpoint with CI error bars; colour-coded by `kind`; `insufficient_data` endpoints greyed and sorted last. |
| `TradeoffMatrix` | `src/components/bottleneck/TradeoffMatrix.tsx` | Endpoint × endpoint heatmap of Spearman ρ (desirability space); click a cell → scatter with Pareto front; MMP evidence badge where available. |
| `AttritionBottleneck` | `src/components/bottleneck/AttritionBottleneck.tsx` | Extends the existing `AttritionWaterfall` with a "dominant gate" callout; shows agreement/disagreement with the leverage ranking. |
| `WeakestLinkBadge` | `src/components/bottleneck/WeakestLinkBadge.tsx` | Per-compound weakest-link pill, rendered in `Inspector` and as a `ResultsTable` column. |

Entry points: auto-run `bottleneck.analyze` on workflow completion (results already in memory — no extra compute round-trip for the user); "Seed BO campaign from bottleneck" button on `BottleneckCard` → `OptimizationView`.

**UI honesty rules (enforce in review):** never render a bottleneck without its reliability chip; never hide the epistemic classification behind a tooltip; when `bottleneck_ambiguous`, the card must not display a single winner.

### 2.13 Acceptance criteria

- **Synthetic fixture A (chemical):** compound set where one endpoint is uniformly poor with tight intervals and in-AD → that endpoint ranks first with `kind="chemical"`, `rank_stability > 0.8`.
- **Synthetic fixture B (epistemic):** same set but the endpoint's predictions are out-of-AD with wide intervals → same endpoint ranks first but with `kind="epistemic"` and `recommended_action="measure_endpoint"`. **This test is the feature's reason to exist; it must pass before anything ships.**
- **Synthetic fixture C (distractor):** endpoint with large headroom but near-zero leverage (low weight, aggregate insensitive) → `kind="distractor"`, `recommended_action="no_action_distractor"`.
- **Small-n:** a set of 10 compounds returns every endpoint at `reliability="insufficient_data"` and an empty effective ranking; the UI shows the guard message, not a bottleneck.
- **Ambiguity:** a fixture with two endpoints of near-identical leverage sets `bottleneck_ambiguous=true`; `BottleneckCard` renders both.
- `bottleneck.attrition` on a completed demo workflow returns per-stage kill counts summing to the total attrition shown by `AttritionWaterfall` (exact agreement — regression test).
- `bottleneck.suggest_weights` output loads into `CampaignSetup` and produces a valid K10 campaign (skip if K10 not yet built).
- With no MMP index present, analysis completes with `achievability_source="spread"` and `mmp_evidence: null` throughout — no error.
- Every successful analyze writes exactly one `bottleneck_identified` journal row (requires M1-CORE).

### 2.14 Ordered task list

1. `L1-T1` Author `data/desirability/agrochem_default.json`; wire `desirability.py` to `regulatory/cutoffs.py`. Unit-test each curve type against known thresholds.
2. `L1-T2` `leverage.py` — counterfactual substitution + headroom + three achievability estimators. Tests on fixtures A/C.
3. `L1-T3` `uncertainty.py` — MC propagation, rank stability, bootstrap CIs, small-n guard. Test on fixture B.
4. `L1-T4` `classify.py` — kind + recommended_action enum. Tests on A/B/C.
5. `L1-T5` `antagonism.py` — Spearman surface; optional MMP evidence path (feature-detect H2 index).
6. `L1-T6` `attrition.py` — gate attrition from workflow run data; regression test vs `AttritionWaterfall`.
7. `L1-T7` `weights.py` — K10 objective seeding.
8. `L1-T8` 5 JSON-RPC handlers (analyze streaming) + `schema.py`.
9. `L1-T9` Migration `bottleneck_analyses`.
10. `L1-T10` Rust `bottleneck.rs` + DTOs + registration + capability + **journal emission (INV-1)**.
11. `L1-T11` `bottleneckStore` + 5 components + auto-run on workflow completion + K10 seed button.
12. `L1-T12` Integration test `tests/integration/test_bottleneck.py`. **Close `GATE-L1`.**

---

## 3. Phase M — Decision Journal

### 3.1 Context and intent

A persistent, immutable, queryable record of **every consequential decision** taken in a project — what was decided, by whom (system or user), on what evidence, what the alternatives were, and how confident the system was. Exportable as a section of the regulatory dossier.

This is the traceability story ("show me why this candidate advanced over that one") without any agentic layer. It extends the existing `DecisionArtifact` / `ReproducibilityInfo` / `provenance.py` patterns into a first-class, project-scoped log.

**Design constraint that determines success or failure: the journal is auto-captured.** If the user has to fill in a form, it will be empty within a week and worthless. Every entry is emitted by an existing code path at the moment the decision is made. The only user-authored fields are an optional free-text note and an optional override reason.

### 3.2 Decision taxonomy

`decision_kind` enum (extensible; unknown kinds must round-trip without loss):

| Kind | Emitted by | Subject |
|------|-----------|---------|
| `workflow_verdict` | `commands/workflow.rs` on run completion | workflow_id |
| `compound_promoted` | workflow gate pass / "Send to VS" transfer | compound_id |
| `compound_rejected` | workflow gate fail (batched: one row per gate, with id list) | gate + compound ids |
| `model_deployed` | `commands/models.rs` deploy_studio_model | model_id |
| `model_selected` | Arena tournament winner adopted | model_id |
| `bottleneck_identified` | `commands/bottleneck.rs` (L1) | analysis_id |
| `bo_batch_proposed` | K10 `opt_propose_batch` | campaign_id + iteration |
| `bo_proposal_accepted` / `bo_proposal_rejected` | user action on `ProposalGrid` | compound ids |
| `transform_applied` | H2 "apply transform → register product" | parent + product |
| `analog_registered` | generation → library promotion | compound_id |
| `tp_liability_flagged` | fate/I6 rescoring flags a TP worse than parent | tp_id |
| `manual_override` | **any user action contradicting a system recommendation** | varies |
| `parameter_changed` | material run-config change (workflow params, weights, thresholds) | run_config |

**`manual_override` is the highest-value row type in the schema.** It is the only place the system records that a human disagreed with it — which is the raw material for both the calibration story and the override analytics in §3.6. Every UI surface that presents a system recommendation must be capable of emitting one when the user goes the other way.

### 3.3 Record structure

```
DecisionEntry {
  entry_id:        uuid
  project_id:      str
  created_at:      iso8601
  actor:           "system" | "user"
  decision_kind:   <enum above>
  subject_type:    "compound" | "workflow" | "model" | "campaign" | "analysis" | "tp" | "config"
  subject_id:      str
  summary:         str                     # one-line, templated — NOT generated prose
  rationale: {
    drivers:       [ { "factor": str, "value": float, "contribution": float } ],
    scores:        { <name>: float },
    thresholds:    { <name>: float }
  }
  alternatives: [ { "id": str, "label": str, "score": float,
                    "why_not": str } ]      # top-k not chosen, templated reason
  confidence: {
    uq:            { <endpoint>: {"interval": [lo,hi]} } | null,
    ad_status:     "in" | "edge" | "out" | null,
    reliability:   "ok" | "low" | "insufficient_data" | null
  }
  provenance: {
    params_hash:   str,                     # links to the exact inputs
    model_versions:{ <endpoint>: str },
    code_version:  str,                     # app version / git sha
    seed:          int | null
  }
  override_of:     entry_id | null          # set on manual_override rows
  supersedes_id:   entry_id | null          # revision chain (INV-2)
  user_note:       str | null
}
```

`summary` and `why_not` are **templated strings assembled from structured fields**, never model-generated text. A regulatory dossier must not contain prose whose provenance cannot be reconstructed deterministically.

### 3.4 Architecture — Rust-side writer (INV-1)

Python handlers that compute a decision return a `rationale_payload` block alongside their normal result. The **Rust command that persists the state change** deserializes it and calls the journal writer **inside the same `rusqlite` transaction** as the mutation.

New `src-tauri/src/journal.rs`:

```rust
pub struct JournalEntry { /* mirrors §3.3 */ }

/// Appends a journal row using the caller's open transaction.
/// Fails the whole transaction on error — the decision and its record
/// are all-or-nothing (INV-1).
pub fn append(tx: &rusqlite::Transaction, entry: &JournalEntry) -> Result<String, Error>;

/// Convenience for commands that don't already hold a transaction.
pub fn append_standalone(conn: &mut Connection, entry: &JournalEntry) -> Result<String, Error>;
```

Every instrumented command in §3.2 is refactored (where it isn't already) to wrap its mutation in an explicit transaction and call `journal::append` before commit.

Python's only journal-adjacent responsibility: emit a well-formed `rationale_payload` in its RPC response. Add `edeon_engine/journal_payload.py` with builders so payload construction is consistent across packages (`build_rationale(drivers, scores, thresholds)`, `build_alternatives(...)`).

### 3.5 SQLite migration

```sql
CREATE TABLE IF NOT EXISTS decision_journal (
  entry_id      TEXT PRIMARY KEY,
  project_id    TEXT NOT NULL,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  actor         TEXT NOT NULL CHECK (actor IN ('system','user')),
  decision_kind TEXT NOT NULL,
  subject_type  TEXT NOT NULL,
  subject_id    TEXT NOT NULL,
  summary       TEXT NOT NULL,
  rationale_json     TEXT,
  alternatives_json  TEXT,
  confidence_json    TEXT,
  provenance_json    TEXT NOT NULL,
  override_of   TEXT REFERENCES decision_journal(entry_id),
  supersedes_id TEXT REFERENCES decision_journal(entry_id),
  user_note     TEXT,
  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_journal_project_time  ON decision_journal(project_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_journal_subject       ON decision_journal(subject_type, subject_id);
CREATE INDEX IF NOT EXISTS idx_journal_kind          ON decision_journal(project_id, decision_kind);
CREATE INDEX IF NOT EXISTS idx_journal_override      ON decision_journal(override_of);
```

> No `UPDATE`/`DELETE` statements against this table anywhere in the codebase except the project cascade. Add a lint/test asserting this (grep-based test is acceptable and is a genuine safeguard).

### 3.6 Derived views

**Compound lineage** — for a compound, the ordered chain of every decision that touched it (registered → passed gates → analog of X → transform applied → proposed in BO batch → accepted → …). This is the "why did this candidate advance" narrative, reconstructed purely from the log. Query: all entries where `subject_id = c` OR the compound appears in an alternatives list OR in a batched gate row's id list. Store batched ids in `rationale_json.compound_ids` so this remains indexable.

**Override analytics** — how often did the user override the system, on what kinds of decisions, and (where a later measured/predicted outcome exists) **did the overrides turn out better?**
- Join `manual_override` rows to any subsequent outcome available for the same subject.
- Report: override rate by `decision_kind`; for overrides with a resolvable outcome, the sign and magnitude of the delta vs. the system's recommended alternative.
- **Report the honest version.** If the sample is small, say so (reuse the §2.6 reliability language). If overrides outperform, that is a signal the model or weights are miscalibrated — surface it as such rather than burying it. This panel is a calibration instrument aimed at the system, not a scorecard aimed at the user, and the copy must make that unambiguous.

### 3.7 JSON-RPC methods

Journal *writes* are Rust-only (§3.4). Python owns only the **derived analytics**, which read the log via a Rust-supplied payload:

```
journal.lineage
  params:  { "entries": [ ...DecisionEntry... ], "compound_id": str }
  returns: { "ok": true,
             "chain": [ { "entry_id": str, "created_at": str,
                          "decision_kind": str, "summary": str,
                          "role": "subject|alternative|batch_member" } ] }

journal.override_analytics
  params:  { "entries": [ ...DecisionEntry... ],
             "outcomes": [ { "subject_id": str, "endpoint": str, "value": float } ] }
  returns: { "ok": true,
             "override_rate_by_kind": { <kind>: {"n_overrides": int, "n_decisions": int, "rate": float} },
             "resolved": [ { "entry_id": str, "endpoint": str,
                             "user_choice_value": float,
                             "system_choice_value": float,
                             "delta": float } ],
             "n_resolved": int,
             "reliability": "ok|low|insufficient_data",
             "interpretation_hint": "model_may_be_miscalibrated | no_signal | system_aligned" }
```

### 3.8 Rust commands

`src-tauri/src/commands/journal.rs`:
- `journal_list(project_id, filters: {kind?, subject_type?, actor?, from?, to?}, limit, offset) -> Vec<DecisionEntry>`
- `journal_get(entry_id) -> DecisionEntry`
- `journal_lineage(project_id, compound_id) -> LineageChain` (fetches rows, delegates assembly to Python)
- `journal_override_analytics(project_id) -> OverrideAnalytics`
- `journal_add_note(entry_id, note)` — **the sole exception to append-only**: `user_note` is nullable-once-writable. Implement as a `supersedes` row rather than an in-place update if strict immutability is preferred; **prefer the supersedes route** and make the UI transparent about it.
- `journal_record_override(subject_type, subject_id, override_of, reason)` — called from UI when a user contradicts a recommendation.
- `journal_export(project_id, format: "csv"|"json") -> path`

Plus: extend `commands/export.rs` to add a **Decision Journal section** to the Environmental Fate Dossier and Project Workflow Summary PDFs (chronological table + per-candidate lineage for the top-ranked compounds).

### 3.9 Zustand deltas

New `src/store/journalStore.ts`:
- state: `entries`, `filters`, `pagination`, `lineage: Record<compoundId, LineageChain>`, `overrideAnalytics`
- actions: `list(filters)`, `get(id)`, `loadLineage(compoundId)`, `loadOverrideAnalytics()`, `addNote(id, note)`, `recordOverride(...)`, `exportJournal(format)`

**Cross-cutting UI contract:** any component presenting a system recommendation (`ProposalGrid`, `BottleneckCard`, `ResultsTable` ranking, `ArenaResultsView`, `TransformTable`) must call `journalStore.recordOverride` when the user takes a contradicting action. Add this to the component review checklist — an un-instrumented recommendation surface is a silent hole in the audit trail.

### 3.10 UI surface

| Component | File | Purpose |
|-----------|------|---------|
| `JournalView` | `src/views/JournalView.tsx` | New view (`ViewId: 'journal'`, sidebar entry, route in `App.tsx`). Filterable, paginated timeline of decisions. |
| `DecisionEntryCard` | `src/components/journal/DecisionEntryCard.tsx` | One entry: actor chip, kind badge, summary, expandable rationale (drivers table), alternatives with `why_not`, confidence (`UqBadge`/`ADWarning` reuse), provenance footer (`ReproducibilityInfo` reuse). |
| `LineageTimeline` | `src/components/journal/LineageTimeline.tsx` | Vertical chain for one compound; opens from `Inspector` and `CompoundDetailModal` ("Why is this here?"). |
| `OverrideAnalyticsPanel` | `src/components/journal/OverrideAnalyticsPanel.tsx` | Override rate by kind; resolved-outcome deltas; reliability chip; calibration-oriented copy per §3.6. |
| `JournalExportButton` | `src/components/journal/JournalExportButton.tsx` | CSV/JSON export; reuse `CitationExportButton` pattern. |

### 3.11 Acceptance criteria

- **INV-1 (atomicity):** a test that forces the caller's transaction to roll back after `journal::append` leaves **zero** rows in `decision_journal`. Conversely, a successful workflow completion writes exactly one `workflow_verdict` row. **This test gates the phase.**
- **INV-2 (append-only):** grep-based test asserts no `UPDATE decision_journal` / `DELETE FROM decision_journal` outside the project-cascade path. Adding a note creates a `supersedes` row; the original remains byte-identical.
- Every `decision_kind` in §3.2 has at least one emitting call site and an integration test that triggers it end-to-end.
- **Override capture:** rejecting a BO proposal, or promoting a compound the ranking placed below the cut, produces a `manual_override` row with `override_of` pointing at the system's recommendation entry.
- **Lineage:** for a compound that was generated → gated → transformed → BO-proposed → accepted, `journal_lineage` returns all five events in chronological order with correct `role` labels.
- **Override analytics:** with < 5 resolved overrides, `reliability="insufficient_data"` and the panel refuses to display a trend line. With a synthetic fixture where overrides systematically beat the system, `interpretation_hint="model_may_be_miscalibrated"`.
- **Determinism:** two identical workflow runs (same seed, same params) produce journal entries whose `summary`, `rationale_json`, and `params_hash` are identical. No non-deterministic prose anywhere in the table.
- **Dossier export:** the Project Workflow Summary PDF contains a Decision Journal section with the chronological table and lineage for the top-ranked compounds.
- Journal writes add < 5 ms to a workflow-completion commit (benchmark; it must never become a reason to skip instrumentation).

### 3.12 Ordered task list

**M1-CORE (build first — cross-cutting):**
1. `M1-T1` Migration `decision_journal` + indexes + append-only lint test.
2. `M1-T2` `src-tauri/src/journal.rs` — `JournalEntry`, `append(tx)`, `append_standalone`. Atomicity test (INV-1). **Close `GATE-M-CORE`.**
3. `M1-T3` `edeon_engine/journal_payload.py` — rationale/alternatives builders; templated `summary` + `why_not` catalogue (one template per `decision_kind`).

**M1-HOOKS (instrument call sites — one task per kind, parallelizable):**
4. `M1-T4` `workflow_verdict`, `compound_promoted`, `compound_rejected`, `parameter_changed` in `commands/workflow.rs`.
5. `M1-T5` `model_deployed`, `model_selected` in `commands/models.rs`.
6. `M1-T6` `analog_registered`, `transform_applied` in `commands/design.rs` + H2 apply-transform path.
7. `M1-T7` `tp_liability_flagged` in `commands/fate.rs`.
8. `M1-T8` `bo_batch_proposed`, `bo_proposal_accepted/rejected` in `commands/optimize.rs` (skip if K10 not built; leave the hook stub).
9. `M1-T9` `bottleneck_identified` in `commands/bottleneck.rs` (L1 dependency).
10. `M1-T10` `manual_override` — `journal_record_override` command + wire every recommendation surface listed in §3.9.

**M1-ANALYTICS + UI:**
11. `M1-T11` `journal.lineage` + `journal.override_analytics` Python handlers + tests.
12. `M1-T12` `commands/journal.rs` — list/get/lineage/analytics/note/export.
13. `M1-T13` Dossier PDF section in `commands/export.rs`.
14. `M1-T14` `journalStore` + `JournalView` + 5 components + `ViewId`/sidebar/route.
15. `M1-T15` Integration test `tests/integration/test_decision_journal.py` (covers every kind + lineage + override).

---

## 4. Master task manifest

| Order | Task ID | Phase | Blocking gate | Notes |
|------:|---------|-------|---------------|-------|
| 1 | M1-T1 … M1-T3 | M-CORE | — | schema + Rust writer + payload builders → **GATE-M-CORE** |
| 2 | L1-T1 … L1-T9 | L | — | analyzer core (Python + migration) |
| 3 | L1-T10 … L1-T12 | L | GATE-M-CORE | Rust + UI + journal emission → **GATE-L1** |
| 4 | M1-T4 … M1-T8 | M-HOOKS | GATE-M-CORE | instrument existing call sites |
| 5 | M1-T9 | M-HOOKS | GATE-L1 | bottleneck emission |
| 6 | M1-T10 | M-HOOKS | GATE-M-CORE | override capture across all recommendation surfaces |
| 7 | M1-T11 … M1-T15 | M-UI | M-HOOKS | analytics, view, dossier export |

**Definition of done (both features):** handlers registered; Rust commands + DTOs + capability; store + UI wired; unit + integration tests green; INV-1 and INV-2 tests green; base build unaffected (no new deps, no extras); existing test suite still passes; no `UPDATE`/`DELETE` on `decision_journal`.

---

## 5. Explicit non-goals

Recorded so scope creep is caught in review rather than in the diff:

- **No LLM or agent orchestration.** No component of either feature calls a language model. `summary` and `why_not` are templated from structured fields. The dossier must contain only text whose provenance is deterministically reconstructable.
- **No autonomous decisions.** The Bottleneck Analyzer *recommends*; it never advances, rejects, or re-weights anything on its own. `bottleneck.suggest_weights` produces a seed the user must accept in `CampaignSetup`.
- **No cross-project meta-learning.** Edeon is local-first and project-scoped. The journal is not a training corpus and is never aggregated across projects or users.
- **No "probability of success" scalar.** A single PoS number over an agrochem program would be false precision built on endpoints whose own calibration is the thing under question. The uncertainty-banded leverage profile is the honest version of the same information, and it is what ships.
