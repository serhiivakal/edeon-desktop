# Edeon Verification Summary Report

**Overall Status:** PASS

## Conformal Coverage Summary

| Endpoint | Task Kind | Test Set Size | Empirical Coverage | Target Range | Status |
|---|---|---|---|---|---|
| bee_acute_oral_ld50 | classification | 39 | 1.0000 | [0.90, 1.00] | PASS |
| bee_acute_contact_ld50 | classification | 85 | 0.9647 | [0.90, 0.98] | PASS |
| fish_acute_lc50 | classification | 66 | 0.9394 | [0.90, 0.97] | PASS |
| daphnia_acute_ec50 | regression | 38 | 1.0000 | [0.90, 1.00] | PASS |
| algae_growth_ec50 | classification | 15 | 0.9333 | [0.90, 0.97] | PASS |
| earthworm_acute_lc50 | regression | 1 | 1.0000 | [0.90, 1.00] | PASS |
| bird_acute_oral_ld50 | classification | 74 | 0.9865 | [0.85, 1.00] | PASS |
| soil_koc | regression | 103 | 0.8738 | [0.85, 0.97] | PASS |
| soil_dt50 | regression_heteroscedastic | 34 | 0.8529 | [0.83, 0.98] | PASS |


## Soil DT50 Heteroscedastic Integrity

- **Mean Test Set NLL:** 0.1911 (Target: $\le 1.5$)
- **Spearman ρ (Predicted vs. Observed σ):** 0.8000 (Target: $\ge 0.3$)
- **DT50 Integrity Status:** PASS

---
Report auto-generated successfully.
