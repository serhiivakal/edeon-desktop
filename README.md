# Edeon Desktop — Agrochemical Lead Optimization & Scientific Intelligence Platform

[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-Non--Commercial-blue.svg)](LICENSE)
[![Platform: Tauri v2](https://img.shields.io/badge/Platform-Tauri_v2_|_React_19-green.svg)](https://tauri.app)
[![Engine: Python 3.11](https://img.shields.io/badge/Engine-Python_3.11_|_RDKit-gold.svg)](https://www.rdkit.org)
[![Tests: 47 Passed](https://img.shields.io/badge/Tests-47%20Passed-brightgreen.svg)](tests/)

**Edeon Desktop** is a local-first, full-stack agrochemical lead optimization platform designed for discovery teams and research institutions. Edeon unifies modern machine learning QSAR modeling, cross-species eco-toxicology selectivity analysis, environmental fate simulation, metabolite rescoring, structure-based docking, retrosynthesis feasibility gating, matched molecular pair SAR, 2D/3D chemical-space cartography, 3D shape/electrostatic screening, and Bayesian-optimization active learning into a single desktop experience.

---

## 🔬 Core Capabilities & Architecture Overview

```
                                 ┌────────────────────────────────────────────────────────┐
                                 │                 React 19 + TypeScript UI               │
                                 │   NGL 3D • TMAP Canvas • Recharts • Zustand Stores     │
                                 └──────────────────────────┬─────────────────────────────┘
                                                            │ Tauri IPC
                                 ┌──────────────────────────┴─────────────────────────────┐
                                 │                 Tauri v2 (Rust Backend)                │
                                 │       SQLite (v24 WAL) • PDF Generator • Sidecar       │
                                 └──────────────────────────┬─────────────────────────────┘
                                                            │ Stdin/Stdout JSON-RPC
                                 ┌──────────────────────────┴─────────────────────────────┐
                                 │               Python Scientific Engine                 │
                                 │  RDKit • scikit-learn • AutoDock Vina • Dimorphite-DL  │
                                 │  AiZynthFinder • mmpdb • TMAP • espsim • BoTorch GP    │
                                 └────────────────────────────────────────────────────────┘
```

### 1. Agrochemical Library Curation & Prep
- **Herbicide-Likeness (Tice Rules)**: Automated filtering enforcing Molecular Weight, LogP, HBD, HBA, rotatable bond, and TPSA thresholds.
- **Bemis-Murcko Scaffold Diversity**: Round-robin diversity sampling across canonical Murcko scaffolds to maximize structural variation.
- **GIL-Releasing Parallel Processing**: Multi-threaded `joblib.Parallel` engine executing standardization, property calculation, PAINS filtering, and 3D conformer generation across all available CPU cores.

### 2. Eco-Toxicology QSAR Studio & Selectivity
- **Multi-Species Risk Profiling**: Simultaneous prediction across crop, pest, pollinator (bee oral/contact), aquatic (fish, daphnia, algae), avian, and mammalian toxicity endpoints.
- **Interactive Modeling Studio**: Automated dataset curation, feature block featurization (Morgan, MACCS, Avalon, 2D descriptors, custom), Optuna hyperparameter optimization, applicability domain (AD) leverage bounds, uncertainty quantification (UQ), and SHAP atom contribution maps.

### 3. Environmental Fate & Metabolite Liability Rescoring
- **Environmental Fate Endpoints**: Conformal interval estimations for Soil $DT_{50}$, $K_{oc}$, BCF, $\log K_{ow}$, Henry's Law, and GUS leaching index ($GUS = \log_{10}(DT_{50}) \times (4.0 - \log_{10}(K_{oc}))$).
- **SyGMa Pathway DAG & Soil Microbial Metabolism**: Degradation pathway tree generation with custom SMIRKS rules (soil microbial biotransformation, aquatic photolysis, soil hydrolysis), cumulative probabilities, automated metabolite rescoring, and liability flags (`⚠️ LIABILITY (HIGH RISK)`).

### 4. Structure-Based 3D Docking & Visualization
- **AutoDock Vina / GNINA Integration**: Automated receptor preparation, HET parsing, binding pocket detection, centroid grid targeting, multi-conformer docking, pose clustering, and 2D interaction diagrams embedded in an interactive WebGL NGL 3D viewport.

### 5. Retrosynthesis Feasibility & Reaction Enumeration
- **Synthesis Route Search & Gating**: Retrosynthesis tree evaluation using AiZynthFinder, RAscore, and **BR-SAScore** (Bicubic Rational Synthetic Accessibility Score) paired with commercial stock reagent matching.
- **Combinatorial Reaction Enumeration**: SMARTS synthetic reaction templates (Amide coupling, Suzuki-Miyaura, $S_NAr$ substitution, Reductive amination, Esterification, Sulfonamides) for core-R group enumeration.

### 6. Matched Molecular Pairs & Free-Wilson SAR
- **`mmpdb` + RDKit MMP Cleavage**: Automated single-bond fragmentation into core-substituent pairs.
- **Selectivity Window-Widening Delta**: Transformation ranking by selectivity improvement ($\Delta \text{selectivity} = \Delta \text{target} - \Delta \text{off-target}$).
- **Free-Wilson Additive Regression**: Decomposes structural series into substituent contribution coefficients ($c_j$) and intercept ($\mu$) via Ridge regression.

### 7. Chemical-Space Cartography
- **TMAP LSH Minimum Spanning Tree**: High-performance MinHash LSH Forest indexing and Minimum Spanning Tree (MST) 2D coordinate calculation scaling to 100k+ compounds.
- **Interactive TmapCanvas Visualizer**: Pan/zoom HTML5 Canvas tree view with MST branch rendering, property gradient node coloring, and 2D structure depiction tooltips.

### 8. 3D Shape & Electrostatic Similarity Screening
- **Open3DAlign Conformer Alignment**: ETKDGv3 conformer ensemble generation, MMFF energy minimization, and 3D shape overlap scoring ($S_{\text{shape}}$).
- **`espsim` Electrostatic Field Scoring**: Partial charge electrostatic potential field similarity ($S_{\text{electrostatic}}$) with Gasteiger charge distance fallback.
- **ROCS-Style ComboScore Ranking**: Combined 3D similarity ranking ($\text{ComboScore} = S_{\text{shape}} + S_{\text{electrostatic}}$, range $0.0 \rightarrow 2.0$).

### 9. Bayesian-Optimization Active-Learning Loop
- **Gaussian Process Surrogate Modeling**: BoTorch / GPyTorch GP regression surrogate model fitting over Morgan fingerprints yielding predicted mean $\mu(x)$ and variance $\sigma^2(x)$.
- **Acquisition Functions**: Expected Improvement (EI), Upper Confidence Bound (UCB), and Thompson Sampling (TS) for prioritizing optimal candidate batches with $\pm 2\sigma$ error bars.

---

## 🛠 Tech Stack

| Component | Stack |
|-----------|-------|
| **Frontend UI** | React 19, TypeScript, Zustand, NGL WebGL 3D, Recharts, TMAP Canvas |
| **Desktop Shell** | Tauri v2 (Rust 2021), `rusqlite` SQLite (WAL mode, 24 migrations), `printpdf` |
| **Python Sidecar** | Python 3.10+, RDKit, scikit-learn, XGBoost, LightGBM, Optuna, Chemprop |
| **Specialized Packages** | `mmpdb`, `tmap`, `faerun`, `espsim`, `botorch`, `gpytorch`, `sygma`, `dimorphite_dl`, `pkasolver`, `aizynthfinder`, `rascore` |

---

## 🚀 Quickstart & Setup

### Prerequisites
- **Node.js**: v18+
- **Rust**: 1.75+ (`cargo`)
- **Conda / Mamba**: Python 3.10 or 3.11 environment

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/serhiivakal/edeon-desktop.git
   cd edeon-desktop
   ```

2. **Install Frontend Dependencies**:
   ```bash
   npm install
   ```

3. **Set up Python Scientific Environment**:
   ```bash
   cd python
   pip install -e .
   cd ..
   ```

4. **Run Desktop Application in Development Mode**:
   ```bash
   npm run tauri dev
   ```

---

## 🧪 Verification & Test Suite

The platform includes an automated Python verification test suite covering speciation, mobility, retrosynthesis, reaction enumeration, environmental biotransformation, SAR MMP, cartography, 3D shape screening, active learning, and decision journals:

```bash
cd python
PYTHONPATH=. pytest tests/
```

**Output:** `47 passed in 15.86s`

To verify the Rust backend compilation:
```bash
cd src-tauri
cargo check --no-default-features
```

---

## 📄 License & Attribution

This project is licensed under the **Non-Commercial Public License** ([LICENSE](LICENSE)) incorporating terms from **Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)**.

- **Non-Commercial Use**: You are free to use, modify, study, and distribute this software for academic, research, personal, and educational purposes.
- **Commercial Exclusion**: Commercial monetization, integration into proprietary commercial products, or paid consulting using this software requires an explicit commercial license.

For commercial licensing requests, scientific inquiries, or collaboration proposals, please reach out to the project maintainers.
