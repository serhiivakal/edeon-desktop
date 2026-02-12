# Model Card: Edeon Tier-1 Reference Soil Dt50 (Heteroscedastic)

**Model ID:** `t1_soil_dt50_v1.0` | **Version:** `v1.0`

## Description
Heteroscedastic mean-variance reference QSAR model combining a 5-seed PyTorch HeteroscedasticMLP ensemble and a 5-seed Chemprop MVE ensemble. Features joint aleatoric-epistemic uncertainty modeling with post-hoc variance calibration.

## Performance (Scaffold Test Set)
- **Negative Log-Likelihood (NLL):** 0.1911
- **Observed vs. Predicted σ Spearman ρ:** 0.8000
- **RMSE:** 1.0087
- **R²:** -13.3996
- **MAE:** 0.7308
- **95% Conformal Coverage:** 85.3%

## Applicability Domain
- **Method:** Tanimoto 5-NN Morgan Fingerprint
- **In-Domain Distance Threshold (95%):** 0.6154
- **Borderline Distance Threshold (99%):** 0.8032

## References
- Nix, D. A., & Weigend, A. S. (1994). Estimating the mean and variance of target distributions.
- Gustafson, D. I. (1989). Groundwater ubiquity score: a simple method for assessing pesticide leachability.
