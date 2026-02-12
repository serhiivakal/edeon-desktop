# Edeon — EPA OPERA Tier-3 Developer Guide

This document describes the technical architecture and implementation details for integrating the EPA OPERA (Open Structure-activity/property Relationship App) command-line interface (CLI) as a Tier-3 external reference backend.

---

## Technical Architecture

The integration consists of:
1.  **`OperaTier3Backend`**: A python class extending `ModelBackend` that invokes the local OPERA CLI executable via `subprocess.run`.
2.  **SQLite Caching Layer**: A local SQLite database at `data/cache/opera_cache.db` to store and retrieve past predictions, ensuring second-call latency is $<100\text{ms}$.
3.  **Tauri IPC Bridge**: Proxy methods routing frontend requests for Tier-3 predictions to the Python `BackendRegistry`.
4.  **Comparison View Drawer**: A frontend user interface drawer triggered from `PredictionDisplay` that visually overlays Tier-1 conformal predictions with Tier-3 OPERA predictions.

---

## 1. Subprocess Execution of OPERA CLI

OPERA CLI is a compiled Matlab application. Execution is done by writing input SMILES to a temporary file and running the runner script:

```bash
./run_OPERA.sh <mcr_directory> -s <temp_smi_file> -o <temp_output_csv> -e <endpoint> -v 1
```

### Configurable Executable Path
The backend resolves the path of the OPERA executable in this order:
1.  **Environment Variable `OPERA_PATH`**: Explicit path to the script or binary (e.g., `/opt/OPERA/run_OPERA.sh`).
2.  **Standard System Binary Search**: Searches PATH and standard locations (e.g. `/usr/local/bin/OPERA_CL`, `/opt/OPERA/OPERA_CL`).

If the executable is not found, the backend enters **Dry-Run / Fallback Mode**.

---

## 2. Dry-Run / Fallback Mode

To prevent developer environments from failing tests or blocking compilation due to the missing 2.05 GB Matlab Compiler Runtime, the backend implements a transparent fallback:

*   **Behavior**: When no binary is detected, the backend returns a prediction constructed by taking the Tier-1 prediction value and applying a small deterministic shift (e.g. $+0.1$ log units).
*   **Indicator**: The `Prediction` object includes a warning `"OPERA binary not found — running in mock mode"`.
*   **Result**: All endpoints render realistically in the comparison drawer, and unit tests can run and verify code paths end-to-end without local dependencies.

---

## 3. Caching Database Schema

To prevent costly subprocess execution overhead, predictions are stored in a dedicated SQLite database located at `data/cache/opera_cache.db`:

```sql
CREATE TABLE IF NOT EXISTS opera_cache (
    smiles        TEXT NOT NULL,
    endpoint      TEXT NOT NULL,
    value_json    TEXT NOT NULL, -- Serialized PredictionValue
    ci_lower      REAL,
    ci_upper      REAL,
    ad_status     TEXT NOT NULL,
    ad_score      REAL,
    units         TEXT NOT NULL,
    model_id      TEXT NOT NULL,
    provenance    TEXT NOT NULL, -- Serialized JSON dict
    created_at    TEXT NOT NULL,
    PRIMARY KEY (smiles, endpoint)
);
```

---

## 4. UI Comparison Logic

The frontend comparison drawer displays the absolute discrepancy ($\Delta$) between Edeon Tier-1 and OPERA Tier-3 predictions:
*   **Significant Discrepancy Highlight**: Marked in orange/red if the difference exceeds a threshold (e.g. $>0.5$ log units for Koc/BCF/DT50).
*   **Domain Conflict Highlight**: Indicated if one model determines the compound is inside the applicability domain (IN) while the other classifies it as outside (OUT).
