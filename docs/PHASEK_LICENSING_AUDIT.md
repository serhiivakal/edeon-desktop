# Phase K Licensing Audit — Feature K10: Bayesian-Optimization Active-Learning Loop

## Executive Summary
Feature K10 introduces Bayesian-Optimization active learning using Gaussian Process (GP) surrogate models and acquisition function optimization (Expected Improvement, UCB, Thompson Sampling). All dependencies have been audited for licensing compliance.

| Package / Library | License | Commercial Redistribution | Copyleft / GPL Risks | Compliance Posture |
|-------------------|---------|---------------------------|----------------------|--------------------|
| **botorch** | BSD 3-Clause | Allowed | None | Approved |
| **gpytorch** | MIT | Allowed | None | Approved |
| **scikit-learn** (GP fallback) | BSD 3-Clause | Allowed | None | Native dependency |

## License Audit Details

### 1. `botorch` (PyTorch Bayesian Optimization Framework)
- **License:** BSD 3-Clause License (Meta AI / PyTorch).
- **Redistribution Terms:** Full commercial redistribution permitted with standard copyright notice.

### 2. `gpytorch` (Gaussian Processes for PyTorch)
- **License:** MIT License (Cornell / Gardner et al.).
- **Redistribution Terms:** Permissive open source.
