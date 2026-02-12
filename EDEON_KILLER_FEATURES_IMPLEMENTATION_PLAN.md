# Edeon Desktop — Killer Features Implementation Plan

> Target: production-grade commercial differentiators for agrochemical lead optimization.
> Scope: 5 feature tracks + 1 cross-cutting trust foundation, slotted into the existing
> Tauri v2 (Rust) ⇄ Python `edeon_engine` (JSON-RPC) ⇄ React/Zustand architecture.
> Author context: solo developer, evenings/weekends, self-funded, public-data-only.

---

## 0. Context & how this maps to what already exists

This plan does **not** rebuild Edeon. It extends the current 6-stage workflow
(`standardize → properties → pesticide-likeness → selectivity → resistance → MPO`),
the QSAR Modeling Studio (`models/`), the offline knowledge browser
(`knowledge.py` over PPDB/ECOTOX/OpenFoodTox), the printpdf report templates
(notably the existing **Environmental Fate Dossier** and **Selectivity Chartbook**),
and the existing AD machinery in `validation.py`.

The thesis (established earlier): Edeon's moat is **seeing the agro-specific failure
modes pharma tools are blind to — non-target selectivity, environmental fate &
metabolites, and registration cut-offs — early and *credibly*.** "Credibly" is the
operative word and the reason F0 below comes first.

The five feature tracks, in dependency order:

| ID | Feature | Anchor | Builds on |
|----|---------|--------|-----------|
| **F0** | Calibrated uncertainty + applicability domain on *every* prediction | Foundation | `validation.py`, calibration split |
| **F1** | Cross-species selectivity (hardened + validated) | Anchor 1 | `toxicity.py`, `selectivity` method, Inspector 2×2 grid |
| **F2** | Environmental fate — parent compound | Anchor 2a | `knowledge.py`, Environmental Fate Dossier |
| **F3** | Transformation products + their fate/tox | Anchor 2b | F2, new pathway engine |
| **F4** | Registration-risk scorecard | Anchor 3 | F1+F2+F3 + structural alerts |
| **F5** | Prescriptive design (MMP / bioisostere) | Stickiness | F1–F4 prediction stack |

---

## 1. Methodology standards (non-negotiable across all tracks)

These are the rules that make the difference between "a demo" and "a tool an agro
computational chemist will stake a project decision on." Every feature must obey them.

1. **No bare point estimates.** Every predicted number returns
   `{value, lower, upper, coverage, ad_status, ad_score}`. Implemented once in F0,
   consumed by F1–F5.
2. **Conformal calibration.** Prediction intervals (regression) and calibrated
   probabilities/sets (classification) via split-conformal prediction on a dedicated
   calibration partition — never the training or test fold.
3. **Applicability domain on every prediction.** k-NN Tanimoto distance to the
   training set; status = `in_domain | borderline | out_of_domain` against a threshold
   derived from the training NN-distance distribution (e.g., 95th percentile).
4. **Scaffold-stratified splits** (Bemis–Murcko, already in `splitters.py`) for all
   reported performance — never random splits in any commercial-facing benchmark.
5. **Mandatory negative controls** in any validation we publish or ship as evidence:
   Y-scrambling (already present) + a decoy/temporal split where feasible.
6. **"Screening flag, not determination" framing** for all regulatory/tox outputs in
   UI, reports, and tooltips. Legal/credibility protection — these are *in-silico
   triage signals*, not regulatory conclusions.
7. **Commercial-clean data only by default.** Any dataset/tool under a non-commercial
   or share-alike license is either (a) replaced by a public-domain equivalent,
   (b) used only to *train* a model whose weights we own (check the specific license),
   or (c) gated behind a documented commercial-license dependency. See §6.

---

## 2. Architecture overview — how new code slots in

No architectural change. Each feature is:

- **Python**: a new module under `edeon_engine/` (or `models/`) + one or more
  registered JSON-RPC methods in `__main__.py`, parallelized with the existing
  `joblib.Parallel(prefer="threads")` pattern where per-compound work dominates.
- **Rust**: a thin command in a new/existing `commands/*.rs` module that forwards
  params to the sidecar via the existing `send_request_with_app` dispatch and emits
  `*://progress` events for long runs (reuse the chunking pattern from the library-prep
  workflow).
- **Zustand**: either extend `workflowStore` (for pipeline-integrated features) or add
  a focused store (e.g., `fateStore`, `regulatoryStore`, `designStore`).
- **SQLite**: additive migrations (`v4`, `v5`, …) following the existing
  `db.rs` migration pattern; large/variable payloads as `*_json` blobs on
  `workflow_results`, structured child rows in new tables where you need to query them.
- **UI**: new column(s) in `ResultsTable.tsx`, new panel(s) in `Inspector.tsx`,
  optionally a new top-level View; charts via Recharts; structures via the existing
  RDKit-SVG `StructureViewer.tsx`; reuse `RiskBadge.tsx`.
- **Reports**: extend the printpdf templates in `commands/export.rs`.

### Shared prediction envelope (define once, in `edeon_engine/uq.py`)

```jsonc
// every endpoint returns this shape
{
  "value": 4.82,            // point estimate (e.g., pLD50, log DT50)
  "lower": 4.10,            // conformal interval lower bound
  "upper": 5.54,            // conformal interval upper bound
  "coverage": 0.90,         // nominal coverage of the interval
  "ad_status": "in_domain", // in_domain | borderline | out_of_domain
  "ad_score": 0.71,         // max Tanimoto to k nearest training cpds (0..1)
  "model_id": "bee_oral_v3" // provenance
}
```

---

## 3. Repository layout (new/changed files)

```
python/edeon_engine/
  uq.py                  # F0: conformal + AD wrappers (NEW)
  selectivity.py         # F1: rework existing selectivity into validated module (REWORK)
  fate/                  # F2 (NEW package)
    __init__.py
    parent_fate.py       #   DT50, Koc, GUS, BCF, Kow, Henry, PBT logic
    fate_models/         #   bundled trained models (.pkl/.onnx) + calibration sets
  transformation/        # F3 (NEW package)
    __init__.py
    rules.py             #   curated SMARTS/SMIRKS abiotic + agro rules (OWNED)
    cts_client.py        #   optional EPA CTS API client
    sygma_adapter.py     #   metabolite enumeration via SyGMa (check license)
    pathway.py           #   builds parent→TP DAG, dedup, depth control
  regulatory/            # F4 (NEW package)
    __init__.py
    alerts.py            #   Benigni-Bossa / ED / PAINS-style SMARTS (reimplemented)
    cutoffs.py           #   EU 1107/2009 + CLP + REACH PBT/vPvB numeric logic
    scorecard.py         #   assembles the per-criterion verdict
  design/                # F5 (NEW package)
    __init__.py
    mmp.py               #   mmpdb query wrapper
    bioisostere.py       #   replacement rules (owned/SwissBioisostere-gated)
    optimize.py          #   enumerate → re-predict full stack → rank

src/
  stores/fateStore.ts          (NEW)  src/stores/regulatoryStore.ts (NEW)
  stores/designStore.ts        (NEW)
  views/FateView.tsx           (NEW)  views/RegulatoryView.tsx      (optional NEW)
  components/uq/UqBadge.tsx     (NEW)  components/uq/IntervalBar.tsx (NEW)
  components/fate/PathwayTree.tsx (NEW)
  components/regulatory/Scorecard.tsx (NEW)
  components/design/AnalogGrid.tsx    (NEW)

src-tauri/src/commands/
  fate.rs  regulatory.rs  design.rs   (NEW)
```

---

## 4. Feature specifications

---

### F0 — Calibrated Uncertainty + Applicability Domain (the trust foundation)

**Commercial value.** This *is* the moat. A confident number with no interval and no
"is this molecule even in scope?" flag is negative value to this audience — they will
catch it and dismiss the tool. An honest interval + AD flag is what they bet on.

**Science / method.**
- *Regression* (DT50, Koc, BCF, pLD50, pEC50): **split-conformal prediction** with a
  normalized nonconformity score `|y − ŷ| / σ̂(x)` where `σ̂` is a learned difficulty
  estimate (e.g., k-NN residual or a second model). Produces per-compound intervals at
  a chosen coverage (default 90%).
- *Classification* (tox category, leacher y/n): **Venn–Abers** for calibrated
  probabilities, or conformal prediction sets for multiclass.
- *AD*: store training-set Morgan fingerprints per model; at predict time compute mean
  Tanimoto to k (=5) nearest neighbors; threshold from the training NN-distance
  distribution. Optionally add descriptor-space leverage (hat value) as a second signal.

**Libraries.** `MAPIE` (sklearn-native conformal) or `crepes` (lightweight conformal
regression/classification); `venn-abers` package for VA. All permissively licensed —
**verify each version's license at integration time**.

**Data.** None external — derived from each model's own calibration partition (you
already mandate one).

**Python / JSON-RPC.** No new top-level method; F0 wraps existing predictors. Add to
`uq.py`:
```python
def conformalize(model, X_calib, y_calib) -> ConformalWrapper
def predict_with_uq(wrapper, X, train_fps) -> list[Envelope]  # see §2 envelope
```
Persist each shipped model alongside its calibration residuals + training fingerprints.

**Rust.** None new — envelopes flow through existing workflow result payloads.

**Zustand.** Extend result types to carry the envelope; no new store.

**UI.**
- `UqBadge.tsx`: a compact AD pill (green/amber/red) reusing `RiskBadge` styling.
- `IntervalBar.tsx`: a tiny horizontal interval glyph (Recharts or raw SVG) showing
  value ± band inline in tables.
- `ResultsTable.tsx`: OOD rows get a subtle red left-border; sort/filter by AD status.
- `Inspector.tsx`: every numeric property shows `value [lower–upper]` + AD badge +
  tooltip explaining coverage and domain.

**SQLite.** Migration `v4`: add `uq_json` to `workflow_results`; store calibration
metadata in `saved_models` (extend existing `provenance`/`cv_results` columns).

**Acceptance criteria.**
- On a held-out **scaffold** split, empirical interval coverage ≈ nominal (90% ± a few %).
- AD status monotonically tracks error: OOD compounds show materially larger mean
  residuals than in-domain.
- Every UI surface that shows a prediction also shows its interval + AD badge.

---

### F1 — Cross-Species Selectivity (hardened & validated) — Anchor 1

**Commercial value.** The headline differentiator: pest efficacy vs. crop, pollinator,
aquatic, avian, earthworm, mammal — the question pharma tools don't ask.

**Science / method.**
- One calibrated endpoint model per non-target species (regression on
  pLD50 / pEC50 / pLC50, or EU/EPA category classification). Reuse the Modeling Studio
  pipeline (featurizers → scaffold CV → Optuna → F0 conformalization).
- **Selectivity Index (SI)** per non-target = `pActivity_target − pToxicity_nontarget`
  in log units. **Worst-case margin** = `min(SI over all non-targets)` → the headline
  sortable metric.
- *Target efficacy* is the data-hard part (see below). Support two modes:
  (a) **user-supplied** measured/assay potency (most defensible — agro teams have this),
  (b) **predicted** target potency where ChEMBL agro-target data exists (ALS, EPSPS,
  ACCase, AChE, nAChR, SDH, CYP51, etc.), clearly flagged as predicted.
- Propagate F0 intervals through the SI via Monte-Carlo over the two distributions.

**Data sources (per endpoint).**
| Endpoint | Source | License note |
|----------|--------|--------------|
| Honeybee (oral/contact LD50) | **ApisTox** curated dataset; ECOTOX | verify ApisTox license |
| Aquatic (Daphnia EC50, fish LC50, algae) | **EnviroTox**; ECOTOX | EnviroTox free, cite |
| Avian (quail/mallard LD50/LC50) | ECOTOX | public domain |
| Earthworm (*E. fetida*) | ECOTOX | public domain |
| Mammalian acute oral LD50 | **EPA T.E.S.T.**; OpenFoodTox; ToxValDB | public / open |
| Crop phytotoxicity | **sparse public data — honest gap**; user data mode | flag clearly |
| Target efficacy | ChEMBL agro targets (predicted) or user assay data | ChEMBL CC BY-SA |

**Python / JSON-RPC.** Rework `selectivity` method; back it with `selectivity.py`:
```jsonc
// request
{"id":1,"method":"selectivity","params":{
   "smiles":["..."], "target_potency":{"mode":"user|predicted","values":[...]},
   "endpoints":["bee","daphnia","fish","bird","earthworm","mammal"]}}
// result: per compound → per endpoint envelope + SI envelope + worst_case_margin
```
Parallelize across compounds with joblib threads.

**Rust.** Already wired through the workflow `selectivity` stage; extend payload only.

**Zustand.** Extend `workflowStore` selectivity result type with per-endpoint envelopes
and `worstCaseMargin`.

**UI.**
- `Inspector.tsx`: upgrade the existing 2×2 grid to a **species × endpoint heatmap**,
  cells colored by margin (safe/marginal/risk) and *shaded by AD* (hatched if OOD).
- `ResultsTable.tsx`: sortable **Selectivity Index** column (worst-case margin) + badge.
- Per-compound **Selectivity Profile** (Recharts bar chart): predicted non-target
  toxicities with the target-potency line overlaid; margins annotated; intervals drawn.
- Wire real data + methodology + AD/CI into the existing **Selectivity Chartbook** report.

**SQLite.** Migration `v4`: `selectivity_json` on `workflow_results`.

**Acceptance criteria.**
- Each endpoint model passes scaffold-split validation with reported metrics in a model
  card; conformal coverage holds.
- Positive controls behave correctly (e.g., a neonicotinoid scores a *poor* bee margin;
  a selective herbicide scores a *good* mammalian margin).
- Crop-phytotox limitation is explicitly surfaced, not hidden.

---

### F2 — Environmental Fate (parent compound) — Anchor 2a

**Commercial value.** Where agro compounds die late and expensively: persistence,
leaching, bioaccumulation. Speaks directly to registration-driven buyers.

**Science / method.**
- **Soil DT50** (degradation half-life): regression, heteroscedastic where possible
  (mean + variance → feeds F0 naturally). **Koc** (soil sorption): regression.
  **BCF** (bioconcentration): regression. **log Kow**: RDKit Crippen as a baseline,
  upgrade to a trained model. **Henry's law / volatility**: estimable.
- **GUS leaching index** = `log10(DT50_soil) × (4 − log10(Koc))` → classify
  leacher / transitional / non-leacher. Pure formula on top of the two models.
- **PBT / vPvB** assessment: apply REACH Annex XIII numeric thresholds to predicted
  P (DT50), B (BCF/Kow), T (chronic ecotox from F1) → P/B/T booleans + overall verdict.

**Data sources.**
| Endpoint | Source | License note |
|----------|--------|--------------|
| Koc, BCF, ready biodegradability, fish biotransformation t½ | **EPA OPERA** models/datasets | **public domain — commercial-safe; prefer this** |
| Soil DT50 (and water/photolysis DT50) | PPDB/BPDB; EFSA dossiers | **PPDB commercial use needs AERU permission — flag** |
| Aquatic chronic tox (for T) | EnviroTox / ECOTOX | free / public |
| log Kow reference | OPERA, PHYSPROP-derived sets | public |

> **Strategic note:** lean on **OPERA** (EPA, public domain) as the commercial-clean
> backbone for Koc/BCF/biodegradation. Use PPDB to *augment/validate* DT50 but resolve
> its commercial-license status before bundling.

**Python / JSON-RPC.** New `fate/parent_fate.py`; method:
```jsonc
{"id":1,"method":"environmental_fate","params":{"smiles":["..."]}}
// result per compound: {dt50_soil, koc, gus{value,class}, bcf, log_kow, henry,
//                        pbt:{p,b,t,verdict}}  -- each numeric an F0 envelope
```

**Rust.** New `commands/fate.rs` → `compute_environmental_fate`, progress events for
large libraries (reuse chunking).

**Zustand.** New `fateStore.ts` (parent fate + later F3 pathway).

**UI.**
- New **Fate View** (or expand Knowledge/Workflow): property cards (DT50, Koc, GUS,
  BCF, Kow, Henry) each with envelope + a **regulatory-threshold comparison** strip
  (e.g., DT50 > 120 d ⇒ persistence flag; GUS > 2.8 ⇒ leacher).
- `ResultsTable.tsx`: compact **Fate flags** column (persistent? leacher? bioaccum?).
- Populate the existing **Environmental Fate Dossier** report with the full parent
  profile + PBT verdict + methodology + disclaimers.

**SQLite.** Migration `v4`: `fate_json` on `workflow_results`.

**Acceptance criteria.**
- Fate models pass scaffold-split validation; coverage holds.
- Known controls reproduce (e.g., atrazine flagged mobile/leacher; a persistent
  organochlorine flagged P and B).
- Threshold comparisons cite the numeric criterion used.

---

### F3 — Transformation Products + their fate/tox — Anchor 2b (the differentiator)

**Commercial value.** The killer-within-the-killer. A clean parent with a persistent or
toxic metabolite dies late in registration. Almost no accessible tool packages
*prediction of TPs → re-scoring those TPs through fate + tox*. This is the unique loop.

**Science / method.**
1. **Enumerate transformation products** from the parent:
   - *Abiotic environmental* (hydrolysis, reduction, direct photolysis, spontaneous
     reactions): **EPA CTS reaction libraries** (public domain) and/or an **owned,
     hand-curated SMARTS/SMIRKS rule set** (`transformation/rules.py`) for the common
     agro routes (ester/amide hydrolysis, N-/O-dealkylation, oxidation, sulfoxidation,
     ring hydroxylation, conjugation).
   - *Metabolic (plant/mammal phase I/II)*: **SyGMa** (rule-based, RDKit/Python — verify
     license; open) for metabolite enumeration with probability scores.
   - *Environmental microbial*: **enviPath/EAWAG-BBD rules are CC BY-NC-SA →
     commercial license required.** Default to owned rules + CTS; offer enviPath as an
     optional licensed plug-in for customers who need it.
2. **Build the pathway DAG** (`pathway.py`): parent → TPs → (optionally) second-generation
   TPs; cap depth (default 2) and rank/prune by rule probability; dedup by canonical SMILES.
3. **Re-score every TP** through F2 (fate) + F1 (tox/selectivity) → flag TPs that are
   *more persistent / more mobile / more toxic* than the parent. This closing of the loop
   is the feature.

**Data / tools.**
| Component | Source | License note |
|-----------|--------|--------------|
| Abiotic env rules | **EPA CTS** (API or rule export) | **public domain — preferred** |
| Owned agro degradation rules | hand-curated SMARTS | **you own it — safest** |
| Plant/mammal metabolites | **SyGMa** | verify license (open) |
| Microbial env pathways (optional) | enviPath | **NC — commercial license needed** |
| TP re-scoring | reuse F1 + F2 | — |

**Python / JSON-RPC.** New `transformation/` package; method:
```jsonc
{"id":1,"method":"transformation_products","params":{
   "smiles":"...","routes":["abiotic","metabolic"],"max_depth":2}}
// result: {nodes:[{id,smiles,parent_id,rule,probability,
//                  fate:{...F2...}, tox:{...F1...}, risk_flag}], edges:[...]}
```

**Rust.** `commands/fate.rs` → `predict_transformation_products` (can be slow; emit
progress + allow cancel via the existing `cancelled_workflows` set).

**Zustand.** Extend `fateStore.ts` with the pathway graph.

**UI.**
- `components/fate/PathwayTree.tsx`: a **transformation DAG viewer** — parent at root,
  TP nodes each rendering a 2D RDKit SVG + a mini risk badge; click a node to load its
  full fate/tox profile into the Inspector. (Render with a lightweight SVG/force layout;
  if you want drag/zoom, a small graph lib — keep it dependency-light.)
- `ResultsTable.tsx`: a **"Problem TP?"** flag column (true if any TP exceeds parent on
  persistence/mobility/tox).
- Add a **Transformation Products** section to the Environmental Fate Dossier report:
  pathway diagram + TP table (SMILES, formation route, fate/tox deltas vs parent).

**SQLite.** Migration `v5`: new table
`transformation_products(id, compound_id FK, parent_tp_id, smiles, route, rule,
probability, fate_json, tox_json, risk_flag)` so TPs are queryable, not just blobbed.

**Acceptance criteria.**
- For reference pesticides, predicted major TPs overlap meaningfully with the
  known metabolites listed in their EFSA conclusions (qualitative recall check).
- The loop fires: at least one validated case where parent passes but a TP is flagged
  (e.g., a known case of a persistent/toxic metabolite).
- No NC-licensed data ships in the default commercial build.

---

### F4 — Registration-Risk Scorecard — Anchor 3

**Commercial value.** Translates chemistry into the **go/no-go language management
thinks in.** Reframes Edeon from "modeling tool" to "registration-risk early-warning
system" — a much easier thing to fund.

**Science / method.** A `regulatory/scorecard.py` that consumes F1+F2+F3 outputs plus
structural alerts and emits a per-criterion verdict (`pass | watch | likely_showstopper`)
with evidence + confidence:
- **PBT / vPvB** (from F2 P/B + F1 T) against REACH Annex XIII numeric criteria.
- **Genotoxicity / carcinogenicity alerts**: **Benigni–Bossa / ISS** structural alerts —
  *reimplemented as SMARTS in `alerts.py`* (do **not** bundle GPL Toxtree; the alert
  definitions are published rules you can encode yourself).
- **Endocrine-disruptor screening flag**: published ED structural-alert profilers
  (screening only — explicitly *not* an ED determination).
- **Groundwater concern**: from F2 GUS/leacher → EU drinking-water 0.1 µg/L trigger.
- **Aquatic hazard classification** (CLP H400/H410-style) from F1 aquatic endpoints.
- **Acute mammalian category** from F1 mammal model vs CLP bands.

**Data sources.**
| Component | Source | License note |
|-----------|--------|--------------|
| Mutagen/carcinogen alerts | Benigni–Bossa (published SMARTS) | reimplement — facts/rules |
| ED screening alerts | published ED profilers/literature | verify, screening-only |
| PBT/vPvB thresholds | REACH Annex XIII (regulatory text) | public |
| CLP/EU 1107/2009 cut-offs | EU regulation text | public |

**Python / JSON-RPC.**
```jsonc
{"id":1,"method":"registration_risk","params":{"smiles":"...","use_predicted_fate":true}}
// result: {criteria:[{name, status, evidence, confidence, source_ref}],
//          overall:{risk:"low|medium|high|showstopper"}}
```

**Rust.** New `commands/regulatory.rs` → `assess_registration_risk`.

**Zustand.** New `regulatoryStore.ts`.

**UI.**
- `components/regulatory/Scorecard.tsx`: a **traffic-light scorecard** per compound —
  each criterion a row with status pill, hover-evidence, and source citation; an overall
  verdict header. Prominent **"in-silico screening, not a regulatory determination"** banner.
- `ResultsTable.tsx`: a **Reg Risk** badge column.
- New **Registration Risk Dossier** printpdf template: per-criterion assessment +
  methodology + disclaimers.

**SQLite.** Migration `v5`: `regulatory_json` on `workflow_results`.

**Acceptance criteria.**
- Alerts fire on positive controls (known mutagens trip Benigni–Bossa; known mobile
  actives trip groundwater; known PBT actives trip PBT).
- Every criterion shows its numeric/structural basis and a disclaimer.
- No criterion presents a screening flag as a determination.

---

### F5 — Prescriptive Design (MMP / bioisostere) — stickiness layer

**Commercial value.** The jump from *diagnostic* ("this has a bee-tox liability") to
*prescriptive* ("…and here are 3 swaps that reduce it while preserving efficacy") is the
jump from "evaluated once and shelved" to "used daily." Daily use justifies a subscription.

**Science / method.**
1. Identify the fragment driving the liability (atom/fragment attribution from the
   relevant F1/F2 model, or simple fragment-deletion sensitivity).
2. Enumerate analogs:
   - **Matched molecular pairs** via **mmpdb** (open source) — build an MMP transform DB
     from your curated + public agro data; query single-point changes that historically
     improve endpoint X.
   - **Bioisosteric replacements** via owned replacement rules; **SwissBioisostere is
     academic-use — gate or replace** for commercial. RDKit BRICS/Recap as a free fallback.
3. Re-predict the **full stack** (F1 selectivity, F2 fate, F4 reg risk) for each analog;
   keep only valid, in-domain molecules; rank by Δ(liability) while preserving efficacy.

**Data / tools.**
| Component | Source | License note |
|-----------|--------|--------------|
| MMP transforms | **mmpdb** (open) + your data | permissive — verify |
| Bioisostere rules | SwissBioisostere | **academic — gate/replace for commercial** |
| Fallback fragmentation | RDKit BRICS/Recap | open |

**Python / JSON-RPC.** New `design/optimize.py`:
```jsonc
{"id":1,"method":"suggest_analogs","params":{
   "smiles":"...","improve":"bee_margin","preserve":["target_efficacy"],"n":20}}
// result: {parent:{...}, suggestions:[{smiles, transform, deltas:{endpoint:Δ},
//          envelopes, ad_status}]}  -- ranked
```

**Rust.** New `commands/design.rs` → `suggest_analogs` (long-running; progress + cancel).

**Zustand.** New `designStore.ts`.

**UI.**
- `components/design/AnalogGrid.tsx`: parent + ranked analog cards (structure,
  transformation applied, predicted endpoint deltas with arrows, intervals, AD badge);
  **"Add to library"** action mounts chosen analogs into the compound store.
- Add an **"Optimize"** action button on any compound in Library/Results/Inspector.

**SQLite.** Suggested analogs are ephemeral until the user saves; saved ones become
normal `compounds` rows (reuse existing schema).

**Acceptance criteria.**
- Suggested analogs are always valid molecules; OOD analogs flagged, not silently shown.
- On a known SAR case, the tool recovers a real improving modification.
- The full re-prediction stack runs end-to-end per analog within a usable time budget.

---

## 5. (intentionally folded into §6)

---

## 6. Data acquisition & licensing appendix

> **The single most important commercial rule:** prefer **public-domain (US EPA)** and
> **open** sources; treat **non-commercial / share-alike / academic-only** sources as
> either model-training inputs you must license-check, or as gated optional plug-ins.

| Resource | Use in plan | Access | License posture for a commercial product |
|----------|-------------|--------|-------------------------------------------|
| **EPA OPERA** | F2 Koc, BCF, biodegradation, Kow | download (models + data) | **Public domain — preferred backbone** |
| **EPA CTS** | F3 abiotic TP rules | API / rule export | **Public domain — preferred** |
| **EPA T.E.S.T.** | F1 mammalian LD50 etc. | download | **Public / open** |
| **US EPA ECOTOX** | F1 aquatic/avian/bee/earthworm | download | **Public domain** |
| **EFSA OpenFoodTox** | F1 mammalian/ref values, F4 | download | **Open (cite)** |
| **EnviroTox** | F1 aquatic ecotox | download | **Free, cite — verify terms** |
| **ApisTox** | F1 honeybee | download (repo) | **Verify license before shipping** |
| **REACH Annex XIII / EU 1107/2009 / CLP** | F2 PBT, F4 cut-offs | regulatory text | **Public** |
| **Benigni–Bossa / ISS alerts** | F4 genotox alerts | published SMARTS | **Reimplement (don't bundle GPL Toxtree)** |
| **mmpdb** | F5 MMP | open source | **Permissive — verify version license** |
| **SyGMa** | F3 metabolites | open source | **Verify license (open) before commercial use** |
| **MAPIE / crepes / venn-abers** | F0 conformal/VA | PyPI | **Permissive — verify per version** |
| **PPDB / BPDB (Hertfordshire AERU)** | F2 DT50 augmentation | web/DB | **Commercial use needs AERU permission — RESOLVE** |
| **ChEMBL** | F1 target efficacy (predicted) | download | **CC BY-SA — share-alike on derived data — care** |
| **enviPath / EAWAG-BBD** | F3 microbial (optional) | API/DB | **CC BY-NC-SA — commercial license required** |
| **SwissBioisostere** | F5 bioisosteres | download | **Academic — gate/replace for commercial** |
| **Toxtree** | (reference only) | GPL software | **GPL — do not bundle; reimplement rules** |

**Action:** before the production build, produce a one-page license register confirming
the status of every shipped dependency. The PPDB and ChEMBL questions in particular
should be resolved with the source holders, because both currently sit in your data path.

---

## 7. Phased task manifest (sequenced for a solo, public-data build)

Ordered by dependency and by "buildable from public data × commercial differentiation."

**Phase A — Trust foundation (do first; everything depends on it)**
- A1. Implement `uq.py` conformal regression + classification (MAPIE/crepes). *[F0]*
- A2. Implement k-NN Tanimoto AD + envelope schema; persist calibration artifacts. *[F0]*
- A3. Wire `UqBadge` + `IntervalBar`; show envelopes in Inspector + ResultsTable. *[F0]*
- A4. Migration `v4` (`uq_json`, calibration metadata). *[F0]*
- **Gate:** coverage ≈ nominal on a scaffold split; AD tracks error.

**Phase B — Environmental fate, parent (highest public-data ROI)**
- B1. Train/port OPERA-based Koc, BCF, Kow, biodegradation models; conformalize. *[F2]*
- B2. DT50 model (OPERA/PPDB-augmented — resolve PPDB license); GUS + PBT logic. *[F2]*
- B3. `environmental_fate` method + `commands/fate.rs` + `fateStore`. *[F2]*
- B4. Fate View + ResultsTable flags + Environmental Fate Dossier population. *[F2]*
- **Gate:** controls reproduce (atrazine mobile; persistent organochlorine P+B).

**Phase C — Transformation products (the differentiator)**
- C1. Curated owned SMARTS/SMIRKS abiotic+agro rule set; CTS client (optional). *[F3]*
- C2. SyGMa adapter (license-checked); `pathway.py` DAG + dedup + depth cap. *[F3]*
- C3. TP re-scoring through F2 (+F1 once available); `transformation_products` method. *[F3]*
- C4. Migration `v5` TP table; `PathwayTree` viewer; dossier TP section. *[F3]*
- **Gate:** predicted TPs overlap known EFSA metabolites; loop flags a real problem-TP.

**Phase D — Selectivity hardening (headline; partly data-constrained)**
- D1. Train calibrated endpoint models: bee, daphnia, fish, bird, earthworm, mammal. *[F1]*
- D2. User-supplied + predicted target-efficacy modes; SI + worst-case margin + MC CI. *[F1]*
- D3. Rework `selectivity`; heatmap Inspector; SI column; Selectivity Chartbook. *[F1]*
- **Gate:** endpoint model cards pass scaffold CV; neonicotinoid scores poor bee margin.

**Phase E — Registration-risk scorecard (rides on B/C/D)**
- E1. `alerts.py` (Benigni–Bossa + ED screening SMARTS, reimplemented). *[F4]*
- E2. `cutoffs.py` (PBT/vPvB, groundwater, CLP) + `scorecard.py`. *[F4]*
- E3. `registration_risk` method; `Scorecard` UI; Reg Risk Dossier report. *[F4]*
- **Gate:** alerts fire on positive controls; disclaimers present everywhere.

**Phase F — Prescriptive design (stickiness; last)**
- F1a. Build mmpdb transform DB; `mmp.py`; bioisostere rules (gate SwissBioisostere). *[F5]*
- F2a. `optimize.py` enumerate → full-stack re-predict → rank; `suggest_analogs`. *[F5]*
- F3a. `AnalogGrid` UI + "Optimize" action + "Add to library". *[F5]*
- **Gate:** recovers a known improving modification; OOD analogs flagged.

**Cross-cutting, continuous — Validation / white-paper track**
- V1. For each shipped model: a model card (data, scaffold-split metrics, coverage, AD,
  Y-scramble). These cards *are* your commercial evidence and your EuroQSAR content.
- V2. Assemble the cross-species-selectivity + TP-fate validation into the preprint that
  doubles as the EuroQSAR Perugia abstract and the lead sales asset.

---

## 8. Notes on sequencing vs. your real constraints

- **Phase A before anything visible.** It's unglamorous but it's the moat; retrofitting
  uncertainty later means re-touching every feature.
- **B and C are your best public-data bets** and the strongest differentiators — and they
  don't depend on the data-hard target-efficacy problem. If time is tight before EuroQSAR,
  **A → B → C** alone is a defensible, novel, commercially distinct story.
- **D (selectivity)** is the headline but the most data-constrained (efficacy + crop
  phytotox). Shipping it with the **user-supplied efficacy** mode first sidesteps the
  weakest data dependency and is *more* credible to buyers (their data, your method).
- **Resolve PPDB and ChEMBL licensing** before the production build — both are in your
  current data path and both carry commercial conditions.
- Keep the **"screening, not determination"** framing everywhere F4 touches — it protects
  you legally and, paradoxically, increases credibility with sophisticated buyers.
