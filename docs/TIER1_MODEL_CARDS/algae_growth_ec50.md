# Model Card: Edeon Tier-1 Reference Algae Growth Ec50 (Classification)

**Model ID:** `t1_algae_growth_ec50_v1.0_cls` | **Version:** `v1.0_cls`

## Description
Binary classification QSAR model combining Random Forest, XGBoost, and a 5-seed Chemprop D-MPNN ensemble with inductive conformal prediction sets. Predicts toxic/nontoxic with calibrated probabilities and a Tanimoto k-NN applicability domain auditor.

## Performance (Scaffold Test Set)
- **Balanced Accuracy:** 0.5000
- **AUC-ROC:** 0.27999999999999997
- **F1:** 0.4706
- **ECE:** 0.3530
- **Conformal Coverage (95%):** 93.3%
- **Mean Set Size:** 1.93

## Applicability Domain
- **Method:** Tanimoto 5-NN Morgan Fingerprint
- **In-Domain Distance Threshold (95%):** 0.9041
- **Borderline Distance Threshold (99%):** 0.9265

## References
- Vovk, V., Gammerman, A., & Shafer, G. (2005). Algorithmic learning in a random world.
- Norinder, U., et al. (2014). Introducing conformal prediction in predictive modeling.
