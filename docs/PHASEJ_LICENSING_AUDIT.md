# Phase J Licensing Audit — Feature J7: Chemical-Space Cartography (TMAP & Faerun)

## Executive Summary
Feature J7 introduces high-capacity chemical space layout visualization using MinHash LSH indexing and Minimum Spanning Trees (MST). All software packages and algorithms have been audited for IP safety.

| Package | License | Commercial Redistribution | Copyleft / GPL Risks | Compliance Posture |
|---------|---------|---------------------------|----------------------|--------------------|
| **tmap** | BSD 3-Clause | Allowed | None | Approved |
| **faerun** | MIT | Allowed | None | Approved |
| **scipy / networkx** (MST fallback) | BSD 3-Clause / 3-Clause | Allowed | None | Native fallback |

## License Audit Details

### 1. `tmap` (LSH Forest MST Engine)
- **License:** BSD 3-Clause License (Reymond Group, University of Bern).
- **Redistribution Terms:** Full commercial redistribution permitted with standard attribution notice.
- **Verification:** No copyleft viral clauses.

### 2. `faerun` (Web visualizer)
- **License:** MIT License.
- **Redistribution Terms:** Permissive open source.
