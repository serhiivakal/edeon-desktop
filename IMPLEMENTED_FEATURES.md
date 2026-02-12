# Edeon Desktop — Implemented Agrochemical Lead Optimization Features

This document provides a comprehensive list of all the features implemented and upgraded in the **Edeon Desktop** codebase to support robust agrochemical lead library preparation, modeling, virtual screening, retrosynthesis gating, SAR analysis, chemical-space cartography, 3D shape alignment, and Bayesian-optimization active learning.

---

## 1. Agrochemical Library Curation & Prep

- **Bemis-Murcko Scaffold Diversity Clustering**:
  - Implemented Murcko scaffold round-robin diversity selections in `clustering.py`.
  - Groups molecules by their canonical scaffold and picks representative candidates iteratively across groups to maximize structural diversity. Acyclic structures are preserved as unique single-molecule scaffold keys.
- **Herbicide-Likeness (Tice Rules) Filter**:
  - Integrated Tice's agrochemical rules (checking thresholds for Molecular Weight, LogP, HBD, HBA, rotatable bonds, and TPSA) into the curation pipeline.
  - Added a sidebar run toggle to exclude compounds categorized as "Low" herbicide-likeness (2+ violations).
  - Displays a sortable **HERBICIDE-LIKE** rating column (High / Med / Low) in the results table using styled `RiskBadge` pills.

---

## 2. Multi-threaded Parallel Backend

- **CPU Core Auto-Detection**:
  - Automatically queries the host machine's total CPU core count on startup via a new `get_cpu_count` JSON-RPC endpoint.
  - Placed an interactive **CPU Workers** range slider in the configuration panel to let the user customize core allocation.
- **RDKit GIL-Releasing Multiprocessing**:
  - Refactored high-compute batch endpoints (Standardization, Properties calculation, PAINS structural alerts checks, and 3D conformer generation/protonation) to run concurrently via `joblib.Parallel` with a thread-based backend, utilizing multi-core speeds by releasing the RDKit C++ GIL.

---

## 3. Real-Time UI Progress Bar & Chunking

- **Sequential Step-Level Chunking**:
  - Divided large compound library files into smaller sequential batches on the frontend (Stage 1-3 in chunks of 100, Stage 5 in chunks of 20) to prevent Tauri IPC locking and browser frame freezes.
- **Dynamic Stage Progress**:
  - Updated stage cards to render independent progress tracks and indicators during execution, with live action labels (e.g. `Generating 3D conformers (40/500)...`).
- **Continuous Header Progress Bar**:
  - Added a progress bar in the main workflow header that computes a continuous, linear progress percentage combining fully completed stages with the exact percentage progress of the currently running stage.

---

## 4. Virtual Screening Integration & Library Transfers

- **Direct "Send to VS workflow" Route**:
  - Added a styled **🚀 Send to VS workflow** button in the Results section.
  - Clicking this captures the completed curation SDF/CSV/SMILES output, resets active run states, mounts the results into the shared `uploadedFile` store state, and instantly redirects the user to the Virtual Screening & Active Learning configuration panel.
- **Right-Click Export to De Novo Design**:
  - Context menu item (`🧪 Export to De Novo Design`) in `LibraryView` and `ResultsTable`.
  - Right-clicking any compound row captures its SMILES string, switches to the `De Novo Design` workbench (`generation`), and populates the compound as the active core/parent SMILES.
- **Active Learning Dataset Info Alert**:
  - Displays a highlighted notification card showing molecule counts and file names once the dataset is loaded in the Active Learning workflow.
  - Integrates a direct file upload zone when no dataset is present and validates input libraries before allowing runs to start.

---

## 5. Docking & 3D WebGL Visualization

- **Reference Ligand Pocket Targeting**:
  - Centered the AutoDock Vina grid boundaries on the co-crystallized reference ligand centroid coordinates (Stage 6) to lock the docking simulation onto the active site pocket.
  - Injected preset reference coordinate centroids for receptors whose co-crystallized ligands were pre-stripped.
- **Interactive Pose Navigation**:
  - Added Left & Right chevrons and Arrow keyboard listener controls to quickly swap through docked pose results.
  - Caps the 2D Interaction Map modal container width at `480px` to fit all screens.
  - Set RDKit SVG margin padding to `0.04` to maximize structure visibility.
- **Resizable Results Grid**:
  - Support vertical drag sizing on the Results Table and a full-screen maximize switch.

---

## 6. Environmental Fate (Parent Compound)

- **QSAR Fate Endpoints**:
  - Implemented predictions for Soil DT50, Koc, BCF, log Kow, and Henry's law constant, each returning conformal intervals (lower/upper bounds) and Applicability Domain (AD) status.
- **GUS Leaching Index**:
  - Computes the GUS score (`GUS = log10(DT50) * (4.0 - log10(Koc))`) and classifies compounds as leachers, transitional, or non-leachers.
- **PBT Scorecard**:
  - Implemented REACH Annex XIII PBT/vPvB scorecard (P, B, T flags and overall verdict) comparing endpoints against regulatory limits.
- **Fate Dashboard & Disclaimer**:
  - Created a dual-tab Fate View with property cards, UQ/AD badges, a dynamic threshold slider for the GUS index, and a regulatory screening disclaimer.

---

## 7. Transformation Products & Metabolism Expansion

- **Curated Agrochemical Degradation Rules**:
  - Curated SMIRKS rules (ester/amide hydrolysis, N-/O-dealkylation, sulfoxidation, ring hydroxylation, glucosylation, nitro reduction, dehalogenation, nitrile-to-amide) representing abiotic and metabolic pathways.
- **Soil Microbial & Environmental Rule Expansion**:
  - Added dedicated soil microbial biotransformation, aquatic photolysis, and soil hydrolysis rule sets with source origin tags (`sygma`, `soil_microbial`, `photolysis`, `hydrolysis`).
  - Implemented automatic `⚠️ LIABILITY (HIGH RISK)` flagging for persistent or toxic metabolites.
- **Pathway Generation & Closed-Loop Rescoring**:
  - Integrated SyGMa to build a transformation DAG (parent -> metabolites) with depth control (`max_depth = 2`) and cumulative probability.
  - Automatically rescores every metabolite through the full environmental fate and toxicity stack, flagging compounds with increased risk compared to the parent.
- **Interactive DAG & Inspector UI**:
  - Developed `PathwayTree.tsx` to render the transformation graph with Bezier curved lines, structural cards, source badges, and danger flags.
  - Added a comparative Metabolite Inspector table to highlight environmental or toxicity risk deltas side-by-side.

---

## 8. Speciation & Retrosynthesis Feasibility Gating

- **pH-Dependent Speciation**:
  - Integrated Dimorphite-DL and `pkasolver` to dynamically calculate pKa shifts and protonation states across physiological and environmental pH ranges (pH 4.0–9.0).
- **Retrosynthesis Route Prediction & Synthesizability Gating**:
  - Created `edeon_retro` package supporting synthesis route search via AiZynthFinder and RAscore.
  - Integrated **BR-SAScore** (Bicubic Rational Synthetic Accessibility Score) by default to score molecular complexity ($1.0 \rightarrow 10.0$).
  - Built `RouteTree.tsx` for visual tree exploration of multi-step reaction pathways and `FeasibilityBadge.tsx` for quick makeability tier assessment (`Feasible`, `Borderline`, `Difficult`).
- **Commercial Stock Reagent Matching**:
  - Cross-references synthetic precursors against building block inventories (`stock.py` / `stock_reagents` table).

---

## 9. Reaction-Based Combinatorial Enumeration

- **SMARTS Reaction Templates**:
  - Built predefined synthetic SMARTS reaction templates in `data/reactions.json` (Amide Coupling, Suzuki-Miyaura, SNAr Substitution, Reductive Amination, Esterification, Sulfonamides).
- **R-Group Library Combination**:
  - Implemented `reaction_enum.py` to enumerate core scaffolds against candidate reagent sets, applying synthetically accessible filters and Tice rules.
- **Combinatorial Enumeration UI**:
  - Developed `ReactionEnumPanel.tsx` integrated directly into `GenerationWorkbenchView.tsx` with mode switching between CReM mutation and Reaction Enumeration.

---

## 10. Matched Molecular Pairs & Free-Wilson SAR

- **`mmpdb` + RDKit MMP Engine**:
  - Built `edeon_sar` package using RDKit single-bond cleavage to extract canonical core-substituent pairs ($R_1 \rightarrow R_2$).
- **Selectivity Window-Widening Transform Ranking**:
  - Ranks R-group transformations by selectivity improvement delta ($\Delta \text{selectivity} = \Delta \text{target} - \Delta \text{off-target}$).
- **Free-Wilson Additive Regression**:
  - Fits additive linear regression models ($y_i = \mu + \sum c_j x_{ij}$) across structural series using Ridge regression, decomposing R-group contribution coefficients $c_j$ and series $R^2$ fit.
- **SAR UI Components**:
  - Built `MmpTransformTable.tsx` and `FreeWilsonPanel.tsx` to render ranked selectivity transformations and substituent contribution coefficients side-by-side.

---

## 11. Chemical-Space Cartography

- **TMAP Layout Engine**:
  - Built `edeon_cartography` package integrating TMAP (LSH Forest + Minimum Spanning Tree layout engine) to map high-dimensional Morgan fingerprints into 2D MST layout coordinates $(x_i, y_i)$ with scipy fallback.
- **Interactive TmapCanvas Visualizer**:
  - Developed `TmapCanvas.tsx` featuring smooth zoom/pan controls, MST branch line rendering, node property gradient coloring, and 2D molecule depiction hover tooltips.

---

## 12. 3D Shape & Electrostatic Similarity Screening

- **Open3DAlign Shape Overlap**:
  - Built `edeon_shape` package using ETKDGv3 conformer embedding, MMFF optimization, and RDKit Open3DAlign (`O3A`) to measure 3D shape similarity ($S_{\text{shape}} \in [0.0, 1.0]$).
- **`espsim` Electrostatic Field Calculation**:
  - Calculates partial charge electrostatic field potential similarity ($S_{\text{electrostatic}} \in [0.0, 1.0]$) using `espsim` with Gasteiger charge distance fallback.
- **ROCS-Style ComboScore Ranking**:
  - Ranks candidate libraries using combined ROCS-style similarity:
    $$\text{ComboScore} = S_{\text{shape}} + S_{\text{electrostatic}} \quad (\text{range } 0.0 \rightarrow 2.0)$$
- **3D Shape UI Panel**:
  - Built `ShapeScreeningPanel.tsx` for specifying active reference active ligands, triggering 3D alignments, and displaying ranked candidate tables with ComboScore badges.

---

## 13. Bayesian-Optimization Active-Learning Loop

- **Gaussian Process Surrogate Model**:
  - Built `edeon_active_learning` package fitting Gaussian Process (GP) surrogate regression models ($f(x) \sim \mathcal{GP}(\mu(x), \sigma^2(x))$) over Morgan fingerprint descriptors.
- **Acquisition Policy Engine**:
  - Implemented Expected Improvement (EI), Upper Confidence Bound (UCB), and Thompson Sampling (TS) acquisition functions to balance exploitation vs. exploration.
- **Active Learning Batch Recommendation**:
  - Prioritizes the optimal next batch of $N$ compounds for synthesis/screening, displaying predicted mean $\mu$, uncertainty standard deviation error bars ($\pm 2\sigma$), and acquisition score badges.
- **Active Learning UI Panel**:
  - Developed `ActiveLearningPanel.tsx` in `GenerationWorkbenchView.tsx` with policy selector, batch size controls, model $R^2$ metrics, and one-click compound library registration.
