# Edeon Phase 5 — Hard Endpoints: Honest Redesign Implementation Specification

**Audience:** coding agent.
**Goal:** ship honest, defensible Tier-1 backends for three endpoints where the previous LogP-based predictions were misleading or absent:

1. **UV photostability** — replace the fake numeric decay curve with a qualitative stratified-alerts panel that classifies compounds as Stable / Moderate / Susceptible based on chromophore, photoreactive-group, and hydrolytic-stability SMARTS rules. No fake half-life.
2. **BCF** — train a Phase 2-style ensemble with explicit ionization-state handling, since published BCF QSARs systematically fail on ionizable compounds and most don't acknowledge it.
3. **Selectivity** — integrate Paper 2's validated cross-species selectivity scorer (12 ortholog pairs) as a profile-returning backend. No interim hand-waving; either Paper 2 artifacts are available and integration proceeds, or the integration infrastructure is built with stubs and slots in when Paper 2 lands.

**Inputs:**
- Phase 1 curated dataset for BCF (`data/curated/bcf/v1.0/`).
- Phase 0 architecture; Phase 2 shared infrastructure; Phase 4's `StructuralAlertsBackend` pattern.
- Paper 2 deliverables (see Section 4.3 for the contract).

**Outputs:** trained BCF T1 backend, photostability stratified-alerts backend, selectivity profile backend, model cards, frontend updates to the fate gauge / toxicity panel / new selectivity panel.

This phase is the *cleanup* — it removes the remaining LogP-heuristic backends from the user-facing surface. After Phase 5, the only T2 backends still in the registry are inactive fallbacks for completeness, not actively-displayed predictions.

---

## 0. Context and Hard Rules

**Hard rule 1: photostability does NOT get a numeric model.**
The published photostability QSAR landscape is fragmented — different endpoints (water phototransformation, soil phototransformation, foliar, atmospheric OH• reaction), different test conditions, no consistent dataset, no reliable cross-test generalization. A trained model would mislead users with false precision. Honest answer: qualitative alerts with structural rationale.

The Phase 4 `StructuralAlertsBackend` pattern is reused but extended into a `StratifiedAlertsBackend` that combines matches across categories (chromophore + photoreactive + hydrolytic) into a final classification (Stable / Moderate / Susceptible).

**Hard rule 2: BCF must report ionizable subset performance separately.**
Most published BCF models report aggregate R² and quietly fail on ionizables (weak acids and bases with pKa in 3–11). The Phase 5 BCF model:
- Includes `ionizable_flag` (from Phase 1 curation) as a feature
- If a pKa predictor is available, computes LogD@pH7 as additional feature
- Reports per-subset metrics (ionizable vs. non-ionizable) in the validation report
- Sets a deliberately lower performance target for the ionizable subset and documents the gap honestly

**Hard rule 3: selectivity has no in-Phase-5 training.**
Phase 5 *consumes* Paper 2's models. If Paper 2 artifacts are not available at integration time, the integration is built around stubs that match the artifact contract (Section 4.3), and the backend stays unregistered until artifacts arrive. Do not invent a placeholder selectivity model — placeholder selectivity is worse than no selectivity, because it normalizes false claims.

**Hard rule 4: test set protection (same as Phase 2/3/4).**
Applies to BCF. The other two endpoints do not have trained models, so the gate doesn't apply.

---

## 1. Tech Stack Assumptions

In addition to Phase 4's stack:

- **pKa prediction (optional)**: `pkai` (pKAI, open-source neural pKa predictor) or `chemaxon-cli` if licensed. If neither is available, the agent uses `ionizable_flag` only and documents the LogD feature as absent.
- **RDKit's `FilterCatalog`**: for managed alert evaluation
- **PyYAML**: for the stratified alerts rules file
- **Pickled / state-dict Paper 2 artifacts**: loaded via `torch.load` and/or `joblib.load` depending on Paper 2's choice

No new heavy dependencies.

---

## 2. Architectural Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│  edeon-train bcf all                  (Phase 2 recipe + ionization)  │
│  edeon-train photostability deploy_alerts (alerts backend)           │
│  edeon-train selectivity deploy       (integrate Paper 2 artifacts)  │
└──────────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────────┐
              ▼               ▼                   ▼
    ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
    │ BCF (regression) │ │ Photostability   │ │ Selectivity      │
    │ Phase 2 recipe   │ │ Stratified Alerts│ │ Paper 2 backend  │
    │ + ionizable_flag │ │ (qualitative)    │ │ (12 pair models, │
    │ + LogD@pH7 opt.  │ │                  │ │  profile output) │
    └──────────────────┘ └──────────────────┘ └──────────────────┘
                              │                     │
                              ▼                     ▼
                  ┌───────────────────────────────────────────┐
                  │  BackendRegistry                          │
                  │  T1 hard-endpoint backends                │
                  │  (selectivity may register lazily when    │
                  │   Paper 2 artifacts arrive)               │
                  └───────────────────────────────────────────┘
                              │
                              ▼
                  ┌───────────────────────────────────────────┐
                  │  Frontend                                 │
                  │  - Fate gauge: BCF row with CI            │
                  │  - Photostability panel: stratified       │
                  │    alerts + risk class badge              │
                  │  - NEW Selectivity panel: 12-cell grid    │
                  │    (or 4×3) color-coded                   │
                  └───────────────────────────────────────────┘
```

---

## 3. Repository Layout

```
edeon/
├── python/
│   ├── edeon_models/
│   │   ├── endpoints.py                          # MODIFIED — add SELECTIVITY_PROFILE
│   │   └── backends/
│   │       ├── alerts/
│   │       │   ├── alerts_backend.py             # Existing (Phase 4)
│   │       │   ├── stratified_alerts_backend.py  # NEW (Phase 5)
│   │       │   └── rules/
│   │       │       ├── eye_irritation.yaml       # Existing (Phase 4)
│   │       │       └── photostability.yaml       # NEW
│   │       ├── trained/
│   │       │   └── tier1_backend.py              # Existing
│   │       └── selectivity/                      # NEW
│   │           ├── __init__.py
│   │           ├── selectivity_backend.py
│   │           ├── paper2_loader.py              # Loads Paper 2 artifacts
│   │           └── schema.py                     # Paper 2 artifact schema validation
│   ├── edeon_train/
│   │   ├── shared/
│   │   │   ├── ionization.py                     # NEW — pKa, LogD, ionizable handling
│   │   │   └── ...
│   │   ├── endpoints/
│   │   │   ├── bcf/                              # NEW
│   │   │   │   ├── __init__.py
│   │   │   │   ├── config.yaml
│   │   │   │   ├── train.py
│   │   │   │   └── card.py
│   │   │   ├── photostability/                   # NEW (alerts-only)
│   │   │   │   ├── __init__.py
│   │   │   │   ├── config.yaml
│   │   │   │   └── card.py
│   │   │   └── selectivity/                      # NEW (integration-only)
│   │   │       ├── __init__.py
│   │   │       ├── config.yaml
│   │   │       └── card.py
├── data/
│   ├── checkpoints/
│   │   ├── bcf/v1.0/
│   │   └── selectivity/v1.0/                     # Symlink or copy of Paper 2 deliverable
│   └── paper2_artifacts/                         # NEW — Paper 2 staging area
│       └── v1.0/
│           ├── manifest.json
│           ├── target_pairs/
│           │   ├── ache_insect_human/
│           │   ├── nachr_insect_vertebrate/
│           │   ├── ... (12 pair directories)
│           └── ortholog_structures/              # Reference structures only — not used at inference
├── docs/
│   ├── PHASE5_NOTES.md
│   ├── PHASE5_PHOTOSTABILITY_PROTOCOL.md
│   ├── PHASE5_BCF_PROTOCOL.md
│   ├── PAPER2_ARTIFACT_CONTRACT.md               # NEW — what Paper 2 must deliver
│   └── TIER1_MODEL_CARDS/
│       ├── bcf.md
│       ├── photostability_alerts.md
│       └── selectivity_profile.md
└── .github/
    └── workflows/
        └── tier1_phase5_regression.yml
```

---

## 4. Modeling Methodology Standards

### 4.1 Photostability — stratified structural alerts

#### 4.1.1 Three alert categories

Compounds match against three independent SMARTS rule sets:

**Category A: Chromophores** (strong UV absorption → photolabile)
- Aromatic nitro groups
- Aromatic azo groups
- Extended π-systems (3+ conjugated aromatic rings)
- Polyene chains
- Quinones / anthraquinones
- Stilbene-like (cross-conjugated alkenes between aromatics)
- Aromatic ketones/aldehydes (Norrish-active)
- N-oxide aromatics

**Category B: Photoreactive groups** (intrinsically photolabile)
- Peroxides (R-O-O-R)
- Hydroperoxides (R-O-O-H)
- Diazo compounds (C=N=N)
- Azides (N=N=N)
- N-nitroso (R-N(NO)-R')
- Diazonium (R-N≡N⁺)

**Category C: Hydrolytic stability flags** (environmentally labile)
- Anhydrides
- Acyl halides
- Esters (general)
- Amides (general)
- Carbamates
- Phosphate esters / phosphonates (relevant for OPs)
- Sulfonyl halides
- Imines / Schiff bases
- Vinyl/allyl halides

#### 4.1.2 Risk classification logic

Aggregate the matches into a final risk class:

```python
def classify_photostability(matches_A, matches_B, matches_C) -> str:
    """
    matches_A, _B, _C: lists of matched rules from each category.
    Returns: "Susceptible", "Moderate", or "Stable".
    """
    # Any photoreactive group → Susceptible
    if len(matches_B) > 0:
        return "Susceptible"

    # Strong chromophore (nitro/azo/quinone) → Susceptible
    strong_chromophore_ids = {"aromatic_nitro", "aromatic_azo", "quinone", "anthraquinone"}
    if any(m["id"] in strong_chromophore_ids for m in matches_A):
        return "Susceptible"

    # Multiple alerts (any combination of moderate ones) → Moderate
    if len(matches_A) + len(matches_C) >= 2:
        return "Moderate"

    # Single alert in A or C → Moderate
    if len(matches_A) + len(matches_C) >= 1:
        return "Moderate"

    # Nothing matched → Stable (with caveat)
    return "Stable"
```

The exact rules go in `rules/photostability.yaml` (Section 6 Task B1).

#### 4.1.3 Prediction output

```python
Prediction(
    smiles=...,
    endpoint="photostability_class",
    value=PredictionValue(kind="categorical", categorical="Moderate"),
    ad_status=ADStatus.UNKNOWN,  # No training data, no AD
    units="category",
    model_id=...,
    model_version="1.0.0",
    tier=1,
    provenance={
        "category_A_matches": [...],  # Each match: id, smarts, description, references
        "category_B_matches": [...],
        "category_C_matches": [...],
        "classification_logic": "any_B → Susceptible | strong_A → Susceptible | else by count",
        "risk_class": "Moderate",
    },
    warnings=[
        "Qualitative screening only — not a quantitative half-life prediction.",
        "Absence of alerts does not guarantee photostability."
    ],
)
```

#### 4.1.4 Caveats documented in card

The model card must include in `not_intended_for`:
- Half-life or decay-rate prediction
- Regulatory phototransformation studies (OECD 316/317)
- Formulation photoprotection optimization (different problem)

And in `known_failure_modes`:
- Compounds whose photolability depends on conformation or aggregation
- Mechanism-specific photoreactions (e.g., singlet oxygen sensitization without obvious chromophore)
- Wavelength-dependent effects (alerts don't distinguish UV-A/B/C selectivity)

### 4.2 BCF — Phase 2 recipe with ionization handling

#### 4.2.1 Architecture

Apply the full Phase 2 ensemble recipe (RF + XGBoost + Chemprop ensemble + split conformal + Tanimoto AD).

**Phase 5 additions for BCF:**

1. **Ionizable flag as feature**: append the Phase-1-curated `ionizable_flag` (1 if pKa∈[3,11], else 0) to the baseline feature vector. Pass as auxiliary feature to Chemprop.
2. **pKa estimate (optional)**: if pKa predictor is available, compute pKa and append to feature vector. If multiple ionizable groups, use the most acidic for acids and most basic for bases (consistent with regulatory practice).
3. **LogD@pH7 (if pKa available)**: compute LogD = LogP - log10(1 + 10^(pH - pKa)) for acids and LogD = LogP - log10(1 + 10^(pKa - pH)) for bases. Add as feature.
4. **Per-subset reporting**: validation report breaks down test performance into `ionizable` and `non_ionizable` subsets. Report RMSE, R², coverage, and AD coverage separately.
5. **q-RASAR-style similarity features (optional)**: if implementation budget permits, add similarity-based features (mean Tanimoto similarity to k nearest training neighbors, mean log-BCF of k nearest neighbors). These improve performance on ionizables according to Pore et al. 2024.

#### 4.2.2 Performance targets

| Subset | R² target | RMSE log target | Coverage 95% | AD coverage target |
|---|---|---|---|---|
| Overall | 0.65 | 0.55 | 0.93–0.97 | 0.55 |
| Non-ionizable | 0.70 | 0.50 | 0.93–0.97 | 0.60 |
| Ionizable | 0.55 | 0.65 | 0.90–1.00 | 0.40 |

The ionizable subset target is deliberately lower. Document the gap honestly in the card.

#### 4.2.3 Required documentation

The model card must include in `known_failure_modes`:
- Strongly ionizable compounds (pKa < 3 or > 11) where ionization dominates partitioning
- Surfactants and very lipophilic compounds (logP > 8)
- Compounds with active uptake via biological transporters (not represented in training data)
- Anion accumulators (e.g., perfluorinated acids) — different mechanism

### 4.3 Selectivity — Paper 2 integration contract

#### 4.3.1 Paper 2 deliverable structure

Paper 2 must produce artifacts conforming to:

```
data/paper2_artifacts/v1.0/
├── manifest.json
├── target_pairs/
│   ├── ache_insect_human/
│   │   ├── model.pkl               # Trained sklearn model OR
│   │   ├── model.pt                # Trained PyTorch state dict
│   │   ├── ensemble_weights.yaml   # If ensemble
│   │   ├── conformal.npz           # CP calibration
│   │   ├── ad_fingerprints.npz     # Tanimoto k-NN AD
│   │   ├── featurizer.yaml         # Featurization recipe
│   │   └── pair_card.yaml          # Pair-specific metadata
│   ├── nachr_insect_vertebrate/
│   ├── nav_pyrethroid_site/
│   ├── ryanodine_receptor/
│   ├── gaba_chloride_channel/
│   ├── cyp51_fungal_human/
│   ├── sdh_fungal_mammalian/
│   ├── cytb_qo_site/
│   ├── hppd_plant_human/
│   ├── ppo_plant_human/
│   ├── epsps_control/               # Negative control (humans lack target)
│   └── als_resistance_control/      # Resistance-mutation control
└── manifest.json                    # Master manifest with versions, hashes
```

#### 4.3.2 manifest.json schema

```json
{
  "paper2_version": "1.0.0",
  "created": "2026-XX-XX",
  "target_pairs": [
    {
      "pair_id": "ache_insect_human",
      "display_name": "AChE: insect vs. human",
      "pest_organism": "Musca domestica",
      "pest_uniprot": "P07140",
      "nontarget_organism": "Homo sapiens",
      "nontarget_uniprot": "P22303",
      "category": "insecticide",
      "model_artifact": "target_pairs/ache_insect_human/model.pt",
      "featurizer_artifact": "target_pairs/ache_insect_human/featurizer.yaml",
      "conformal_artifact": "target_pairs/ache_insect_human/conformal.npz",
      "ad_artifact": "target_pairs/ache_insect_human/ad_fingerprints.npz",
      "pair_card": "target_pairs/ache_insect_human/pair_card.yaml",
      "performance": {
        "rmse_log_selectivity": 0.45,
        "spearman": 0.72,
        "ad_coverage_test": 0.61
      },
      "selectivity_units": "log10(IC50_nontarget / IC50_pest)",
      "direction": "higher = more selective for pest"
    },
    ...
  ]
}
```

#### 4.3.3 pair_card.yaml schema

```yaml
pair_id: ache_insect_human
description: |
  Insect AChE vs human AChE selectivity. Compounds binding more
  strongly to insect AChE than human AChE are more selective.
training_data:
  n_compounds: 423
  selectivity_range_log: [-2.5, 4.1]
  sources: [ChEMBL, BindingDB, IUPHAR]
featurizer:
  type: chemprop_with_descriptors
  reference: featurizer.yaml
model:
  type: ensemble
  components: [random_forest, xgboost, chemprop_gnn]
  weights_file: ensemble_weights.yaml
uncertainty:
  method: split_conformal
  alpha: 0.05
applicability_domain:
  method: tanimoto_knn
  k: 5
  in_threshold: 0.42
  out_threshold: 0.58
performance:
  rmse_log: 0.45
  r2: 0.55
  spearman: 0.72
  coverage_95_test: 0.94
references:
  - "Paper 2 citation"
known_failure_modes:
  - "Allosteric inhibitors not represented in training data"
  - "Covalent inhibitors (organophosphates) handled separately"
```

#### 4.3.4 Edeon-side integration

```python
class SelectivityProfileBackend(ModelBackend):
    """Tier-1 backend serving selectivity predictions across all target pairs.

    Returns either:
    - A profile across all pairs if no conditions specified
    - A single-pair prediction if conditions["target_pair"] is set
    """

    def __init__(self, paper2_artifacts_dir: Path):
        self._manifest = load_manifest(paper2_artifacts_dir / "manifest.json")
        self._pair_backends: dict[str, PairBackend] = {}
        for pair_meta in self._manifest["target_pairs"]:
            pair_id = pair_meta["pair_id"]
            self._pair_backends[pair_id] = PairBackend.load(
                paper2_artifacts_dir / "target_pairs" / pair_id
            )

    def endpoint(self) -> Endpoint: return Endpoint.SELECTIVITY_PROFILE
    def tier(self) -> int: return 1
    def version(self) -> str: return self._manifest["paper2_version"]

    def predict(self, smiles, conditions=None) -> list[Prediction]:
        pair_filter = conditions.get("target_pair") if conditions else None

        predictions = []
        for s in smiles:
            if pair_filter:
                # Single pair prediction
                pair = self._pair_backends[pair_filter]
                pred = pair.predict_single(s)
                predictions.append(self._build_pair_prediction(s, pair_filter, pred))
            else:
                # Profile across all pairs
                pair_results = {
                    pid: pb.predict_single(s)
                    for pid, pb in self._pair_backends.items()
                }
                predictions.append(self._build_profile_prediction(s, pair_results))

        return predictions
```

#### 4.3.5 What Paper 2 must deliver vs. what Edeon does

Paper 2 produces:
- Per-pair trained models (any architecture, the spec is artifact-agnostic)
- Per-pair conformal calibrators
- Per-pair AD definitions
- Per-pair featurizer specifications
- A manifest tying it all together

Edeon does:
- Load artifacts via a stable schema
- Featurize query SMILES once per featurizer type (cache across pairs sharing a featurizer)
- Apply each pair's model
- Construct Prediction objects with both per-pair and aggregate views
- Render in the new Selectivity panel

The decoupling means Paper 2 can evolve its modeling internally without breaking Edeon's loader, as long as the manifest schema is respected. The contract is documented in `docs/PAPER2_ARTIFACT_CONTRACT.md`.

---

## 5. Per-Endpoint Specifications

### 5.1 photostability_class (alerts-only)

```yaml
endpoint: photostability_class
mode: stratified_structural_alerts
rules_file: python/edeon_models/backends/alerts/rules/photostability.yaml
classification:
  classes: [Stable, Moderate, Susceptible]
  default: Stable
deployment:
  endpoint_id: photostability_class
  tier: 1
  tier_label: qualitative
  no_training: true
```

### 5.2 bcf

```yaml
endpoint: bcf
phase1_dataset: data/curated/bcf/v1.0
target_column: value_log
target_kind: regression
primary_split: scaffold
additional_splits: [random]
calibration_split: scaffold/cal
test_split: scaffold/test
baseline_models: [random_forest, xgboost]
include_chemprop: true
auxiliary_features: [ionizable_flag, logd_pH7]
pka_predictor: auto         # auto | pkai | none
chemprop:
  hpo_trials: 20
  ensemble_seeds: [0, 1, 2, 3, 4]
  max_epochs: 50
ad:
  k: 5
  fp_radius: 2
  fp_bits: 2048
conformal:
  alpha: 0.05
  method: split
optional_features:
  qrasar_similarity: true     # Enable q-RASAR-style similarity features
  k_neighbors_for_similarity: 5
performance_targets:
  overall_r2: 0.65
  non_ionizable_r2: 0.70
  ionizable_r2: 0.55
  rmse_log: 0.55
  coverage_95: [0.93, 0.97]
  ad_coverage_test: 0.55
subset_reporting: [ionizable, non_ionizable]
deployment:
  endpoint_id: bcf
  tier: 1
  fallback_to_tier: 2
```

### 5.3 selectivity_profile

```yaml
endpoint: selectivity_profile
paper2_artifacts_dir: data/paper2_artifacts/v1.0
expected_pairs: 12
required_manifest_version: ">=1.0.0,<2.0.0"
performance_targets:
  min_pairs_loaded: 8           # Must load at least 8 of 12 pairs to register
  min_loaded_pair_test_spearman: 0.4
deployment:
  endpoint_id: selectivity_profile
  tier: 1
  no_local_training: true
  lazy_registration: true       # Register only when artifacts present and valid
```

---

## 6. Task Manifest

### Group A — Shared Infrastructure Extensions

#### Task A1: Add SELECTIVITY_PROFILE to Endpoint enum
**Depends on:** Phase 0.
**File:** `python/edeon_models/endpoints.py`
**Action:** Add:

```python
SELECTIVITY_PROFILE = "selectivity_profile"
```

`endpoint_metadata`: units = "log10_ratio", direction = "higher = more selective for pest target".

**Acceptance:** Enum updated; metadata helper returns the new entry.

---

#### Task A2: StratifiedAlertsBackend
**Depends on:** Phase 4 `StructuralAlertsBackend`.
**File:** `python/edeon_models/backends/alerts/stratified_alerts_backend.py`

```python
class StratifiedAlertsBackend(ModelBackend):
    """Alerts backend that combines matches across categories into a final
    classification per a configurable logic function."""

    def __init__(self, endpoint: Endpoint, rules_file: Path,
                 classification_fn: Callable[[dict[str, list]], str]):
        ...
```

Loading the rules file expects YAML structured as:

```yaml
endpoint: photostability_class
version: 1.0
description: |
  Stratified structural alerts for UV photostability...
categories:
  chromophores:
    - id: aromatic_nitro
      smarts: "[c][N+](=O)[O-]"
      description: ...
      references: [...]
    - ...
  photoreactive:
    - id: peroxide
      smarts: "[OX2]-[OX2]"
      description: ...
      references: [...]
  hydrolytic_labile:
    - id: anhydride
      smarts: "[CX3](=O)[OX2][CX3]=O"
      ...
```

The backend evaluates SMARTS per category, builds `{category_name: matched_list}`, then calls the user-provided `classification_fn` to produce the final categorical class.

**Acceptance:** Loads rules, evaluates against a small test panel, classification matches expected.

---

#### Task A3: Ionization utilities
**Depends on:** Phase 2.
**File:** `python/edeon_train/shared/ionization.py`

```python
def detect_ionizable(smiles: str) -> bool:
    """Heuristic ionizability check via functional group SMARTS.
       Should match Phase 1's curation rule.
       Returns True if compound has acidic or basic group expected
       to be ionized at pH 3-11."""

def predict_pka(smiles: str, predictor: Literal["pkai", "auto", "none"] = "auto") -> Optional[float]:
    """Attempt to predict pKa using available predictor.
       Returns None if no predictor available."""

def compute_logd(logp: float, pka: float, ph: float = 7.4,
                 is_acid: bool = True) -> float:
    """Henderson-Hasselbalch-derived LogD at specified pH."""

def featurize_ionization(smiles_list: list[str],
                          pka_predictor: Literal["pkai", "auto", "none"] = "auto"
                         ) -> np.ndarray:
    """Returns (n_compounds, 3) array: [ionizable_flag, predicted_pka, logd_pH7].
       NaN where pKa unavailable."""
```

For the pKAI integration, attempt `import pkai`. If unavailable, log a warning and proceed with `ionizable_flag` only.

**Acceptance:** Unit test on 10 known compounds (acetic acid, ethylamine, glucose, glyphosate, imidacloprid, ...) — ionization correctly detected; pKa within 1.5 log units of literature when predictor available.

---

### Group B — Photostability Alerts

#### Task B1: Photostability rules file
**Depends on:** A2.
**File:** `python/edeon_models/backends/alerts/rules/photostability.yaml`
**Action:** Author per Section 4.1.1. Include ≥ 6 alerts per category. SMARTS patterns must:
- Match expected positive controls (e.g., nitrobenzene, formaldehyde, benzoyl peroxide, methyl acetate)
- Not over-trigger on safe controls (ethanol, glucose, caffeine should match few or no alerts)

Each alert entry follows the schema in Task A2.

Verify by writing `tests/test_photostability_rules.py` with a small positive/negative panel and asserting expected matches.

**Acceptance:** Rules file validates; smoke test confirms expected matches on 20-compound panel.

---

#### Task B2: Photostability backend wiring
**Depends on:** B1, A2.
**Action:** Create `endpoints/photostability/config.yaml`, `card.py`. The `__init__.py` constructs a `StratifiedAlertsBackend(endpoint=PHOTOSTABILITY_CLASS, rules_file=..., classification_fn=classify_photostability)` where `classify_photostability` implements the logic from Section 4.1.2.

Register in `build_default_registry()`: replaces the existing T2 LogP-based photostability backend.

**Acceptance:** `reg.get(Endpoint.PHOTOSTABILITY_CLASS).tier() == 1`. Predicting on benzoyl peroxide returns "Susceptible"; on glucose returns "Stable".

---

#### Task B3: Photostability documentation
**Depends on:** B2.
**Files:**
- `docs/PHASE5_PHOTOSTABILITY_PROTOCOL.md` — full methodology, alert list rationale, classification logic
- `docs/TIER1_MODEL_CARDS/photostability_alerts.md` — model card
- `docs/EYE_IRRITATION_ALERTS_RATIONALE.md` (Phase 4) is the template

**Acceptance:** Documents committed.

---

### Group C — BCF Training

#### Task C1: BCF endpoint config and orchestrator
**Depends on:** A3, Phase 2 done.
**Files:** `python/edeon_train/endpoints/bcf/{config.yaml, train.py}`
**Action:** Copy a Phase 2 endpoint folder as starting template (e.g., bee_acute_oral_ld50). Modify:
- Config per Section 5.2.
- `train.py` calls `featurize_ionization` to produce the additional features; concatenate to baseline feature vector.
- Chemprop: pass ionization features via `--features-path` (Chemprop 2.x) or equivalent.
- If `qrasar_similarity` is enabled, compute k-nearest-neighbor similarity features on the training set fingerprint database.
- Evaluation script computes overall and per-subset metrics.

**Acceptance:** `edeon-train bcf train` runs to completion. HPO history saved.

---

#### Task C2: q-RASAR similarity features (optional)
**Depends on:** C1, A3.
**File:** Extend `python/edeon_train/shared/featurize.py` with:

```python
def qrasar_similarity_features(query_smiles: list[str],
                                training_smiles: list[str],
                                training_y: np.ndarray,
                                k: int = 5,
                                fp_radius: int = 2,
                                fp_bits: int = 2048) -> np.ndarray:
    """Returns per-query: [
        mean Tanimoto to k nearest training neighbors,
        max Tanimoto to k nearest training neighbors,
        mean y of k nearest training neighbors (weighted by Tanimoto),
        std y of k nearest training neighbors,
    ]
    Shape: (n_query, 4)
    """
```

Use these as auxiliary features in BCF only. If implementation budget is tight, skip and document; performance target adjusts accordingly.

**Acceptance:** Function returns correct shape and values on a small test set.

---

#### Task C3: Run full BCF pipeline
**Depends on:** C1, optionally C2.
**Action:** train → calibrate → evaluate (gate opens once) → deploy → card. Use Phase 2's `TrainedTier1Backend` as the deployed class. Subset metrics in validation report.

**Acceptance:** Performance targets met or gaps documented. T1 backend registered.

---

#### Task C4: BCF card
**Depends on:** C3.
**Files:** `card.py` + `docs/TIER1_MODEL_CARDS/bcf.md`
**Action:** Generate with subset metrics (ionizable / non-ionizable). Document failure modes per Section 4.2.3.

**Acceptance:** Card complete.

---

#### Task C5: BCF protocol document
**Depends on:** C3.
**File:** `docs/PHASE5_BCF_PROTOCOL.md`
**Action:** Document the full methodology: feature set including ionization, pKa predictor used (or absent), subset reporting, q-RASAR features if used, performance gap on ionizables.

**Acceptance:** Document committed.

---

### Group D — Selectivity Integration

#### Task D1: Paper 2 artifact contract document
**Depends on:** none (can be drafted independently of artifact arrival).
**File:** `docs/PAPER2_ARTIFACT_CONTRACT.md`
**Action:** Full contract document per Section 4.3.1-4.3.3:
- Directory structure
- manifest.json JSON schema
- pair_card.yaml schema
- Featurizer specification format
- Model artifact format expectations (sklearn pickle / PyTorch state_dict / Chemprop checkpoint)
- AD format
- Conformal calibration format
- Version/compatibility policy

This document is the contract Paper 2 must honor. Share with the Paper 2 team for review before they finalize their export format.

**Acceptance:** Document committed and reviewed by the Paper 2 contributor.

---

#### Task D2: Artifact loader and schema validation
**Depends on:** D1.
**File:** `python/edeon_models/backends/selectivity/paper2_loader.py`

```python
class Paper2Manifest(BaseModel):
    """Pydantic model validating Paper 2's manifest.json."""
    paper2_version: str
    created: datetime
    target_pairs: list[TargetPairMeta]


class TargetPairMeta(BaseModel):
    pair_id: str
    display_name: str
    pest_organism: str
    pest_uniprot: Optional[str] = None
    nontarget_organism: str
    nontarget_uniprot: Optional[str] = None
    category: Literal["insecticide", "fungicide", "herbicide", "control"]
    model_artifact: str
    featurizer_artifact: str
    conformal_artifact: str
    ad_artifact: str
    pair_card: str
    performance: dict[str, float]
    selectivity_units: str
    direction: str


def load_paper2_manifest(artifacts_dir: Path) -> Paper2Manifest:
    """Validate and load Paper 2 manifest. Raise if any required path missing."""


def verify_paper2_artifacts(artifacts_dir: Path) -> tuple[bool, list[str]]:
    """Verify all referenced files exist and are loadable.
    Returns (ok, errors)."""
```

**Acceptance:** Validates a synthetic well-formed manifest. Rejects manifests with missing fields or missing referenced files.

---

#### Task D3: PairBackend implementation
**Depends on:** D2.
**File:** `python/edeon_models/backends/selectivity/paper2_loader.py`

```python
class PairBackend:
    """Loads and runs inference for a single ortholog pair."""

    @classmethod
    def load(cls, pair_dir: Path) -> "PairBackend":
        """Load model, featurizer, conformal calibrator, AD."""

    def predict_single(self, smiles: str) -> dict:
        """Returns:
            {
                "value": float,           # log10 selectivity ratio
                "ci_lower": float,
                "ci_upper": float,
                "ad_status": ADStatus,
                "ad_score": float,
            }
        """
```

Model loading must handle multiple artifact types:
- `.pkl`/`.joblib` → sklearn (RF, XGBoost)
- `.pt`/`.ckpt` → PyTorch (Chemprop, custom NNs)
- Distinguish via file extension and the `model` section of `pair_card.yaml`

**Acceptance:** Loads a synthetic PairBackend (sklearn RF on dummy data with frozen calibration and AD), predicts on a SMILES, returns the expected schema.

---

#### Task D4: SelectivityProfileBackend
**Depends on:** D3, A1.
**File:** `python/edeon_models/backends/selectivity/selectivity_backend.py`

Implement per Section 4.3.4.

```python
class SelectivityProfileBackend(ModelBackend):
    def predict(self, smiles, conditions=None) -> list[Prediction]:
        # ... (per 4.3.4)

    def metadata(self) -> ModelCard:
        """Composed from individual pair cards.
        Description summarises the 12 pairs."""
```

The Prediction's `value` for a profile query:
- `value.kind = "categorical"`, `value.categorical = "profile"` (sentinel)
- `provenance.pair_results = {pair_id: {value, ci_lower, ci_upper, ad_status, ...}}`
- `provenance.summary = {n_pairs_with_high_selectivity, n_pairs_with_poor_selectivity, ...}`

For a single-pair query:
- `value.kind = "numeric"`, `value.numeric = <selectivity score>`
- `ci_lower`/`ci_upper` from the pair's conformal
- `ad_status` from the pair's AD
- `provenance.pair_id = ...`, `provenance.pair_card_summary = ...`

**Acceptance:** Profile query on a synthetic backend with 3 stub pairs returns prediction with all three pair_results present. Single-pair query returns numeric value with CI.

---

#### Task D5: Lazy registration in registry
**Depends on:** D4.
**File:** Modify `build_default_registry()`.
**Action:**

```python
def _maybe_register_selectivity(registry: BackendRegistry):
    artifacts_dir = Path("data/paper2_artifacts/v1.0")
    if not artifacts_dir.exists():
        logger.info("Paper 2 artifacts not found at %s — selectivity backend not registered", artifacts_dir)
        return

    try:
        manifest = load_paper2_manifest(artifacts_dir)
        ok, errors = verify_paper2_artifacts(artifacts_dir)
        if not ok:
            logger.warning("Paper 2 artifacts present but invalid: %s", errors)
            return
        if len(manifest.target_pairs) < 8:
            logger.warning("Paper 2 artifacts have only %d pairs; need ≥ 8 to register", len(manifest.target_pairs))
            return
        backend = SelectivityProfileBackend(artifacts_dir)
        registry.register(backend)
        logger.info("Selectivity backend registered with %d pairs", len(manifest.target_pairs))
    except Exception as e:
        logger.error("Failed to register selectivity backend: %s", e, exc_info=True)
```

**Acceptance:** With no artifacts directory, registry builds without selectivity backend. With a valid synthetic artifacts directory, backend registers.

---

#### Task D6: Selectivity card
**Depends on:** D4, D5.
**Files:** `card.py` + `docs/TIER1_MODEL_CARDS/selectivity_profile.md`
**Action:** Auto-generate from individual pair cards. Aggregate description: "Cross-species selectivity profile across N target pairs spanning insecticides (M pairs), fungicides (O pairs), herbicides (P pairs), and controls."

Cite Paper 2 publication once published.

**Acceptance:** Card complete.

---

### Group E — Frontend Updates

#### Task E1: Photostability panel
**Depends on:** B2.
**Files:** Locate existing photostability component (`Inspector.tsx` per the audit). Replace the animated decay curve with:
- Risk class badge (Stable green, Moderate yellow, Susceptible red)
- Three small expandable sections: Chromophores, Photoreactive, Hydrolytic
- Each section shows matched alerts (id, description, citation link)
- "What this means" tooltip explaining: "This is a qualitative screening, not a quantitative half-life. Absence of alerts does not guarantee photostability."

Remove the "Moderate / High Solar" toggle. Remove the SVG decay chart.

**Acceptance:** Panel renders for known compounds: benzoyl peroxide → Susceptible with peroxide alert; nitrobenzene → Susceptible with aromatic_nitro alert; ethanol → Stable.

---

#### Task E2: BCF row in fate gauge
**Depends on:** C3.
**Action:** Add a BCF row to the existing fate gauge alongside Koc, DT50, GUS. Use the Phase 0 `PredictionDisplay` component. Show the value with units (log BCF), CI, tier badge, AD warning.

**Acceptance:** BCF row renders.

---

#### Task E3: Selectivity panel (NEW component)
**Depends on:** D4.
**File:** `src/components/selectivity/SelectivityPanel.tsx` (or similar location matching project layout)

Layout:
- 12 cells in a 4×3 or 3×4 grid (group by category: insecticides, fungicides, herbicides + controls)
- Each cell shows: pair name (short), selectivity score, color-coded background (red poor, yellow moderate, green good), small AD indicator
- Click a cell → side panel opens with detail: pair card summary, CI, organism info, references
- Top of panel: summary stats ("8 of 12 pairs predicted in domain; selectivity profile is favorable for X pairs, concerning for Y")

Gracefully handle the case where the selectivity backend is not registered (Paper 2 artifacts absent): show a placeholder "Selectivity prediction requires Paper 2 model artifacts. See documentation."

**Acceptance:** Panel renders with 12 cells when backend present; gracefully degrades when absent.

---

### Group F — Validation and CI

#### Task F1: Phase 5 regression CI
**Depends on:** B2, C3, D5.
**File:** `.github/workflows/tier1_phase5_regression.yml`

Smoke tests:
- BCF backend loads and predicts on 20 reference compounds within tolerance
- Photostability backend loads; reference panel returns expected risk classes
- Selectivity backend either: loads with valid synthetic artifacts, OR gracefully returns "not registered" — both states are acceptable

Reference compounds and tolerances in `tests/regression/tier1_phase5_tolerance.yaml`.

**Acceptance:** CI green.

---

#### Task F2: Synthetic Paper 2 test fixture
**Depends on:** D5.
**File:** `tests/fixtures/paper2_synthetic_v1.0/`
**Action:** Create a minimal valid Paper 2 artifact bundle for testing:
- 3 pair directories (one insecticide, one fungicide, one herbicide)
- Each with a trivial sklearn RF model on a synthetic dataset
- Valid manifest, pair cards, AD/conformal artifacts
- Used in CI for testing the selectivity loader without requiring Paper 2 to be finished

**Acceptance:** Fixture validates and loads as expected.

---

#### Task F3: End-to-end Phase 5 test
**Depends on:** all previous.
**File:** `tests/integration/test_t1_phase5_e2e.py`

Test that:
- Photostability returns categorical class with provenance.matched alerts per category
- BCF returns numeric value with CI and subset-aware AD
- Selectivity returns profile when artifacts present, gracefully handles absence

**Acceptance:** Test passes.

---

#### Task F4: Benchmark results document
**Depends on:** C3, B2, D5.
**File:** `docs/PHASE5_BENCHMARK_RESULTS.md`
**Action:** Auto-generated summary table. For BCF: overall + subset metrics. For photostability: qualitative description + summary statistics on the rule library (n_alerts per category, etc.). For selectivity: per-pair metrics from the loaded artifacts.

**Acceptance:** Document committed.

---

## 7. Acceptance Criteria for Phase 5 Complete

Phase 5 is complete when ALL of the following hold:

1. `Endpoint.SELECTIVITY_PROFILE` added to enum.
2. Photostability T1 alerts backend deployed and registered; legacy T2 LogP-based photostability superseded.
3. BCF T1 backend trained, deployed, registered. Overall and subset performance targets met or documented gap.
4. Selectivity infrastructure complete:
   - Artifact contract document published.
   - Loader + PairBackend + SelectivityProfileBackend implemented and tested with synthetic fixture.
   - Lazy registration: when valid Paper 2 artifacts are at `data/paper2_artifacts/v1.0/`, the backend registers automatically.
5. Frontend: photostability panel redesigned, BCF row added to fate gauge, selectivity panel new component (renders with synthetic fixture; gracefully degrades when absent).
6. CI regression workflow passes.
7. `PHASE5_PHOTOSTABILITY_PROTOCOL.md`, `PHASE5_BCF_PROTOCOL.md`, `PAPER2_ARTIFACT_CONTRACT.md`, `PHASE5_BENCHMARK_RESULTS.md`, `PHASE5_NOTES.md` are populated.
8. Model cards present for all three endpoints (BCF, photostability_alerts, selectivity_profile).

---

## 8. Out of Scope (for Phase 5)

Do **not** in Phase 5:

- Train selectivity models locally — that is Paper 2's job.
- Implement docking, FEP+, or any 3D structural pipeline locally — Paper 2 uses these, Edeon consumes outputs only.
- Replace the 3D viewer's docking implementation (Phase 6).
- Replace the bioisostere engine (Phase 6).
- Implement EPA T.E.S.T as a T3 backend for any endpoint.
- Train models for endpoints already covered (Phases 2-4).
- Add new endpoints beyond the three specified.
- Modify Phase 1 curation rules.
- Implement live external API queries.

If the agent identifies a blocker, document in PHASE5_NOTES.md and stop.

---

## 9. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| pKa predictor (pkai) not installable | Fall back to ionizable_flag only; document; downstream LogD feature not available, retrain without it |
| BCF performance on ionizables remains poor (R² < 0.5) | Document honestly in card; this matches published reality (Pore et al. 2024 R²=0.57) — not a failure, an honest result |
| q-RASAR similarity features don't improve BCF | Drop them; document; they're optional anyway |
| Photostability SMARTS over-trigger on common pesticides | Test against 30 marketed pesticides as control; tune categories; some over-flagging is acceptable since the output is qualitative |
| Paper 2 not finished by Phase 5 execution | Lazy registration handles this; integration infrastructure ready when artifacts arrive |
| Paper 2 artifact format changes after contract published | Version the contract (>=1.0.0,<2.0.0 semver); breaking changes require contract update |
| Selectivity panel demo with synthetic fixture is too obviously synthetic | Acceptable for development; for sales demos, gate on real Paper 2 artifacts being present |
| Selectivity backend loads but several pairs fail | The lazy registration policy requires ≥ 8 of 12 pairs to register; below that, log warning and skip |

---

## 10. Conventions

- Random seeds: 42 for BCF splits and HPO; alerts and selectivity are deterministic by nature.
- Tier labeling: photostability alerts uses `tier=1` with `tier_label="qualitative"` in the card.
- Selectivity profile predictions: `value.kind = "categorical"` with `value.categorical = "profile"` as sentinel; the actual per-pair values live in provenance.
- Provenance fields for selectivity single-pair: `pair_id`, `pair_card_summary`, `component_predictions`.
- Provenance fields for selectivity profile: `pair_results` (dict per pair), `summary` (counts and aggregate stats).
- Provenance fields for photostability: `category_A_matches`, `category_B_matches`, `category_C_matches`, `classification_logic`, `risk_class`.

---

## 11. Handoff Notes

Phase 5 outputs feed:

- **Phase 6** — last engineering cleanup (real docking, bioisosteres). After Phase 5, the only LogP-heuristic backends remaining are inactive fallbacks; the active product is fully T1.
- **Paper 2 publication** — selectivity backend deployment is the productization story. The paper's discussion can cite Edeon as the implementation.
- **Paper 3 — Edeon Open Benchmarks** — BCF is the last new ecotox/fate dataset in the benchmark suite.
- **Commercial pitch** — after Phase 5: every fate-gauge cell, every toxicity-panel cell, the new selectivity panel is T1. The product story is "every prediction is a trained, validated model with calibrated uncertainty and applicability domain; where prediction is genuinely impossible, we show transparent qualitative alerts with citations rather than fake numbers." That story is defensible end-to-end.

After Phase 5, the credibility floor for an expert evaluator is around 8.5/10 (per the earlier subjective scale). The remaining gaps are stylistic (3D viewer docking is currently misleading; bioisosteres are rule-based) rather than scientific — Phase 6 closes those.

---

## 12. Deviation Log

Maintain `docs/PHASE5_NOTES.md` recording:
- pKa predictor used (pkai version, or "none" if unavailable).
- Whether q-RASAR similarity features were implemented.
- BCF subset performance gap (final numbers).
- Photostability SMARTS refinements made from initial example rules.
- Number of Paper 2 pairs loaded; any pairs that failed loading and why.
- Whether selectivity backend was registered with real artifacts or kept as integration-ready with synthetic fixtures.
- Final test-set evaluation timestamp for BCF.

---

**End of Phase 5 Specification.**
