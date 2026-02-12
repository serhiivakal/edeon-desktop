# 3D Molecular Docking Protocol

Edeon integrates actual 3D molecular docking via AutoDock Vina and optional GNINA rescoring.

## Pipeline
1. **Receptor Prep**: Converts PDB to PDBQT, adding polar hydrogens and Gasteiger charges.
2. **Ligand Prep**: Generates 3D coordinates using ETKDGv3 and minimizes via MMFF94. Converts to PDBQT with rotatable torsions.
3. **Vina Execution**: Runs AutoDock Vina subprocess with specified binding box and exhaustiveness.
4. **Pose Parsing**: Extracts individual docked poses and scores.

## Score Interpretation
- Score ≤ -10 kcal/mol: Strong binding (interpret cautiously — empirical estimate)
- -10 to -8: Moderate binding
- -8 to -6: Weak binding
- ≥ -6: Unfavorable
