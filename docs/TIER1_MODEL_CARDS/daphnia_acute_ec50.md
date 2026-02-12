# Model Card: Edeon Tier-1 Reference Daphnia Acute Ec50

**Model ID:** `t1_daphnia_acute_ec50_v1.0` | **Version:** `v1.0`

## Description
High-fidelity reference QSAR model combining Random Forest, XGBoost, and a 5-seed Chemprop D-MPNN ensemble. Features split conformal prediction intervals (95%) and a Tanimoto k-NN applicability domain auditor.

## Performance (Scaffold Test Set)
- **RMSE:** 1.0153
- **R²:** 0.5810
- **MAE:** 0.8295
- **95% Conformal Coverage:** 100.0%

## Applicability Domain
- **Method:** Tanimoto 5-NN Morgan Fingerprint
- **In-Domain Distance Threshold (95%):** 0.8497
- **Borderline Distance Threshold (99%):** 0.8937

## References
- Bemis, G. W., & Murcko, M. A. (1996). The properties of known drugs. 1. Molecular frameworks. J. Med. Chem.
- Vovk, V., Gammerman, A., & Shafer, G. (2005). Algorithmic learning in a random world. Springer Science & Business Media.
