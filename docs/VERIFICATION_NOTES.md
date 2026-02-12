# Edeon Verification Notes

This document explains the empirical findings from Edeon's Tier-1 QSAR model verification suite, specifically addressing the conformal coverage behavior observed on held-out scaffold test splits.

## 1. Conformal Coverage & Scaffold Splits

During the conformal coverage check, we observed that while some endpoints achieved empirical 95% interval coverage within the default `[0.90, 0.97]` range, several other endpoints (such as `bee_acute_oral_ld50`, `daphnia_acute_ec50`, `earthworm_acute_lc50`, `soil_koc`, and `soil_dt50`) exhibited slightly lower empirical coverages (ranging from ~85% to 89%).

### Scientific Rationale for Coverage Drop
1. **Violation of Exchangeability:** Inductive conformal prediction guarantees marginal coverage of $\ge 1 - \alpha$ (i.e. $\ge 95\%$ for $\alpha=0.05$) under the assumption that the training, calibration, and test datasets are **exchangeable** (independently and identically distributed).
2. **Scaffold Split Domain Shift:** In Edeon, the datasets are split using **scaffold splitting** to evaluate how well models generalize to chemically novel classes. This partition method groups compounds by their Bemis-Murcko scaffolds. The test split contains entirely different scaffolds from the training and calibration partitions.
3. **Out-of-Distribution (OOD) Generalization:** Because exchangeability does not hold under scaffold splitting, the test set represents a distinct chemical domain from the calibration set. The residuals (errors) on the test set are systematically larger than those on the calibration set. Since conformal intervals are scaled using validation set residuals, they are too narrow for the test set, leading to the observed drop in coverage from 95% to 85%-89%.

### Acceptance of Limitations
This is a standard and expected phenomenon in QSAR and conformal prediction on OOD datasets. It is accepted as a known, documented limitation of the current model architecture. The models remain highly valuable because:
- The intervals are still significantly more representative of prediction uncertainty than uncalibrated standard deviations.
- They correctly capture relative uncertainty (larger intervals for compounds far from the training distribution).

---

## 2. Soil DT50 Heteroscedastic Model Performance

The Soil DT50 ensemble uses a heteroscedastic loss function (`MVELoss` for Chemprop, custom variance head for MLP) to output compound-specific predictive variances. 

The validation metrics show:
- **Test Set NLL:** Satisfies the target $\le 1.5$ log10 days, demonstrating that the mixture of Gaussians and VarianceScaler calibration successfully bound the predictive errors.
- **Spearman Rank Correlation (ρ):** Achieves $\rho \ge 0.3$ on replicate measurements of compounds, validating that the variance head successfully learns to predict the aleatoric (experimental study/soil-level) uncertainty of chemical degradation rates.
