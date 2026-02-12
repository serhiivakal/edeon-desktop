# Edeon Desktop — Tier 2 Pre-Made Workflows Implementation Plan

> Companion to the Tier 1 plan. Four supporting workflows that complete the discovery
> cycle: **top-of-funnel triage, competitive positioning, selectivity optimization, and
> IP/novelty exploration.**
> **Assumes the Tier 1 framework (§1 of the Tier 1 plan) already exists** — the workflow
> registry, `list_workflows`/`run_workflow` JSON-RPC, the confidence-aware verdict rule,
> the provenance manifest, and the Gallery → Config → Pipeline → DecisionArtifact UI.
> This plan specs only what is **new**.

---

## 0. Context — the Tier 2 set

| ID | Workflow | Job / gate | Persona | New capability |
|----|----------|-----------|---------|----------------|
| **W5** | Hit-to-Shortlist Triage | "Cut thousands of hits to a diverse, de-risked shortlist." | Discovery (high-frequency) | staged-cost runner (P2) |
| **W6** | Comparative Benchmarking | "How does my candidate stack up vs. the market standard?" | Management / competitive | **reference-active library (P1)** |
| **W7** | Selectivity Window Optimization | "Widen my narrowest safety margin without collapsing the others." | Discovery | maximin objective (P3a) |
| **W8** | Scaffold-Hop / Novelty Explorer | "Find novel scaffolds that keep this lead's profile." | Discovery / IP strategy | scaffold-novelty heuristic (P3b) |

These complement Tier 1 (which covered the expensive go/no-go gates). Together the eight
workflows span the full cycle: **triage → optimize → position → de-risk → register.**

---

## 1. What is reused vs. new

**Reused unchanged from Tier 1:** `WorkflowSpec`/`Step`/`Verdict`/`WorkflowResult`
contracts; `runner.py`; `verdict.py` (confidence-aware rule); `provenance.py`;
`registry.py`; generic `run_workflow`/`list_workflows`; Rust `run_named_workflow`;
`WorkflowGalleryView`, `VerdictHeader`, `DecisionArtifact`; the F0 envelope on every
number. New workflows are **new registry entries** — no new RPC plumbing.

**New for Tier 2:**
- **P1 — Reference-Active Library** (the one substantial new asset; powers W6, optionally W8).
- **P2 — Staged-cost execution** in the runner (cheap filters on the full library,
  expensive predictions only on survivors) — needed for W5 at scale.
- **P3a — Maximin selectivity objective** (W7 ranking helper).
- **P3b — Scaffold-novelty heuristic** (W8 ranking helper).

---

## 2. Repository layout (new files)

```
python/edeon_engine/workflows/
  w5_triage.py            # W5 spec + aggregator (attrition waterfall)
  w6_benchmarking.py      # W6 spec + aggregator (positioning)
  w7_selectivity_window.py# W7 spec + aggregator (maximin)
  w8_scaffold_hop.py      # W8 spec + aggregator (novelty heuristic)
  presets.py              # MPO/triage scoring profiles per pest class
  objectives.py           # maximin (P3a) + scaffold-novelty (P3b) helpers
reference/
  reference_library.py    # P1: query/curation API over the bundled reference DB
  build_reference_db.py   # P1: offline build script (curate measured + predict gaps)

src/
  components/workflow/AttritionWaterfall.tsx   (NEW, W5)
  components/workflow/PositioningChartbook.tsx (NEW, W6)
  components/workflow/SelectivityWindow.tsx    (NEW, W7)
  components/design/AnalogGrid.tsx             (reuse, W7/W8)

src-tauri/src/commands/reference.rs            (NEW: query reference library)
```

SQLite: bundled `reference_actives.sqlite` (read-only, shipped). No change to the
project DB beyond the Tier 1 `v6` migration (workflow runs already persist generically).

---

## 3. Prerequisite sub-features

### P1 — Reference-Active Library (prerequisite for W6)

**What.** A bundled, read-only database of **marketed agrochemical actives** with a
profile on every Edeon axis (efficacy class, selectivity endpoints, fate, regulatory),
each value tagged **measured vs. predicted** with provenance. This is independently one
of the most valuable assets in the product: it gives every prediction instant context and
is itself a validation showcase.

**Data sourcing.**
| Axis | Measured source | Fallback |
|------|-----------------|----------|
| Identity, use class, MoA (HRAC/IRAC/FRAC) | PPDB/BPDB; regulatory labels | — |
| Bee / aquatic / avian / mammal tox | ECOTOX, OpenFoodTox, EnviroTox | Edeon-predicted |
| DT50, Koc, GUS, BCF | PPDB; EFSA dossiers; OPERA | Edeon-predicted |
| Regulatory status (PBT/ED/approval) | EU pesticides database, EFSA conclusions | — |

> **Licensing (carry forward from the data appendix):** measured fate/identity data from
> **PPDB/BPDB carries commercial-use conditions — resolve with AERU before shipping.**
> Prefer public-domain measured sources (ECOTOX, OpenFoodTox, OPERA, EU pesticides DB);
> fill remaining gaps with Edeon predictions, clearly tagged.

**Schema (`reference_actives.sqlite`).**
```
actives(id, name, cas, smiles, use_class, moa_group, approval_status)
active_values(active_id FK, axis, value, unit, source_type, source_ref)
                                          // source_type: "measured" | "predicted"
```

**API.** `reference/reference_library.py`; JSON-RPC:
```jsonc
{"id":1,"method":"reference_lookup","params":{
   "by":"moa|use_class|name|similarity","query":"ALS inhibitors","limit":10}}
// -> [{active, profile:[{axis,value,source_type,source_ref, envelope?}]}]
```
"similarity" mode returns the nearest marketed actives to a query SMILES (Tanimoto) —
useful context anywhere in the app.

**Build script.** `build_reference_db.py`: curate measured values; run Edeon predictors
to fill gaps; tag every value; stamp data versions into provenance. Re-runnable as data
updates.

**Acceptance.** Library loads; every value tagged measured/predicted with a source;
similarity lookup returns sensible neighbors; no commercially-restricted measured data
ships unresolved.

### P2 — Staged-cost execution (prerequisite for W5)

**Why.** Triage runs on large libraries; you must not run expensive predictions
(selectivity, fate) on everything. Extend `runner.py` with a **funnel** capability: a
step can be marked `gate=True`, and downstream `expensive=True` steps run **only on
survivors** of the gates. Track per-stage counts for the attrition waterfall.

**Contract addition.**
```python
Step(..., gate: bool=False, expensive: bool=False)
# runner records survivors after each gate; expensive steps receive only survivors;
# WorkflowResult.sections["attrition"] = [{stage, in, out, dropped, reason}]
```

**Acceptance.** Expensive steps demonstrably receive only post-gate survivors; attrition
counts are exact and reproducible.

### P3 — Ranking helpers (`objectives.py`)

- **P3a maximin selectivity** (W7): `score = min(selectivity_index over non-targets)`;
  rank analogs by **lift in the minimum margin**, subject to no other margin dropping
  below its threshold. Penalize OOD (gate behind toggle).
- **P3b scaffold-novelty** (W8): `novelty = 1 − Tanimoto(lead, candidate)` **and**
  `bemis_murcko_scaffold(candidate) != bemis_murcko_scaffold(lead)` (hard requirement);
  optional `min Tanimoto distance to reference-active library` as a structural-novelty
  hint. **Structural heuristic only — not a legal/FTO/patentability signal** (see W8).

---

## 4. Workflow specifications

---

### W5 — Hit-to-Shortlist Triage

**Sales framing.** The high-frequency top-of-funnel job every discovery team runs.
Packages your existing library-prep, likeness, alerts, diversity, and MPO into one
opinionated funnel that turns thousands of hits into a diverse, de-risked, ranked
shortlist — with a satisfying attrition waterfall a team lead can show upward.

**Input.** `library` (thousands–tens of thousands).

**Steps (funnel — note `gate`/`expensive`).**
| # | Step (method) | applies_to | flags | Defaults | Produces |
|---|---------------|------------|-------|----------|----------|
| 1 | `standardize` | each_compound | — | — | clean structures |
| 2 | `compute_properties` | each_compound | — | — | descriptors |
| 3 | `pesticide_likeness` (Tice) | each_compound | gate | class=herbicide; drop "Low" | likeness pass/fail |
| 4 | structural alerts (PAINS/reactive) | each_compound | gate | drop flagged | alert pass/fail |
| 5 | `selectivity` (quick subset) | survivors | expensive | bee+mammal | quick liability screen |
| 6 | diversity select (Bemis-Murcko round-robin) | survivors | — | target N reps | diverse subset |
| 7 | `mpo_score` | subset | — | triage preset (P-presets) | ranked shortlist |

**Logic / output.** No GO/NO_GO. Output = a **ranked shortlist** tiered
(priority / consider / deprioritized by MPO) + the **attrition waterfall** + a diversity
summary (scaffold count represented). Confidence-aware: OOD compounds in the quick-screen
are flagged, not silently ranked.

**Decision artifact — "Triage Shortlist".** `AttritionWaterfall` (compounds in→out per
stage) + ranked shortlist table (MPO, key flags, AD) + diversity summary +
**"Send shortlist to VS / library"** (reuse the existing Send-to-VS route).

**Config.** Pest class (herbicide/insecticide/fungicide → Tice thresholds + likeness
preset), shortlist size N, quick-screen endpoints, MPO weights.

**Acceptance.**
- Expensive steps run only on survivors (P2); attrition counts exact.
- Diversity guarantee: shortlist spans ≥ N distinct Bemis-Murcko scaffolds.
- Large-library runtime within target (define, e.g., ~10k compounds in minutes on the
  configured worker count).

---

### W6 — Comparative Benchmarking vs. reference actives

**Sales framing.** The most *persuasive* workflow for management and go/no-go: position
a candidate against the marketed standard on every axis and state it plainly —
"comparably efficacious to [standard], but lower bee risk and shorter soil persistence."
Doubles as a validation/credibility showcase.

**Input.** `single` or `series` candidate(s) + a reference set (by MoA class, use class,
or user pick) from **P1**.

**Steps.**
| # | Step (method) | applies_to | Defaults | Produces |
|---|---------------|------------|----------|----------|
| 1 | `standardize` | each_compound | — | clean structures |
| 2 | `selectivity`+`environmental_fate`+`registration_risk` | each_compound | — | candidate profile |
| 3 | `reference_lookup` (P1) | reference set | by MoA / user pick | reference profiles |
| 4 | align axes; compute positioning Δ | per axis | thresholds | better/comparable/worse |

**Logic.** Per axis, classify candidate vs. the reference set (better / comparable /
worse) → a narrative **positioning summary**. Crucial honesty rules:
- **Tag measured vs. predicted** on both sides; never present a predicted-vs-measured
  comparison as if both were measured.
- If the candidate is **OOD** on an axis, that comparison is `low confidence` (§1.3) and
  flagged, not asserted.

**Decision artifact — "Positioning Chartbook".** Radar + per-axis bar charts
(candidate vs. reference set, with measured/predicted tags and CIs) + a plain-language
positioning paragraph + a table. Prominent measured-vs-predicted legend.

**Acceptance.**
- Reference profiles load with provenance and source tags.
- Known cases position correctly (a benign candidate reads "lower tox" vs. a toxic standard).
- Measured/predicted clearly distinguished everywhere; OOD axes flagged.

---

### W7 — Selectivity Window Optimization

**Sales framing.** Specializes the optimization loop to your headline axis: map the full
selectivity window across all non-targets, find the **limiting** margin, and widen it
**without collapsing the others** (a maximin objective). Distinct from the Tier 1
Lead-Optimization Cycle, which targets whatever the dominant liability is; W7 is the
selectivity-window specialist with the multi-margin trade-off front and center.

**Input.** `single` lead or `series`.

**Steps.**
| # | Step (method) | applies_to | Defaults | Produces |
|---|---------------|------------|----------|----------|
| 1 | `standardize` | each_compound | — | clean structures |
| 2 | `selectivity` (full panel) | each_compound | all non-targets | margin landscape |
| 3 | identify limiting margin | per compound | min over non-targets | target endpoint |
| 4 | `suggest_analogs` | each_compound | improve=limiting, preserve=efficacy | analogs |
| 5 | `selectivity` (full panel) | each_analog | — | analog margins |
| 6 | rank by **maximin** (P3a) | analog set | no other margin < threshold | ranked analogs |

**Logic.** Maximize the **minimum** selectivity margin across non-targets; reject analogs
that widen the target margin but push another below its threshold (surface these as
trade-off-flagged, not as wins). OOD analogs gated.

**Decision artifact — "Selectivity Window Report".** `SelectivityWindow` chart (per
non-target margins, **before → after**, with the limiting margin highlighted) + ranked
`AnalogGrid` by maximin lift + trade-off flags + **"Add to library"**.

**Acceptance.**
- Recovers a known margin-widening modification on a test series.
- Maximin ranking never surfaces an analog that drops another margin below threshold as a win.
- Trade-offs explicit; OOD gated.

---

### W8 — Scaffold-Hop / Novelty Explorer

**Sales framing.** Generate structurally **novel scaffolds that retain a lead's predicted
profile** — for backup series, novelty, and IP-around thinking. Attractive in agro's
dense patent landscape.

> **Hard guardrail (bake into the artifact and tooltips):** this is **structural /
> chemistry novelty exploration only.** It is **not** a freedom-to-operate, patentability,
> or legal-novelty determination, and must never be presented as one. Edeon reports
> *structural distance* from a lead and (optionally) from known marketed actives — a
> heuristic, not legal advice. No patent data, no FTO claims.

**Input.** `single` lead.

**Steps.**
| # | Step (method) | applies_to | Defaults | Produces |
|---|---------------|------------|----------|----------|
| 1 | `standardize` | lead | — | clean structure |
| 2 | `selectivity`+`environmental_fate` | lead | — | lead profile |
| 3 | `suggest_analogs` (scaffold-hopping) | lead | scaffold-changing transforms; BRICS/Recap | diverse analogs |
| 4 | enforce scaffold difference (P3b) | analogs | different Murcko scaffold + Tanimoto dist | novel-scaffold set |
| 5 | `selectivity`+`environmental_fate` | each_analog | — | analog profiles |
| 6 | filter to profile-match; rank by novelty×match (P3b) | analog set | tolerance; in-domain | ranked novel scaffolds |

**Logic.** Keep analogs whose profile matches the lead within tolerance; require a
**distinct Bemis-Murcko scaffold** and Tanimoto distance ≥ threshold from the lead;
optionally report structural distance to the nearest reference active (P1) as a novelty
*hint* (with the guardrail). Rank by `novelty × profile_match`, OOD gated.

**Decision artifact — "Scaffold-Hop Explorer".** Grid of novel scaffolds (structure,
scaffold-distance, profile-match deltas, optional distance-to-known-actives, AD) +
the structural-novelty disclaimer banner + **"Add as backup series to library."**

**Acceptance.**
- Output scaffolds are genuinely scaffold-distinct (different Murcko scaffold, distance ≥
  threshold) yet profile-matching within tolerance.
- OOD gated; the FTO/legal disclaimer present on the artifact and any export.
- No patent/FTO/legal claim appears anywhere in output.

---

## 5. Phased task manifest (sequenced by value × buildability)

**Phase 5 — W5 Triage** *(pure composition + P2; high-frequency, fast win)*
- 5.1 P2 staged-cost runner enhancement; `presets.py` triage profiles.
- 5.2 `w5_triage.py` + attrition aggregator; `AttritionWaterfall`.
- 5.3 Reuse Send-to-VS route for shortlist hand-off.
- **Gate:** W5 acceptance (survivor-only expensive steps; diversity guarantee; runtime).

**Phase 6 — P1 Reference-Active Library, then W6 Benchmarking** *(the new asset)*
- 6.1 `build_reference_db.py`; curate measured (public-domain first), predict gaps, tag.
- 6.2 `reference_library.py` + `reference_lookup` method + Rust `reference.rs`.
- 6.3 `w6_benchmarking.py` + positioning aggregator; `PositioningChartbook`.
- **Gate:** P1 + W6 acceptance (provenance tags; correct positioning; measured/predicted
  distinction; PPDB commercial status resolved or excluded).

**Phase 7 — W7 Selectivity Window** *(composition + P3a)*
- 7.1 `objectives.py` maximin; `w7_selectivity_window.py`; `SelectivityWindow` chart.
- **Gate:** W7 acceptance.

**Phase 8 — W8 Scaffold-Hop** *(composition + P3b + guardrail)*
- 8.1 `objectives.py` scaffold-novelty; `w8_scaffold_hop.py`; reuse `AnalogGrid`.
- 8.2 Disclaimer banner + export guard (block any FTO/legal phrasing).
- **Gate:** W8 acceptance, including the no-legal-claim check.

---

## 6. Why Tier 2 completes the picture

- **Full-cycle coverage.** Tier 1 owned the expensive go/no-go gates; Tier 2 adds the
  daily top-of-funnel (W5), the management-facing positioning story (W6), the headline-axis
  optimizer (W7), and the IP/backup-series explorer (W8). Eight workflows now map the whole
  discovery loop — a complete, demoable product narrative.
- **The reference-active library is a force-multiplier** beyond W6: it contextualizes every
  prediction across the app and is a credibility asset in its own right.
- **Persona/pricing map widens:** W5→discovery (volume), W6→management (the buyer who signs
  off), W7→discovery, W8→discovery/IP — useful module/tier boundaries.
- **Same trust spine throughout:** confidence-aware verdicts, provenance manifests,
  measured-vs-predicted honesty, and explicit "screening/structural heuristic, not a
  determination" framing — the discipline that lets a sophisticated buyer act on Edeon's output.
