# CReM + EasyDock Licensing Audit

This document reviews the licensing terms, dependencies, and commercial bundling eligibility for the generative chemistry and docking components introduced in Workstream F.

## Recommendation Summary

| Component | Repository | License | Key Dependencies | Bundling OK? | Action / Resolution |
|---|---|---|---|---|---|
| **CReM (core)** | [DrrDom/crem](https://github.com/DrrDom/crem) | BSD 3-Clause | RDKit (BSD-3) | **Yes** | Bundle and integrate as default mutation engine. |
| **CReM-dock** | [ci-lab-cz/crem-dock](https://github.com/ci-lab-cz/crem-dock) | BSD 3-Clause | RDKit, AutoDock Vina | **Yes** | Integrate as default closed-loop generation pipeline. |
| **EasyDock** | [ci-lab-cz/easydock](https://github.com/ci-lab-cz/easydock) | BSD 3-Clause | RDKit, Meeko (LGPL-2.1) | **Yes** | Integrate as high-throughput virtual screening orchestrator. |
| **CReM-pharm** | [ci-lab-cz/crem-pharm](https://github.com/ci-lab-cz/crem-pharm) | GPLv3 | RDKit | **No** | **Do not bundle.** Exclude from direct package distribution to avoid copyleft contamination. Support only via user-provided path. |
| **CReM-opt** | TBD | TBD | TBD | **No** | Exclude from design workflow until released and audited. |

---

## Detailed Component Analysis

### 1. CReM (core)
*   **License**: BSD 3-Clause. This is a highly permissive license that allows modification, commercial redistribution, and sublicensing in a closed-source product without copyleft obligations.
*   **Dependencies**: Requires `rdkit>=2017.09`. RDKit is licensed under the permissive BSD 3-Clause license.
*   **Bundling Verdict**: **GO**. Fully compliant.

### 2. CReM-dock
*   **License**: BSD 3-Clause.
*   **Dependencies**: Requires `crem` (BSD-3), `rdkit` (BSD-3), and docking runners. Fits perfectly into the Edeon architecture.
*   **Bundling Verdict**: **GO**. Fully compliant.

### 3. EasyDock
*   **License**: BSD 3-Clause.
*   **Dependencies**: Requires `rdkit`, `dask`, and `meeko` (LGPL-2.1). 
    *   *LGPL-2.1 compliance*: LGPL allows dynamic linking/use of Python libraries as dependencies in closed-source products without triggering copyleft, provided we do not modify Meeko itself (which we don't; it is just a standard library dependency in conda/pip).
    *   *Docking engines*: AutoDock Vina is Apache 2.0 (OK to bundle/invoke). Smina/Gnina are user-provided.
*   **Bundling Verdict**: **GO**. Fully compliant.

### 4. CReM-pharm
*   **License**: GPLv3. 
    *   *Copyleft Risk*: GPLv3 requires that any work containing or derived from GPLv3 code must be open-sourced under the GPLv3 license. Bundling GPLv3 Python code directly in a commercial closed-source desktop application like Edeon triggers this obligation, contaminating the codebase.
*   **Resolution**: **NO-GO** for bundling. We will exclude CReM-pharm from direct distribution. The UI tab for pharmacophore-guided mutations will be disabled by default, with a warning explaining that the user must locally install the GPLv3 dependency and specify its path in Settings to enable the feature.

---

## Verification & Compliance Action Plan
1.  Add `crem` and `easydock` to `poe` conda environment (BSD-3).
2.  Do not include `crem-pharm` in `requirements.txt` or `pyproject.toml`.
3.  Ensure `easydock` only accesses Meeko/RDKit via standard Python imports.
4.  Retain licensing notices for CReM, Meeko, and Vina in the product's attribution/credits folder.
