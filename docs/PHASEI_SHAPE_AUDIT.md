# Phase I Licensing Audit — Feature I4: 3D Shape & Electrostatic Similarity Screening

## Executive Summary
Feature I4 introduces ROCS-style 3D shape alignment and partial charge electrostatic similarity scoring ($S_{\text{shape}} + S_{\text{electrostatic}}$). All software libraries have been audited for IP safety and commercial redistribution compliance.

| Package / Component | License | Commercial Redistribution | Copyleft / GPL Risks | Compliance Posture |
|---------------------|---------|---------------------------|----------------------|--------------------|
| **espsim** | MIT | Allowed | None | Approved |
| **RDKit `rdMolAlign` (Open3DAlign)** | BSD 3-Clause | Allowed | None | Native dependency |
| **RDKit `AllChem` ETKDGv3** | BSD 3-Clause | Allowed | None | Native dependency |

## License Audit Details

### 1. `espsim` (Electrostatic Field Calculator)
- **License:** MIT License (University of Oxford / Oxford Drug Discovery).
- **Redistribution Terms:** Full commercial and proprietary distribution permitted.
- **Verification:** No copyleft viral clauses.

### 2. RDKit Open3DAlign (`O3A`)
- **License:** BSD 3-Clause License.
- **Algorithm:** Open3DAlign shape alignment (Tosco, Balle & Shkurti, 2011).
