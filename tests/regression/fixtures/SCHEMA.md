# Regression Test Fixtures Schema

This document specifies the schema and format of the CSV regression testing fixtures located under `tests/regression/fixtures/`.

## Purpose
The regression testing suite uses these fixtures to detect **drift** in ML model predictions and chemical calculations. 

> [!NOTE]
> The "expected" values defined in these CSV files are **not ground truth** historical database entries. Instead, they represent the **frozen outputs of the current model implementation**. 
> The purpose of these tests is to serve as a continuous validation harness, raising warning alerts if future database schema, descriptor featurizations, or ML estimator updates cause predicted values to drift away from these established Baselines.

---

## File Format

Fixture files MUST be standard CSV files with the following header:

```csv
smiles,endpoint,expected_value,expected_value_lower,expected_value_upper,notes
```

### Column Definitions

| Column | Type | Required | Description |
|---|---|---|---|
| `smiles` | String | **Yes** | Valid canonical SMILES representation of the target test compound. |
| `endpoint` | String | **Yes** | One of the 16 canonical `Endpoint` identifier strings (e.g. `bee_acute_oral_ld50`). |
| `expected_value` | Float | **Yes** | The expected primary numeric prediction value frozen from the baseline run. |
| `expected_value_lower` | Float | No | The expected lower bound value of the 95% Conformal Confidence Interval. |
| `expected_value_upper` | Float | No | The expected upper bound value of the 95% Conformal Confidence Interval. |
| `notes` | String | No | Explanatory context detailing the baseline tier, algorithm, or featurization (quoted). |

---

## Example Row

```csv
smiles,endpoint,expected_value,expected_value_lower,expected_value_upper,notes
CCO,bee_acute_oral_ld50,12.5,5.0,30.0,"Tier-2 LogP baseline"
```
