# Edeon — EPA OPERA Endpoint Mapping

This document outlines the mappings, units, column headers, and conversion formulas for integrating EPA OPERA predictions as Tier-3 external references within Edeon.

| Edeon Endpoint | Edeon Units | OPERA Endpoint Name | OPERA Output Col | OPERA Raw Units | Conversion Formula to Edeon |
|---|---|---|---|---|---|
| `soil_koc` | L/kg | `Koc` | `Koc_pred` | $\log_{10}(\text{L/kg})$ | $\text{Koc} = 10^{\text{Koc\_pred}}$ |
| `bcf` | L/kg | `BCF` | `BCF_pred` | $\log_{10}(\text{L/kg})$ | $\text{BCF} = 10^{\text{BCF\_pred}}$ |
| `soil_dt50` | days | `BioDeg` | `BioDeg_pred` | $\log_{10}(\text{days})$ | $\text{DT50} = 10^{\text{BioDeg\_pred}}$ |
| `rat_acute_oral_ld50` | mg/kg bw | `CATMoS` | `CATMoS_LD50_pred` | $\log_{10}(\text{mg/kg})$ | $\text{LD50} = 10^{\text{CATMoS\_LD50\_pred}}$ |
| `logp` | dimensionless | `LogP` | `LogP_pred` | Log units | $\text{LogP} = \text{LogP\_pred}$ (identity) |
| `pka` | pH units | `pKa` | `pKa_a_pred`, `pKa_b_pred` | pH units | Acidic: $\text{pKa}_a$, Basic: $\text{pKa}_b$ |
| `solubility` | mg/L | `WS` | `WS_pred` | $\log_{10}(\text{mol/L})$ | $\text{WS} = 10^{\text{WS\_pred}} \times \text{MW} \times 1000$ |
| `henrys_law` | atm-m³/mol | `HL` | `HL_pred` | $\log_{10}(\text{atm-m³/mol})$ | $\text{HL} = 10^{\text{HL\_pred}}$ |

---

## Column Detail Mappings

When executing a prediction, the OPERA CLI returns a CSV file with specific column headers for each calculated endpoint. Edeon parses the following columns to populate the `Prediction` object:

### 1. Applicability Domain (AD)
*   **Column**: `<OPERA_Endpoint>_AD`
*   **Values**:
    *   `1`: Mapped to `ADStatus.IN` (In Domain)
    *   `0`: Mapped to `ADStatus.OUT` (Out of Domain)
    *   Otherwise: Mapped to `ADStatus.UNKNOWN`

### 2. Similarity Index (Sim Index)
*   **Column**: `<OPERA_Endpoint>_Sim_index`
*   **Value**: Mapped to `ad_score` in the Edeon prediction object (higher = more structurally similar to training set).

### 3. Confidence/Accuracy Index (Conf Index)
*   **Column**: `<OPERA_Endpoint>_Conf_index`
*   **Value**: Extracted and placed in the prediction `provenance` metadata dictionary as `confidence_index`.

---

## Chemistry Conversions

### Water Solubility (WS)
OPERA predicts water solubility in molar concentration ($\log_{10}(\text{mol/L})$). To convert this to the standard regulatory unit of $\text{mg/L}$ used in Edeon, the formula uses the compound's Molecular Weight ($\text{MW}$) calculated via RDKit:
$$\text{Solubility (mg/L)} = 10^{\text{WS\_pred}} \times \text{MW} \times 1000$$

### Acidic/Basic pKa
OPERA predicts the strongest acidic site (`pKa_a_pred`) and the strongest basic site (`pKa_b_pred`). Edeon returns a composite representation of both values under the `pka` endpoint value structure, indicating the strongest acidic and basic constants.
