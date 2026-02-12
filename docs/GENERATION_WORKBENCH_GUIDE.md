# De Novo Design Workbench User Guide

Welcome to the **Edeon De Novo Design Workbench**. This guide outlines how to use the generative design environment to build, screen, and rank drug/pesticide candidates using closed-loop chemical evolution.

---

## 1. Overview of Design Modes

The Generation Workbench provides three distinct operational modes to guide your pesticide or crop protection design workflows:

### A. CReM-dock (Closed-loop Evolutionary De Novo Design)
This is the main closed-loop pipeline of Edeon. It performs generative evolution of molecules using the following cyclic protocol:
1. **Mutation**: Generates structurally diverse analogs from a parent seed molecule using the CReM mutator core.
2. **Docking**: Automatically runs virtual screening (using Vina) to assess binding affinity of all mutated analogs against the selected receptor.
3. **Safety Profile (QSAR)**: Predicts Tier-1 properties, pesticide likeness, selective toxicity, resistance risks, and environmental persistency.
4. **MPO Selection**: Calculates a composite multi-parameter optimization (MPO) score. The highest-ranking analogs are selected to seed the next generation.

### B. CReM Mutation (Simple Diversification)
A fast, ligand-only diversification tool. It applies local modifications (substitutions, insertions, deletions) around a seed molecule using a fragment database, but skips the expensive docking and QSAR steps. Excellent for standard bioisostere generation or scaffold hopping.

### C. EasyDock Batch (Parallel Virtual Screening)
Allows you to paste a list of custom SMILES (comma- or newline-separated) and dock them in parallel against the chosen target protein receptor. Useful for screening pre-curated collections or validation sets.

---

## 2. Receptor Preset Pockets

The environment includes pre-configured grid box parameters and reference files for key crop protection target receptors:

*   **ALS (Acetolactate Synthase)**: Target pocket for sulfonylurea and triazolopyrimidine herbicides (PDB: 1YBH).
*   **EPSPS (Shikimate Synthase)**: Essential for shikimate pathway disruption fits (glyphosate target; PDB: 2AAY).
*   **HPPD (Dioxygenase)**: Bleaching target pocket for triketones like mesotrione (PDB: 1TFZ).
*   **GS (Glutamine Synthetase)**: Glufosinate target pocket evaluating nitrogen assimilation disruption (PDB: 2O2A).
*   **ACCase (Acetyl-CoA Carboxylase)**: Lipid synthesis enzyme, carboxyltransferase domain fits for "fops" and "dims" (PDB: 1UYR).
*   **PPO (Protoporphyrinogen Oxidase)**: Diphenyl ether lipid peroxidation target (PDB: 1SEZ).
*   **PSII (Photosystem II)**: Core photosynthetic electron transport complex for triazines and ureas (PDB: 1FEV).
*   **SDH (Succinate Dehydrogenase)**: Mitochondrial Complex II respiratory target for carboxamide fungicides (PDB: 2FBW).

---

## 3. Multi-Parameter Optimization (MPO) Weights

Edeon uses an MPO scoring system to balance target binding affinity (docking) with toxicity and environmental safety. You can adjust the weights (0–100%) for each category:

1. **Pesticide Likeness (Tice Rules)**: Assesses compliance with agricultural physicochemical boundaries (LogP, MW, rotatable bonds, hydrogen bond donors/acceptors).
2. **Cross-Species Selectivity**: Scores the safety margin between the pest target and non-target organisms (e.g. honeybee *Apis mellifera* or fish).
3. **Resistance Evasion**: Evaluates mutation tolerance to ensure analogs remain effective against known target-site mutations.
4. **Toxicity Profile**: Penalizes compounds with predicted acute oral LD50 toxicity, skin sensitization, or mutagenicity.
5. **Environmental Fate**: Favors compounds with lower soil persistence ($DT_{50}$) and lower groundwater leaching potential (GUS index).

---

## 4. Step-by-Step Design Workflow

### Step 1: Set Seed Parent Molecule
Enter the parent SMILES. You can also click **"Pull active compound"** to automatically pull the compound currently active in the Edeon Inspector view.

### Step 2: Configure Parameters
*   **For CReM-dock**:
    *   *Generations (Iterations)*: Number of evolutionary cycles (default: 3).
    *   *Pool Size / Gen*: Number of mutants simulated per cycle (default: 20).
    *   *Seeds Kept / Gen*: Number of elite survivors that seed the next generation (default: 5).
*   **For CReM Mutation**:
    *   *Mutation Radius*: Size of the environment around the mutated atom (1 to 5).
    *   *Max Mutants*: Upper limit on generated outputs.
    *   *Heavy Atom Size limits*: Size boundaries of replacement fragments.

### Step 3: Run the Job
Click **Execute Design Job**. A progress bar will stream progress from the backend.

### Step 4: Analyze Results & Library Integration
When completed, the results grid displays generated compounds sorted by their composite score. Clicking a row shows:
*   Side-by-side structures of the parent molecule and the mutated analog.
*   Docking Affinity delta.
*   MPO safety rating (out of 10).
*   Predicted toxicity endpoints.

If you find a promising analog, click **"Add to Project Library"** to save it to your project workspace.

---

## 5. Licensing Note on CReM-pharm

> [!WARNING]
> Due to GPLv3 copyleft licensing restrictions, the pharmacophore-guided CReM mutator (`CReM-pharm`) is excluded from Edeon's pre-compiled bundle. To enable this feature, configure a local Python environment containing the `crem-pharm` package and link its path in Settings.
