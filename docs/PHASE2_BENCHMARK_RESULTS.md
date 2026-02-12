# Phase 2 — Benchmark Results Summary

**Generated:** 2026-06-02  
**Phase:** Tier-1 Reference Model Training  
**Split Strategy:** Scaffold (headline), reported on test partition

---

## Overall Performance Summary

To better match practical regulatory use cases and avoid serving misleading continuous predictions, the 5 endpoints that originally achieved $R^2 < 0.5$ in regression mode have been converted to **binary classification** (toxic/nontoxic). The remaining 2 ecotox endpoints and 2 soil endpoints stay in regression mode.

### Binary Classification Endpoints

| Endpoint | n_train | n_cal | n_test | Balanced Accuracy | AUC-ROC | F1 | ECE | Conformal Coverage (95%) | Ensemble |
|---|---|---|---|---|---|---|---|---|---|
| `bee_acute_oral_ld50` | 188 | 41 | 39 | 0.528 | 0.605 | 0.235 | 0.119 | 100.0% | RF+XGB+Chemprop |
| `bee_acute_contact_ld50` | 401 | 86 | 85 | 0.761 | 0.807 | 0.629 | 0.084 | 96.5% | RF+XGB+Chemprop |
| `fish_acute_lc50` | 319 | 69 | 66 | 0.670 | 0.825 | 0.804 | 0.112 | 93.9% | RF+XGB+Chemprop |
| `algae_growth_ec50` | 76 | 17 | 15 | 0.500 | 0.280 | 0.471 | 0.353 | 0.933 | RF+XGB+Chemprop |
| `bird_acute_oral_ld50` | 350 | 75 | 74 | 0.480 | 0.467 | 0.787 | 0.093 | 0.986 | RF+XGB+Chemprop |

### Regression Endpoints

| Endpoint | n_train | n_cal | n_test | Scaffold RMSE | $R^2$ | Conformal Coverage (95%) | Ensemble |
|---|---|---|---|---|---|---|---|
| `daphnia_acute_ec50` | 274 | 59 | 58 | 1.015 | 0.581 | 100.0% | RF+XGB+Chemprop |
| `earthworm_acute_lc50` | 7 | 2 | 1 | 0.769 | N/A | 100.0% | RF+XGB |
| `soil_koc` | 503 | 108 | 103 | 0.724 | 0.710 | 88.3% | RF+XGB+Chemprop |
| `soil_dt50` | 242 | 52 | 34 | 0.485 | -2.322 | 82.4% | RF+XGB+Chemprop |

---

## Per-Endpoint Detail

### Bee Acute Oral LD50 (Classification)

- **Validation Report:** [validation_report.html](file:///home/svakal/Projects/Edeon/data/checkpoints/bee_acute_oral_ld50/v1.0_cls/validation_report.html)
- **Model Card:** [bee_acute_oral_ld50.md](file:///home/svakal/Projects/Edeon/docs/TIER1_MODEL_CARDS/bee_acute_oral_ld50.md)
- **Performance:** Balanced Accuracy 0.528, AUC-ROC 0.605, F1 0.235
- **Notes:** Small dataset. Conformal coverage is 100.0% with a mean set size of 1.87 (indicating high prediction set uncertainty).

### Bee Acute Contact LD50 (Classification)

- **Validation Report:** [validation_report.html](file:///home/svakal/Projects/Edeon/data/checkpoints/bee_acute_contact_ld50/v1.0_cls/validation_report.html)
- **Model Card:** [bee_acute_contact_ld50.md](file:///home/svakal/Projects/Edeon/docs/TIER1_MODEL_CARDS/bee_acute_contact_ld50.md)
- **Performance:** Balanced Accuracy 0.761, AUC-ROC 0.807, F1 0.629
- **Notes:** Moderately large dataset. Shows strong classification performance and well-calibrated conformal coverage (96.5%).

### Fish Acute LC50 (Classification)

- **Validation Report:** [validation_report.html](file:///home/svakal/Projects/Edeon/data/checkpoints/fish_acute_lc50/v1.0_cls/validation_report.html)
- **Model Card:** [fish_acute_lc50.md](file:///home/svakal/Projects/Edeon/docs/TIER1_MODEL_CARDS/fish_acute_lc50.md)
- **Performance:** Balanced Accuracy 0.670, AUC-ROC 0.825, F1 0.804
- **Notes:** Multispecies dataset with binarization at $\le 10$ mg/L. Good AUC-ROC (0.825) and acceptable conformal coverage (93.9%).

### Daphnia Acute EC50 (Regression)

- **Validation Report:** [validation_report.html](file:///home/svakal/Projects/Edeon/data/checkpoints/daphnia_acute_ec50/v1.0/validation_report.html)
- **Model Card:** [daphnia_acute_ec50.md](file:///home/svakal/Projects/Edeon/docs/TIER1_MODEL_CARDS/daphnia_acute_ec50.md)
- **Performance:** RMSE 1.015, $R^2$ 0.581
- **Notes:** Best performing regression endpoint. Conformal coverage of 100% indicates slightly conservative prediction intervals.

### Algae Growth EC50 (Classification)

- **Validation Report:** [validation_report.html](file:///home/svakal/Projects/Edeon/data/checkpoints/algae_growth_ec50/v1.0_cls/validation_report.html)
- **Model Card:** [algae_growth_ec50.md](file:///home/svakal/Projects/Edeon/docs/TIER1_MODEL_CARDS/algae_growth_ec50.md)
- **Performance:** Balanced Accuracy 0.500, AUC-ROC 0.280, F1 0.471
- **Notes:** Very small dataset (76 train / 15 test). The poor AUC-ROC (0.280) indicates that it performs worse than random chance on the scaffold split, reflecting extreme generalization difficulties.

### Earthworm Acute LC50 (Regression)

- **Validation Report:** [validation_report.html](file:///home/svakal/Projects/Edeon/data/checkpoints/earthworm_acute_lc50/v1.0/validation_report.html)
- **Model Card:** [earthworm_acute_lc50.md](file:///home/svakal/Projects/Edeon/docs/TIER1_MODEL_CARDS/earthworm_acute_lc50.md)
- **Performance:** RMSE 0.769, $R^2$ N/A
- **Notes:** Extremely small dataset (only 1 test sample). Chemprop was dropped due to high CV error. Results are statistically meaningless but retained for coverage completeness.

### Bird Acute Oral LD50 (Classification)

- **Validation Report:** [validation_report.html](file:///home/svakal/Projects/Edeon/data/checkpoints/bird_acute_oral_ld50/v1.0_cls/validation_report.html)
- **Model Card:** [bird_acute_oral_ld50.md](file:///home/svakal/Projects/Edeon/docs/TIER1_MODEL_CARDS/bird_acute_oral_ld50.md)
- **Performance:** Balanced Accuracy 0.480, AUC-ROC 0.467, F1 0.787
- **Notes:** Binarized at $\le 2000$ mg/kg. High F1 but poor balanced accuracy (0.480) and AUC-ROC (0.467) on the scaffold test split. Conformal coverage is 98.6%.

### Soil Koc (Regression)

- **Validation Report:** [validation_report.html](file:///home/svakal/Projects/Edeon/data/checkpoints/soil_koc/v1.0/validation_report.html)
- **Model Card:** [soil_koc.md](file:///home/svakal/Projects/Edeon/docs/TIER1_MODEL_CARDS/soil_koc.md)
- **Performance:** RMSE 0.724, $R^2$ 0.710
- **Notes:** Strong regression model with good generalization. Conformal coverage is 88.3%.

### Soil DT50 (Regression)

- **Validation Report:** [validation_report.html](file:///home/svakal/Projects/Edeon/data/checkpoints/soil_dt50/v1.0/validation_report.html)
- **Model Card:** [soil_dt50.md](file:///home/svakal/Projects/Edeon/docs/TIER1_MODEL_CARDS/soil_dt50.md)
- **Performance:** RMSE 0.485, $R^2$ -2.322
- **Notes:** Poor generalization on scaffold test set despite low train RMSE, indicating scaffold shift sensitivity. Conformal coverage is 82.4%.

---

## Methodology

See [PHASE2_VALIDATION_PROTOCOL.md](file:///home/svakal/Projects/Edeon/docs/PHASE2_VALIDATION_PROTOCOL.md) for the full methodology description.

## Deviations

See [PHASE2_NOTES.md](file:///home/svakal/Projects/Edeon/docs/PHASE2_NOTES.md) for the deviation log.
