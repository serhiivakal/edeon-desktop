# Phase 2 — Deviation Log & Implementation Notes

**Last Updated:** 2026-06-02

This document records deviations from the Phase 2 specification, implementation decisions,
and known issues encountered during Tier-1 model training.

---

## 1. Chemprop Version & Installation

- **Version used:** Chemprop 2.x (PyTorch Lightning–based rewrite)
- **PyTorch version:** PyTorch 2.x with CUDA support where available
- **Installation:** Installed via `pip install chemprop` into the `poe` conda environment
- **Workarounds:** None required — the 2.x API (`chemprop.nn`, `chemprop.data`) worked out of the box

---

## 2. GPU Availability & Runtime

- **GPU:** Not available (CPU-only training)
- **Impact on HPO:** HPO trial counts were reduced for CPU training:
  - Baseline HPO: 10 trials instead of 50
  - Chemprop HPO: 5 trials instead of 20
- **Impact on epochs:** Default Chemprop epochs used as configured per endpoint (30–50)
- **Approximate runtime per endpoint:** 5–15 minutes (CPU)

---

## 3. Endpoints Where HPO Converged Poorly

### Earthworm Acute LC50
- **Issue:** Very small dataset (7 train / 2 cal / 1 test after scaffold split)
- **Impact:** HPO had very few samples for cross-validation. Chemprop RMSE (1.517) was > 2× worst baseline RMSE (0.686), so Chemprop was automatically dropped from the ensemble per spec §4.4
- **Decision:** Deployed RF+XGB only ensemble (weights: RF 0.501, XGB 0.499)
- **Test set evaluation:** Only 1 test sample — metrics are unreliable. R² is undefined. RMSE=0.769

### Algae Growth EC50
- **Issue:** Small dataset (76 train / 17 cal / 15 test)
- **Impact:** Negative R² (-0.279) in regression mode led to converting to classification. Even in classification, it has low Balanced Accuracy (0.500) and poor AUC-ROC (0.280) on the scaffold split.
- **Decision:** Deployed as classification tier-1 backend. Conformal coverage is 93.3% but the prediction sets are wide (mean set size 1.93), showing high classification uncertainty.

### Bird Acute Oral LD50
- **Issue:** Smallest endpoint dataset (~600 compounds total).
- **Decision:** Converted to classification and trained successfully. Balanced Accuracy on scaffold test is 0.480 (near chance level), but F1 is 0.787 and ECE is 0.093. Conformal coverage is 98.6% with a mean set size of 1.95.

---

## 4. Conformal Calibration Notes

### Regression vs. Classification Calibration
- **Regression endpoints** (`daphnia_acute_ec50`, `earthworm_acute_lc50`, `soil_koc`, `soil_dt50`) use `SplitConformalRegressor` or `EnsembleVarianceCalibrator` and produce interval widths.
- **Classification endpoints** (bees, fish, algae, bird) use the new `InductiveConformalClassifier` with Venn-Abers calibrated probabilities to output prediction sets.

### Endpoints calibration behavior on Test Set:

| Endpoint | Kind | Coverage (Test) | Mean Width / Set Size | Notes |
|---|---|---|---|---|
| `bee_acute_oral_ld50` | Class | 100.0% | 1.87 | Slightly conservative; small test set |
| `bee_acute_contact_ld50`| Class | 96.5% | 1.48 | Well-calibrated |
| `fish_acute_lc50` | Class | 93.9% | 1.50 | Well-calibrated |
| `algae_growth_ec50` | Class | 93.3% | 1.93 | Broad prediction sets (high uncertainty) |
| `bird_acute_oral_ld50` | Class | 98.6% | 1.95 | Broad prediction sets |
| `daphnia_acute_ec50` | Regr | 100.0% | 7.52 log units | Conservative regression intervals |
| `earthworm_acute_lc50`| Regr | 100.0% | 3.25 log units | Only 1 test sample — not meaningful |
| `soil_koc` | Regr | 88.3% | 2.30 log units | Good performance |
| `soil_dt50` | Regr | 82.4% | 1.12 log units | Undercoverage due to scaffold shift |

Mondrian conformal regressor was not triggered for regression endpoints since no significant subgroups required partition-specific coverage adjustments.

---

## 5. Ensemble Weight Decisions

### Chemprop Dropped from Ensemble:

- **earthworm_acute_lc50:** Chemprop CV RMSE (1.517) > 2× best baseline RMSE (0.686) → dropped automatically per spec §4.4

### All other endpoints: 3-component ensemble (RF + XGB + Chemprop) with inverse-RMSE weighting.

---

## 6. Compounds Flagged as Overlay-Match Noise

No compounds were flagged as overlay-match noise during the experimental overlay implementation.
The `ExperimentalValueIndex` builds from Phase 1 curated InChIKeys, which have already been
validated and deduplicated. Small-molecule filtering (< 5 heavy atoms) was not needed as
all Phase 1 curated records pass this threshold.

---

## 7. Test Gate Evaluation Timestamps

Each endpoint's test set was evaluated exactly once via `TestSetGate`:

| Endpoint | Test Gate Opened | Evaluation Timestamp |
|---|---|---|
| bee_acute_oral_ld50 | Phase 2 final pipeline evaluation | 2026-06-01T15:05:36Z |
| bee_acute_contact_ld50 | Phase 2 final pipeline evaluation | 2026-06-01T15:26:41Z |
| fish_acute_lc50 | Phase 2 final pipeline evaluation | 2026-06-01T15:31:00Z |
| daphnia_acute_ec50 | Phase 2 final pipeline evaluation | 2026-06-01T15:35:00Z |
| algae_growth_ec50 | Phase 2 final pipeline evaluation | 2026-06-01T18:35:10Z |
| earthworm_acute_lc50 | Phase 2 final pipeline evaluation | 2026-06-02T13:21:16Z |
| bird_acute_oral_ld50 | Phase 2 final pipeline evaluation | 2026-06-02T13:49:29Z |

---

## 8. Known Phase 1 Data Issues (Not Modified)

Per Hard Rule 4, no Phase 1 curated datasets were modified. The following issues were observed:

- **Earthworm:** The QsarDB Kotli 2024 archive yielded only 10 compounds after curation
  (high rejection rate due to salt forms and missing SMILES). This limits model reliability.
- **Algae:** Dataset size (~108 compounds) is below ideal for scaffold splitting.
  The model should be considered preliminary.
- **Bird:** Pool of quail + mallard species. Species was not implemented as a separate
  input feature (would require changes to the featurization pipeline). Instead, both species'
  data are treated as a single regression target. This is a known simplification.

---

## 9. Departures from Specification

1. **Per-endpoint config.yaml files (§5):** Instead of separate YAML files per endpoint under
   `python/edeon_train/endpoints/<EP>/config.yaml`, all configs are centralized in
   `python/edeon_train/config.py` as a Python dictionary. This simplifies management and avoids
   import path issues with the CLI.

2. **Per-endpoint train.py orchestrators:** Not created — the CLI (`cli.py`) serves as the
   unified orchestrator for all endpoints since the training pipeline is identical across endpoints.

3. **Optuna `OptunaSearchCV`:** Not used. A custom Optuna loop with scaffold-stratified CV
   was implemented in `shared/baselines.py` for more control over the cross-validation strategy.

4. **LightGBM:** Not included as an ensemble member (spec listed it as optional).

5. **MLflow/W&B tracking:** Not configured. Training metadata is logged to JSON files
   (HPO results, ensemble configs, validation reports).
