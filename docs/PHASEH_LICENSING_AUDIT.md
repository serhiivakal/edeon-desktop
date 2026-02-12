# Phase H Licensing Audit — Feature H2: Matched Molecular Pairs & Free-Wilson SAR

## Executive Summary
Feature H2 introduces local library Matched Molecular Pair (MMP) fragmentation indexing, selectivity window-widening transform ranking, and Free-Wilson additive regression. All dependencies and algorithms have been audited for intellectual property and licensing safety.

| Package / Algorithm | License | Commercial Redistribution | Copyleft / GPL Risks | Compliance Posture |
|---------------------|---------|---------------------------|----------------------|--------------------|
| **mmpdb** | BSD-3-Clause | Allowed | None | Approved for embedded sidecar distribution |
| **RDKit `rdMMPA`** | BSD-3-Clause | Allowed | None | Native dependency |
| **scikit-learn** (Ridge/OLS) | BSD-3-Clause | Allowed | None | Native dependency |

## License Audit Details

### 1. `mmpdb` (Matched Molecular Pair Database Engine)
- **License:** BSD 3-Clause Clear License (University of Vienna / D3Pharm).
- **Redistribution Terms:** Commercial and proprietary distribution permitted provided copyright notice and disclaimer are retained.
- **Verification:** No copyleft viral triggers exist. Safe for bundling.

### 2. Free-Wilson SAR Additive Model
- **Algorithm:** $y_i = \mu + \sum_{j} c_j x_{ij}$ (Free & Wilson, 1964).
- **Implementation:** Custom scikit-learn / NumPy matrix decomposition solver implemented directly within Edeon's engine.
