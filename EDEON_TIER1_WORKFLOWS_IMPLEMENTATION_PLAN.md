# Edeon Desktop — Tier 1 Pre-Made Workflows Implementation Plan

> Scope: four decision-grade, packaged workflows built **on top of** the existing
> F0–F5 capabilities (calibrated UQ+AD, selectivity, environmental fate, transformation
> products, registration-risk scorecard, prescriptive design).
> Architecture: a **backend-declarative orchestration layer** — each workflow is a recipe
> in a registry, not bespoke wiring. Reproducible, provenance-tracked, headless-capable.
> Author context: solo dev, evenings/weekends, public-data-only, local-first product.

---

## 0. Context — what these are and what they assume

You now have a **capability platform**. These workflows turn capabilities into
**recognizable jobs at named go/no-go gates**, each producing a *decision artifact*
(a verdict + a dossier + a ranked table), not a pile of numbers.

The four Tier 1 workflows and their personas:

| ID | Workflow | Decision gate | Persona | New capability needed |
|----|----------|---------------|---------|-----------------------|
| **W1** | Registration Readiness Pre-Screen | "Will this survive EU 1107/2009 + EFSA before we invest?" | Project lead / Reg. affairs | none (pure composition) |
| **W2** | Pollinator Safety Screen | "Is this a bee risk, and is it exposure-driven?" | Ecotox / Discovery | **systemicity estimator** (small, specced in §5) |
| **W3** | Transformation-Product Liability Sweep | "My parent is clean — are its breakdown products?" | Env. fate / Reg. | none (pure composition) |
| **W4** | Lead-Optimization Cycle | "What do I make next to fix the liability?" | Agro chemist (daily) | none (composition + ranking) |

**Assumed engine methods already implemented (from the F0–F5 plan):**
`standardize`, `compute_properties`, `pesticide_likeness`, `selectivity` (with bee,
daphnia, fish, bird, earthworm, mammal endpoints), `environmental_fate`,
`transformation_products`, `registration_risk`, `suggest_analogs` — each returning the
F0 **envelope** `{value, lower, upper, coverage, ad_status, ad_score, model_id}`.

---

## 1. The workflow framework (build this once, reuse 4×)

### 1.1 Orchestration model

A workflow is a **declarative recipe**: an ordered list of steps, each calling an
existing engine method, plus an **aggregator** that turns step outputs into a verdict +
dossier sections. Logic lives in Python (`workflows/` package); the frontend only
configures, triggers, streams progress, and renders the artifact. Benefits: one place to
version each recipe, testable in isolation, and the *same* recipe runs headless for large
libraries (future "engine" licensing line).

### 1.2 Data contracts (define in `edeon_engine/workflows/contracts.py`)

```python
@dataclass
class WorkflowSpec:
    id: str                      # "registration_readiness"
    name: str                    # "Registration Readiness Pre-Screen"
    persona: str                 # "Regulatory affairs / project lead"
    input_kind: str              # "single" | "series" | "library"
    default_params: dict         # opinionated defaults (UI renders these)
    steps: list[Step]
    aggregator: Callable         # (step_outputs, params) -> WorkflowResult
    report_template: str         # printpdf template id

@dataclass
class Step:
    name: str                    # "environmental_fate"
    method: str                  # JSON-RPC method to call
    applies_to: str              # "parent" | "each_compound" | "each_tp"
    params: dict                 # may reference prior outputs via "$step.field"
    on_fail: str = "warn"        # "warn" | "abort" | "skip"

@dataclass
class Verdict:
    band: str                    # "GO" | "CONDITIONAL" | "NO_GO"  (or risk bands)
    driver: str                  # the binding criterion, in plain language
    confidence: str              # "high" | "moderate" | "low"  (driven by AD/CI)
    rationale: str

@dataclass
class WorkflowResult:
    workflow_id: str
    per_compound: list[dict]     # rows: key metrics (envelopes) + flags + Verdict
    overall: Verdict | None      # for single/series-level calls
    sections: dict               # structured blocks for the dossier
    warnings: list[str]          # OOD compounds, data-gap endpoints, disclaimers
    provenance: dict             # see §1.6
```

### 1.3 The confidence-aware verdict rule (the trust moat at workflow level)

A verdict must **never** be falsely confident. Encode this once and apply in every
aggregator:

1. If a **showstopper criterion** is triggered **and** its inputs are `in_domain` →
   `NO_GO`, `confidence = high`.
2. If a showstopper would trigger but key inputs are `out_of_domain` **or** intervals
   straddle the threshold → **do not** emit GO/NO_GO; emit `CONDITIONAL`,
   `confidence = low`, `driver = "insufficient model coverage — measured data needed"`.
3. All criteria clear, in-domain → `GO`, `confidence = high`.
4. Watch-level (near threshold, in-domain) → `CONDITIONAL`, `confidence = moderate`.
5. Confidence is the *minimum* across the binding criteria's AD/CI quality, never an
   average. One OOD showstopper caps the whole verdict's confidence.

This rule is what separates Edeon from a black box: a sophisticated buyer trusts a tool
that says "I can't tell you yet, get data" over one that bluffs.

### 1.4 Generic JSON-RPC (no per-workflow methods)

```jsonc
// discover available workflows (UI renders the gallery from this)
{"id":1,"method":"list_workflows","params":{}}
// -> [{id, name, persona, input_kind, default_params, step_names}]

// run any workflow
{"id":2,"method":"run_workflow","params":{
   "workflow_id":"registration_readiness",
   "input":{"smiles":["..."], "efficacy":{...optional...}},
   "params":{...overrides of default_params...}}}
// streams progress events, then returns WorkflowResult
```

Progress event (reuse existing `workflow://progress` channel), now step-aware:
```jsonc
{"workflow_id":"...","step":"transformation_products","applies_to":"each_compound",
 "done":120,"total":500,"overall_fraction":0.42,"label":"Screening TPs (120/500)..."}
```

### 1.5 Rust / Zustand / UI / SQLite contracts

- **Rust** (`commands/workflow.rs`): add `list_workflows` and `run_named_workflow`
  (forwards to the sidecar `run_workflow`, relays progress, persists `WorkflowResult`,
  honors the existing `cancelled_workflows` set). The legacy 6-stage `start_workflow`
  stays; new workflows go through `run_named_workflow`.
- **Zustand** (`workflowStore.ts`): generalize `selectedWorkflowType` → `selectedWorkflowId`;
  add `availableWorkflows`, `workflowParams`, `runWorkflow()`, `workflowResult`.
- **UI** — four surfaces, reused by all workflows:
  1. **Workflow Gallery** (`views/WorkflowGalleryView.tsx`, NEW): cards grouped by
     persona, populated from `list_workflows`. This is the product's "what can Edeon do
     for me" front door.
  2. **Config panel**: reuse `WorkflowRunConfig.tsx`; render param controls from the
     selected spec's `default_params` schema.
  3. **Pipeline progress**: reuse `Pipeline.tsx`/`PipelineStage.tsx`; stages = the
     workflow's `steps`.
  4. **Decision Artifact view** (`components/workflow/DecisionArtifact.tsx`, NEW):
     a traffic-light **verdict header**, dossier `sections`, a results table
     (`ResultsTable.tsx` extended with the workflow's key columns + verdict badge),
     and an **"Export Dossier"** button.
- **SQLite** (migration `v6`): add to `workflows` / `workflow_results`:
  `workflow_id TEXT`, `params_json`, `verdict_json`, `provenance_json`.
  TP child rows already exist in `transformation_products` (v5).

### 1.6 Provenance manifest (cheap here, high-trust)

Every run stores a reproducibility manifest in `provenance_json`:
```jsonc
{"edeon_version":"...","workflow_id":"...","workflow_version":"1.0",
 "params":{...}, "model_ids":{"bee_oral":"v3","dt50_soil":"v2",...},
 "data_versions":{"ecotox":"2026-03","opera":"2.9",...},
 "run_utc":"2026-...","input_hash":"sha256:..."}
```
This makes any verdict re-creatable — essential for regulated R&D and a real trust signal.

### 1.7 Methodology standards (inherited, restated)

- Confidence-aware verdicts (§1.3) — mandatory in every aggregator.
- **"Screening, not a regulatory/safety determination"** banner on every W1/W2/W3 artifact.
- **Data-gap honesty**: where an endpoint has thin public data (crop phytotox;
  systemicity is an estimate), surface it in `warnings`, never hide it.
- All numbers carry their F0 envelope through to the UI and the dossier.

---

## 2. Repository layout (new files)

```
python/edeon_engine/workflows/
  __init__.py
  contracts.py            # WorkflowSpec, Step, Verdict, WorkflowResult
  registry.py             # REGISTRY: dict[id -> WorkflowSpec]; list_workflows()
  runner.py               # run_workflow(): executes steps, streams progress, aggregates
  verdict.py              # the §1.3 confidence-aware verdict helper
  provenance.py           # manifest builder
  w1_registration.py      # W1 spec + aggregator
  w2_pollinator.py        # W2 spec + aggregator
  w3_tp_liability.py      # W3 spec + aggregator
  w4_lead_opt.py          # W4 spec + aggregator
  systemicity.py          # W2 prerequisite (Briggs/Kleier) — §5

src/
  views/WorkflowGalleryView.tsx          (NEW)
  components/workflow/DecisionArtifact.tsx (NEW)
  components/workflow/VerdictHeader.tsx    (NEW)
  components/fate/PathwayTree.tsx          (reuse from F3 for W3)
  components/design/AnalogGrid.tsx         (reuse from F5 for W4)

src-tauri/src/commands/workflow.rs         (extend: list_workflows, run_named_workflow)
```

---

## 3. Cross-workflow task: build the framework first

**T0 — Framework (blocks everything below)**
1. `contracts.py`, `registry.py`, `verdict.py`, `provenance.py`.
2. `runner.py`: iterate steps; resolve `$step.field` references; apply `applies_to`
   fan-out (parent / each_compound / each_tp) with joblib threads; emit step-aware
   progress; call aggregator; attach provenance + warnings.
3. JSON-RPC `list_workflows`, `run_workflow` in `__main__.py`.
4. Rust `list_workflows`, `run_named_workflow`; migration `v6`.
5. UI: `WorkflowGalleryView`, `VerdictHeader`, `DecisionArtifact` shell;
   generalize `workflowStore`.
6. **Gate:** a trivial 1-step demo workflow runs end-to-end (gallery → config →
   progress → verdict artifact → persisted with provenance).

---

## 4. Workflow specifications

For each: persona/sales framing · input · step sequence · verdict logic ·
decision artifact · UI specifics · acceptance criteria.

---

### W1 — Registration Readiness Pre-Screen

**Sales framing.** The highest-value workflow: it sits at the most expensive gate in
agro — *before* field trials and the tox package. Reframes Edeon as a registration-risk
early-warning system. Sell to project leads and regulatory affairs.

**Input.** `single` or small `series` (advanced candidates). Optional measured efficacy.

**Steps.**
| # | Step (method) | applies_to | Defaults | Produces |
|---|---------------|------------|----------|----------|
| 1 | `standardize` | each_compound | — | clean structures |
| 2 | `environmental_fate` | each_compound | — | DT50, Koc, GUS, BCF, Kow, PBT(P/B/T) |
| 3 | `transformation_products` | each_compound | depth=2, routes=[abiotic,metabolic] | TP DAG |
| 4 | `environmental_fate` + `selectivity`(tox subset) | each_tp | mammal+aquatic | TP fate/tox |
| 5 | `selectivity` | each_compound | full panel | non-target tox (for T + CLP) |
| 6 | `registration_risk` | parent **and** worst_tp | EU 1107/2009 + CLP + REACH XIII | scorecard |

**Verdict logic (aggregator).** Per the §1.3 rule, over criteria {PBT/vPvB, groundwater
0.1 µg/L, ED screening alert, genotox alert, aquatic CLP, acute mammal CLP}. Additional:
if a **TP** introduces a showstopper absent in the parent → set
`driver="metabolite-driven risk"` and surface that TP. Overall band per compound:
`GO | CONDITIONAL | NO_GO`.

**Decision artifact — "Registration Readiness Dossier".** Exec-summary verdict;
per-criterion **scorecard for parent + worst TP** (status pill, evidence, source ref,
confidence); fate summary; TP call-out; warnings + screening disclaimer.
Results-table columns: `Reg verdict` badge, binding criterion, confidence.

**UI.** Reuse `Scorecard` (F4) inside `DecisionArtifact`; verdict header traffic-light.

**Acceptance.**
- Known PBT active → `NO_GO` (in-domain), correct binding criterion named.
- Known clean active → `GO`.
- Parent with a known problematic metabolite → `CONDITIONAL/NO_GO` with
  `metabolite-driven risk` driver.
- OOD showstopper → `CONDITIONAL`, `confidence=low`, never a false GO.
- Screening disclaimer present on the dossier.

---

### W2 — Pollinator Safety Screen

**Sales framing.** Topical, EFSA-driven, a genuine product-killer in the EU. The
differentiator vs. a naive "bee LD50" tool: it weighs **intrinsic bee toxicity against
exposure potential via systemicity** — a systemic bee-toxic compound (nectar/pollen/
guttation exposure) is categorically worse than a contact-only one. Sell to ecotox/safety.

**Input.** `series` or `library`.

**Prerequisite.** The **systemicity estimator** (§5) — small, public-physchem, no
proprietary data.

**Steps.**
| # | Step (method) | applies_to | Defaults | Produces |
|---|---------------|------------|----------|----------|
| 1 | `standardize` | each_compound | — | clean structures |
| 2 | `selectivity` (bee subset) | each_compound | oral + contact LD50 | bee tox envelopes |
| 3 | `systemicity` | each_compound | Briggs/Kleier | phloem/xylem mobility index |
| 4 | aggregate → **pollinator-risk index** | each_compound | tox × exposure | risk band + driver |

**Verdict logic.** `index = f(bee_tox_hazard, systemicity_exposure)`:
high tox × high systemicity → **High** (exposure-driven); high tox × low systemicity →
**Med** (contact-route-driven); low tox → **Low**. `driver` names whether risk is
tox-driven or exposure-driven. OOD on either input downgrades confidence (§1.3).

**Decision artifact — "Pollinator Safety Report".** Ranked table by pollinator-risk
index (bee oral, bee contact, systemicity, risk band, driver, AD/CI); per-compound card
explaining the driver; warnings (larval-tox data gap if applicable) + screening disclaimer.

**UI.** Heatmap-style risk column; sortable by index; driver chip (tox vs exposure).

**Acceptance.**
- Systemic bee-toxic neonicotinoid → **High**, driver = exposure.
- Contact-only bee-toxic, non-systemic → **Med**, driver = contact route.
- Bee-safe compound → **Low**.
- Systemicity estimator validated against a panel of known systemic vs. contact actives.
- OOD downgrades confidence.

---

### W3 — Transformation-Product Liability Sweep

**Sales framing.** Your differentiator as a one-click job: clean parents die late on
ugly metabolites. Almost nobody packages *predict TPs → re-score TPs through fate+tox →
flag the ones worse than the parent.* Sell to environmental-fate and regulatory teams.

**Input.** `single` or `series`.

**Steps.**
| # | Step (method) | applies_to | Defaults | Produces |
|---|---------------|------------|----------|----------|
| 1 | `standardize` | each_compound | — | clean structures |
| 2 | `transformation_products` | each_compound | depth=2, both routes, prob≥cutoff | TP DAG |
| 3 | `environmental_fate` | each_tp | — | TP persistence/mobility/BCF |
| 4 | `selectivity` (tox subset) | each_tp | aquatic+mammal+bee | TP tox |
| 5 | aggregate → **Δ vs parent** per axis | per TP | thresholds | liability flags |

**Verdict logic.** A TP is flagged if it exceeds the parent on a regulated axis beyond
threshold **and** its formation probability ≥ cutoff. Rank flagged TPs by
`severity × formation_likelihood`. Compound-level band: `clean` / `parent-OK-TP-liability`
/ `parent-liability`.

**Decision artifact — "Transformation-Product Liability Report".** `PathwayTree` (F3)
+ TP table (route, probability, fate/tox Δ vs parent, flag) + a headline **"worst TP"**
call-out. Warnings + disclaimer.

**UI.** Reuse `PathwayTree.tsx`; "Problem TP?" column in results.

**Acceptance.**
- Reference pesticides with known problematic metabolites → those TPs flagged.
- Clean references → no false flags.
- Probability cutoff demonstrably filters noise (sensitivity check).

---

### W4 — Lead-Optimization Cycle

**Sales framing.** The daily-habit, subscription-justifying loop: from *diagnosis* to
*prescription*. "Here's your series' worst liability, and here are the next molecules to
make that fix it without losing efficacy." Sell to the agro chemist.

**Input.** `series` + `objective` (improve, e.g., `bee_margin`) + `preserve`
(e.g., `target_efficacy`). If `objective` omitted, auto-detect the series' dominant liability.

**Steps.**
| # | Step (method) | applies_to | Defaults | Produces |
|---|---------------|------------|----------|----------|
| 1 | `standardize` | each_compound | — | clean structures |
| 2 | `selectivity`+`environmental_fate`+`registration_risk` | each_compound | — | full profile |
| 3 | detect worst liability | series | per-axis ranking | objective (if auto) |
| 4 | `suggest_analogs` | each_compound | improve=objective, preserve=preserve, n | analog set |
| 5 | `selectivity`+`environmental_fate`+`registration_risk` | each_analog | — | analog profiles |
| 6 | rank analogs (multi-objective) | analog set | maximize Δobjective s.t. preserve, in-domain | ranked proposals |

**Verdict / ranking logic.** Rank by improvement in the objective **subject to**
preserving the `preserve` axes within tolerance; **penalize OOD** analogs (gate them
behind a toggle, never surface OOD as a confident win); explicitly flag any analog that
improves the target but **worsens another regulated axis** ("no free lunch"). No
GO/NO_GO band here — output is a *ranked make-list* with predicted deltas + confidence.

**Decision artifact — "Optimization Proposal".** Parent-series summary (dominant
liability) + `AnalogGrid` (F5): structure, transformation applied, per-axis Δ with
arrows, intervals, AD badge, trade-off flags + **"Add selected to library"**.

**UI.** Reuse `AnalogGrid.tsx`; in-domain-only toggle default ON; objective override
dropdown.

**Acceptance.**
- On a known SAR series, recovers a real improving modification.
- Trade-offs surfaced (improves bee margin, flags a fate worsening).
- OOD analogs gated, not shown as confident wins.
- End-to-end runtime within a usable budget for a typical series (define a target, e.g.,
  ≤ a few minutes for ~20 leads × n analogs).

---

## 5. Prerequisite sub-feature for W2 — Systemicity estimator

**Why.** W2's value depends on exposure context. Build a small, honest estimator from
**published physicochemical rules** (no proprietary data).

**Method.** Phloem/xylem mobility from `log Kow` + `pKa` (acid/base):
- **Briggs/Kleier**-style phloem-mobility model → a mobility index (e.g., the classic
  "intermediate lipophilicity + weak acid" phloem-mobility window).
- Output: `{systemicity_index, route: "phloem|xylem|contact", envelope}` with the F0
  AD/CI treatment (here AD = physchem-range applicability), and a **clear "estimate,
  not measurement"** flag.

**Module.** `workflows/systemicity.py`; JSON-RPC method `systemicity`.

**Acceptance.** Reproduces the known systemic-vs-contact classification on a reference
panel; flags out-of-range inputs; estimate caveat surfaced.

> Note: systemicity is independently useful beyond W2 (it's a roadmap "agro-native
> bioavailability" signal) — building it here pays off across the product.

---

## 6. Phased task manifest (sequenced by value × buildability)

**Phase 0 — Framework** *(T0, blocks all)* → gate in §3.

**Phase 1 — W1 Registration Readiness** *(pure composition, highest value)*
- 1.1 `w1_registration.py` spec + aggregator (uses confidence-aware verdict).
- 1.2 Wire parent + worst-TP `registration_risk`; metabolite-driven-risk logic.
- 1.3 "Registration Readiness Dossier" printpdf template.
- 1.4 Gallery card + DecisionArtifact wiring.
- **Gate:** W1 acceptance criteria pass on the control set.

**Phase 2 — W3 TP Liability Sweep** *(pure composition, differentiator)*
- 2.1 `w3_tp_liability.py` spec + Δ-vs-parent aggregator + ranking.
- 2.2 Report template; PathwayTree reuse.
- **Gate:** W3 acceptance criteria pass.

**Phase 3 — W2 Pollinator Safety** *(adds systemicity)*
- 3.1 `systemicity.py` (§5) + method + validation panel.
- 3.2 `w2_pollinator.py` spec + tox×exposure index + driver logic.
- 3.3 Pollinator Safety Report template.
- **Gate:** W2 + systemicity acceptance criteria pass.

**Phase 4 — W4 Lead-Optimization Cycle** *(most complex orchestration)*
- 4.1 Worst-liability auto-detection; multi-objective analog ranking with OOD gating.
- 4.2 `w4_lead_opt.py` spec + aggregator; AnalogGrid reuse; "Add to library".
- 4.3 Optimization Proposal artifact.
- **Gate:** W4 acceptance criteria pass; runtime within target.

**Cross-cutting — validation evidence**
- Each workflow ships a short **"how it decides" methodology note** (criteria, thresholds,
  data versions, disclaimers). These notes double as demo scripts and EuroQSAR material,
  and as the per-workflow page in your sales one-pager.

---

## 7. Why this structure pays off commercially

- **Demo = workflow.** Each Tier 1 workflow is a self-contained 3–5 minute demo with a
  punchy verdict at the end — far more persuasive than touring features.
- **Pricing/persona mapping.** Workflows map onto buyers (W1→regulatory, W2→ecotox,
  W4→discovery), giving you natural module/tier boundaries later.
- **Headless reuse.** Because orchestration is backend + declarative, the identical
  recipes run batch/headless on large libraries — the basis for a future "Edeon engine"
  offering without rebuilding anything.
- **Trust compounds.** The confidence-aware verdict (§1.3) and provenance manifest
  (§1.6) are what let a sophisticated buyer act on an Edeon verdict — the moat, expressed
  at the level of the decision rather than the individual prediction.
