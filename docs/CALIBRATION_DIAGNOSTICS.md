# Edeon — GUI Calibration Diagnostics Documentation

This document explains the technical implementation, mathematical formulas, and visual interpretations of the calibration diagnostics provided in the Edeon GUI. These diagnostics help computational chemists justify model confidence, identify out-of-domain predictions, and verify model reliability.

---

## 1. Regression Calibration Diagnostics

Regression models (e.g., $EC_{50}$, $LC_{50}$, $K_{oc}$ predictions) display three primary interactive charts:

### A. Parity Plot (Observed vs. Predicted)
The Parity Plot is a scatter plot comparing experimental observations (x-axis) to model predictions (y-axis) on a held-out test set.
- **Identity Line ($y = x$)**: Indicates a perfect prediction where predicted values match observed values exactly. Points closer to this diagonal indicate higher accuracy.
- **Conformal Uncertainty Bounds**: Hovering over any point displays the compound's SMILES, Observed/Predicted values, and its $95\%$ Conformal Prediction Interval (CI) bounds:
  $$\text{Interval} = [\hat{y} - q_{1-\alpha}, \hat{y} + q_{1-\alpha}]$$
  where $q_{1-\alpha}$ is the calibrated conformal error margin.
- **AD Highlighting**: Points are color-coded based on applicability domain status (Green = In Domain, Yellow = Borderline, Red = Out of Domain).

### B. Conformal Calibration Curve
This line chart evaluates the empirical coverage of the conformal prediction intervals.
- **Expected Confidence (x-axis)**: The specified target confidence level $C \in \{0.0, 0.1, \ldots, 1.0\}$.
- **Actual Coverage Rate (y-axis)**: The actual percentage of test compounds whose true observed values fall within the scaled prediction intervals.
- **Interpretation**: 
  - A perfectly calibrated model follows the diagonal identity line ($y = x$).
  - If the curve lies **above** the diagonal, the model's prediction intervals are conservative (larger than necessary, yielding higher-than-expected coverage).
  - If the curve lies **below** the diagonal, the intervals are overconfident (too narrow, yielding lower coverage than expected).

### C. Residuals Distribution
A histogram displaying the distribution of errors (residuals: $e_i = y_{i,\text{true}} - \hat{y}_{i,\text{pred}}$).
- **Interpretation**: A well-behaved, homoscedastic regression model should exhibit a symmetric, zero-centered normal distribution of residuals.
- **Statistics**: The panel displays the mean residual ($\mu$) and standard deviation ($\sigma$) to measure bias and variance.

---

## 2. Classification Calibration Diagnostics

Classification models (e.g., binary toxicity/hazard prediction) display three specialized visual panels:

### A. Reliability Diagram
The Reliability Diagram plots the mean predicted probability of positive class bins against the empirical positive fraction (true observations).
- **Interpretation**:
  - Perfect calibration matches the $y=x$ diagonal line. For example, of the compounds predicted to have an $80\%$ probability of toxicity, exactly $80\%$ should be toxic.
  - Deviations below the diagonal indicate **overconfidence** (predicted probabilities are higher than the true positive rate).
  - Deviations above the diagonal indicate **underconfidence** (predicted probabilities are lower than the true positive rate).

### B. ROC & PR Curves
- **ROC Curve (Receiver Operating Characteristic)**: Plots the False Positive Rate (FPR) vs. True Positive Rate (TPR) across all threshold levels, displaying the Area Under Curve (AUC-ROC).
- **PR Curve (Precision-Recall)**: Plots Recall (x-axis) vs. Precision (y-axis), displaying the Area Under Precision-Recall Curve (PR-AUC). This is particularly informative for imbalanced agrochemical datasets where safety triggers are rare.

### C. Confusion Matrix Heatmap
An interactive $2 \times 2$ grid summarizing classification outcomes:
- **True Negatives (TN) & True Positives (TP)**: Correct classifications.
- **False Positives (FP)**: False alarms (non-toxic predicted as toxic).
- **False Negatives (FN)**: Dangerous misses (toxic predicted as non-toxic).

---

## 3. Applicability Domain (AD) Diagnostics

Applicability Domain auditing guarantees that a model is only queried on chemical spaces similar to its training set.

### A. Tanimoto k-NN Distance Histogram
Edeon uses k-NN Tanimoto distance calculations based on Morgan fingerprints ($radius=2, bits=2048$):
- **Training Set (Slate Bars)**: The distribution of internal pairwise distances within the training set, reflecting the dataset's diversity.
- **Test Set (Green/Blue Bars)**: The distribution of distances from test compounds to the training set.

### B. Real-time Query Highlight
When inspecting a compound in the Inspector panel, a **dotted vertical reference line** overlays the AD histogram:
- **Green Indicator**: The query molecule's distance is within the core training set bounds (In Domain: $\text{dist} \le \text{Threshold}_{\text{in}}$).
- **Yellow Indicator**: The query molecule lies in the borderline/uncertain domain.
- **Red Indicator**: The query molecule is chemically distinct from the training set (Out of Domain), signaling high predictive uncertainty.

---

## 4. Chemical Class Performance Breakdown

Both regression and classification models feature a sortable grid analyzing performance metrics across specific chemical groups (e.g., *organophosphates, phenoxyacids, triazoles*):
- **Columns**: Chemical Family Name, Count ($N$), Error Metric (RMSE for regression, F1 / Balanced Accuracy for classification), and Applicability Domain (AD) Coverage.
- **Utility**: Allows chemists to identify specific chemical families where a model exhibits elevated error rates or poor coverage, guiding targeted model retraining.
