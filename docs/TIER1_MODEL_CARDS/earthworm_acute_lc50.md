# Model Card: Edeon Tier-1 Reference Earthworm Acute Lc50

**Model ID:** `t1_earthworm_acute_lc50_v1.0` | **Version:** `v1.0`

## Description
High-fidelity reference QSAR model combining Random Forest, XGBoost, and a 5-seed Chemprop D-MPNN ensemble. Features split conformal prediction intervals (95%) and a Tanimoto k-NN applicability domain auditor.

## Performance (Scaffold Test Set)
- **RMSE:** 0.7691
- **R²:** nan
- **MAE:** 0.7691
- **95% Conformal Coverage:** 100.0%

## Applicability Domain
- **Method:** Tanimoto 5-NN Morgan Fingerprint
- **In-Domain Distance Threshold (95%):** 0.9048
- **Borderline Distance Threshold (99%):** 0.9048

## References
- Bemis, G. W., & Murcko, M. A. (1996). The properties of known drugs. 1. Molecular frameworks. J. Med. Chem.
- Vovk, V., Gammerman, A., & Shafer, G. (2005). Algorithmic learning in a random world. Springer Science & Business Media.
