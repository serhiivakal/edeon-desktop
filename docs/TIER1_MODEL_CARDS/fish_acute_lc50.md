# Model Card: Edeon Tier-1 Reference Fish Acute Lc50 (Classification)

**Model ID:** `t1_fish_acute_lc50_v1.0_cls` | **Version:** `v1.0_cls`

## Description
Binary classification QSAR model combining Random Forest, XGBoost, and a 5-seed Chemprop D-MPNN ensemble with inductive conformal prediction sets. Predicts toxic/nontoxic with calibrated probabilities and a Tanimoto k-NN applicability domain auditor.

## Performance (Scaffold Test Set)
- **Balanced Accuracy:** 0.6696
- **AUC-ROC:** 0.8253968253968254
- **F1:** 0.8043
- **ECE:** 0.1125
- **Conformal Coverage (95%):** 93.9%
- **Mean Set Size:** 1.50

## Applicability Domain
- **Method:** Tanimoto 5-NN Morgan Fingerprint
- **In-Domain Distance Threshold (95%):** 0.8272
- **Borderline Distance Threshold (99%):** 0.8834

## References
- Vovk, V., Gammerman, A., & Shafer, G. (2005). Algorithmic learning in a random world.
- Norinder, U., et al. (2014). Introducing conformal prediction in predictive modeling.
