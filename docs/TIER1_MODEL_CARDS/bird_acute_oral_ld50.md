# Model Card: Edeon Tier-1 Reference Bird Acute Oral Ld50 (Classification)

**Model ID:** `t1_bird_acute_oral_ld50_v1.0_cls` | **Version:** `v1.0_cls`

## Description
Binary classification QSAR model combining Random Forest, XGBoost, and a 5-seed Chemprop D-MPNN ensemble with inductive conformal prediction sets. Predicts toxic/nontoxic with calibrated probabilities and a Tanimoto k-NN applicability domain auditor.

## Performance (Scaffold Test Set)
- **Balanced Accuracy:** 0.4800
- **AUC-ROC:** 0.4666666666666666
- **F1:** 0.7869
- **ECE:** 0.0927
- **Conformal Coverage (95%):** 98.6%
- **Mean Set Size:** 1.95

## Applicability Domain
- **Method:** Tanimoto 5-NN Morgan Fingerprint
- **In-Domain Distance Threshold (95%):** 0.8449
- **Borderline Distance Threshold (99%):** 0.9022

## References
- Vovk, V., Gammerman, A., & Shafer, G. (2005). Algorithmic learning in a random world.
- Norinder, U., et al. (2014). Introducing conformal prediction in predictive modeling.
