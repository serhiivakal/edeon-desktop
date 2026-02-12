# Model Card: Edeon Tier-1 Reference Bee Acute Contact Ld50 (Classification)

**Model ID:** `t1_bee_acute_contact_ld50_v1.0_cls` | **Version:** `v1.0_cls`

## Description
Binary classification QSAR model combining Random Forest, XGBoost, and a 5-seed Chemprop D-MPNN ensemble with inductive conformal prediction sets. Predicts toxic/nontoxic with calibrated probabilities and a Tanimoto k-NN applicability domain auditor.

## Performance (Scaffold Test Set)
- **Balanced Accuracy:** 0.7608
- **AUC-ROC:** 0.8067993366500829
- **F1:** 0.6286
- **ECE:** 0.0837
- **Conformal Coverage (95%):** 96.5%
- **Mean Set Size:** 1.48

## Applicability Domain
- **Method:** Tanimoto 5-NN Morgan Fingerprint
- **In-Domain Distance Threshold (95%):** 0.8524
- **Borderline Distance Threshold (99%):** 0.8921

## References
- Vovk, V., Gammerman, A., & Shafer, G. (2005). Algorithmic learning in a random world.
- Norinder, U., et al. (2014). Introducing conformal prediction in predictive modeling.
