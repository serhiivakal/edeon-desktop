# Phase 0 Notes — Legacy Predictors Inventory

This document inventories the existing legacy LogP-based predictors within Edeon's original `edeon_engine` codebase. These predictors are slated for migration behind the new `ModelBackend` interface as Tier-2 (T2) baseline backends.

---

## 1. Inventory of Legacy Predictors

The following list identifies the 12 endpoints specified in Phase 0 Section 0, detailing their legacy source location, served endpoint, inputs, and output shapes.

### 1. Honeybee Acute Oral Toxicity
- **Source File**: [python/edeon_engine/toxicity.py](file:///\\wsl.localhost\Ubuntu\home\svakal\Projects\Edeon\python\edeon_engine\toxicity.py) (supplemented by [scoring.py](file:///\\wsl.localhost\Ubuntu\home\svakal\Projects\Edeon\python\edeon_engine\scoring.py))
- **Function Name**: `_predict_bee_toxicity(props)` / `environmental_safety` calculation
- **Endpoint served**: `bee_acute_oral_ld50` and `bee_acute_contact_ld50`
- **Inputs**: Computed molecular properties (`logp`, `mol_weight`, `hbd`, `tpsa`) calculated from SMILES.
- **Output**: 
  - `toxicity.py`: A `dict` containing risk level (`"High" | "Med" | "Low"`), risk score (`0.0–10.0`), qualitative detail, and regulatory threshold.
  - `scoring.py`: Raw numeric contact LD50 value calculated as `10 ** (2.5 - 0.5 * logp)`.

### 2. Fish Acute Toxicity
- **Source File**: [python/edeon_engine/toxicity.py](file:///\\wsl.localhost\Ubuntu\home\svakal\Projects\Edeon\python\edeon_engine\toxicity.py)
- **Function Name**: `_predict_fish_toxicity(props)`
- **Endpoint served**: `fish_acute_lc50`
- **Inputs**: Computed molecular properties (`logp`, `mol_weight`, `tpsa`) calculated from SMILES.
- **Output**: A `dict` containing risk level (`"High" | "Med" | "Low"`), risk score (`0.0–10.0`), qualitative detail, and regulatory threshold.

### 3. Daphnia Acute Toxicity
- **Source File**: [python/edeon_engine/selectivity.py](file:///\\wsl.localhost\Ubuntu\home\svakal\Projects\Edeon\python\edeon_engine\selectivity.py)
- **Function Name**: `_estimate_daphnia_selectivity(props)`
- **Endpoint served**: `daphnia_acute_ec50`
- **Inputs**: Computed molecular properties (`logp`, `tpsa`) calculated from SMILES.
- **Output**: A `dict` containing organism, selectivity index (`0.5–50.0`), risk level (`"safe" | "moderate" | "danger"`), and detail.

### 4. Earthworm Acute Toxicity
- **Source File**: [python/edeon_engine/selectivity.py](file:///\\wsl.localhost\Ubuntu\home\svakal\Projects\Edeon\python\edeon_engine\selectivity.py)
- **Function Name**: `_estimate_earthworm_selectivity(props)`
- **Endpoint served**: `earthworm_acute_lc50`
- **Inputs**: Computed molecular properties (`logp`, `mol_weight`, `tpsa`) calculated from SMILES.
- **Output**: A `dict` containing organism, selectivity index (`0.5–50.0`), risk level (`"safe" | "moderate" | "danger"`), and detail.

### 5. Bird Acute Oral Toxicity (Mallard)
- **Source File**: [python/edeon_engine/toxicity.py](file:///\\wsl.localhost\Ubuntu\home\svakal\Projects\Edeon\python\edeon_engine\toxicity.py)
- **Function Name**: `_predict_bird_toxicity(props)`
- **Endpoint served**: `bird_acute_oral_ld50`
- **Inputs**: Computed molecular properties (`logp`, `mol_weight`, `hba`) calculated from SMILES.
- **Output**: A `dict` containing risk level (`"High" | "Med" | "Low"`), risk score (`0.0–10.0`), qualitative detail, and regulatory threshold.

### 6. Mammal Acute Oral Toxicity (Rat)
- **Source File**: [python/edeon_engine/toxicity.py](file:///\\wsl.localhost\Ubuntu\home\svakal\Projects\Edeon\python\edeon_engine\toxicity.py)
- **Function Name**: `_predict_mammal_toxicity(props)`
- **Endpoint served**: `rat_acute_oral_ld50`
- **Inputs**: Computed molecular properties (`logp`, `mol_weight`, `tpsa`, `hbd`, `hba`, `rotatable_bonds`) calculated from SMILES.
- **Output**: A `dict` containing risk level (`"High" | "Med" | "Low"`), risk score (`0.0–10.0`), qualitative detail, and regulatory threshold.

### 7. Skin Sensitization
- **Source File**: *None* (No legacy implementation exists under the original `python/edeon_engine` codebase).
- **Function Name**: *None*
- **Endpoint served**: `skin_sensitization`
- **Inputs**: SMILES string.
- **Output**: A baseline category classification (`"Non-sensitizer" | "Weak" | "Strong"`) generated via standard LogP/MW heuristic checks in the migrated T2 wrapper.

### 8. Eye Irritation
- **Source File**: *None* (No legacy implementation exists under the original `python/edeon_engine` codebase).
- **Function Name**: *None*
- **Endpoint served**: `eye_irritation`
- **Inputs**: SMILES string.
- **Output**: A baseline category classification (`"Non-irritant" | "Irritant" | "Severe Irritant"`) generated via standard LogP/polar-surface-area heuristic checks in the migrated T2 wrapper.

### 9. Soil Organic Carbon Partition Coefficient (Koc)
- **Source File**: [python/edeon_engine/scoring.py](file:///\\wsl.localhost\Ubuntu\home\svakal\Projects\Edeon\python\edeon_engine\scoring.py) (within `environmental_safety` evaluation block)
- **Function Name**: Inlined under `compute_mpo_score`
- **Endpoint served**: `soil_koc`
- **Inputs**: Computed molecular properties (`logp`) calculated from SMILES.
- **Output**: Log Koc value computed as `max(0.0, min(6.0, 0.47 * logp + 1.09))`.

### 10. Soil Degradation Half-Life (DT50)
- **Source File**: [python/edeon_engine/scoring.py](file:///\\wsl.localhost\Ubuntu\home\svakal\Projects\Edeon\python\edeon_engine\scoring.py) (within `environmental_safety` evaluation block)
- **Function Name**: Inlined under `compute_mpo_score`
- **Endpoint served**: `soil_dt50`
- **Inputs**: Computed molecular properties (`logp`, `mol_weight`, `tpsa`) calculated from SMILES.
- **Output**: Numeric soil degradation half-life (days) capped at `[2.0, 365.0]` using `20.0 * (1.0 + 0.3 * max(0.0, logp)) * (1.0 + 0.2 * max(0.0, (mw - 200.0) / 100.0)) * math.exp(-tpsa / 150.0)`.

### 11. Gustafson Groundwater Ubiquity Score (GUS Index)
- **Source File**: [python/edeon_engine/scoring.py](file:///\\wsl.localhost\Ubuntu\home\svakal\Projects\Edeon\python\edeon_engine\scoring.py) (within `environmental_safety` evaluation block)
- **Function Name**: Inlined under `compute_mpo_score`
- **Endpoint served**: `gus_index`
- **Inputs**: Computed molecular properties (`logp`, `mol_weight`, `tpsa`) calculated from SMILES.
- **Output**: Leaching risk score computed as `math.log10(dt50) * (4.0 - log_koc) if log_koc < 4.0 else 0.0`.

### 12. Photostability
- **Source File**: *None* (No legacy implementation exists under the original `python/edeon_engine` codebase).
- **Function Name**: *None*
- **Endpoint served**: `photostability_class`
- **Inputs**: SMILES string.
- **Output**: A qualitative category classification (`"Stable" | "Unstable"`) generated via standard structural complexity (rotatable bonds/conjugated systems proxy) checks in the migrated T2 wrapper.

---

## 2. Manual Smoke Test Checklist for UI Integration

This checklist outlines the manual verification procedures to ensure end-to-end correctness of the QSAR models preference system, pipeline deployment, and Inspector UI displays:

- [x] **Open Inspector with a compound**: 
  - Mount any valid target compound from the library or search canvas.
- [x] **Verify each predictor cell shows tier badge**:
  - The inlined tier badge (`T1`/`T2`/`T3`/`T4`) is visible adjacent to or within each value block.
- [x] **Verify AD warning displays**:
  - An applicability domain status badge is present (e.g. renders `AD unknown` or grey status warning indicator on legacy LogP-based T2 backends).
- [x] **Click a value → `ModelCardViewer` opens**:
  - Clicking any active prediction display launches the diagnostic dialog detailing the model description, training dataset constraints, applicability metrics, and failure modes.
- [x] **Open Settings → Model Preferences shows endpoints**:
  - The model preferences tab lists the canonical parameters with color-coded tier selector dropdowns.
- [x] **Set a preference → re-run prediction → preference respected**:
  - Pinning a custom tier for an endpoint instantly writes preference records to the local SQLite database and updates the active prediction's tier when evaluated.
- [x] **Open QSAR Studio → train a model → click "Deploy to Pipeline" → predict in Inspector → see T4 badge**:
  - Training a regression model, deploying it to a target endpoint, and running calculations displays the custom prediction with an amber/purple `T4` Custom badge.
