import numpy as np
from rdkit import Chem
from rdkit.Chem import Descriptors

# Define a diverse library of 100 unique, valid organic SMILES strings
compounds = [
    # Alkanols
    ("Methanol", "CO"),
    ("Ethanol", "CCO"),
    ("Propan-1-ol", "CCCO"),
    ("Butan-1-ol", "CCCCO"),
    ("Pentan-1-ol", "CCCCCO"),
    ("Hexan-1-ol", "CCCCCCCO"),
    ("Heptan-1-ol", "CCCCCCCO"),
    ("Ethylene glycol", "OCCO"),
    ("Propylene glycol", "CC(O)CO"),
    ("Glycerol", "OCC(O)CO"),
    ("Cyclopropanol", "OC1CC1"),
    ("Cyclobutanol", "OC1CCC1"),
    ("Cyclopentanol", "OC1CCCC1"),
    ("Cyclohexanol", "OC1CCCCC1"),
    ("Benzyl alcohol", "OCC1=CC=CC=C1"),
    # Carboxylic acids & esters
    ("Acetic acid", "CC(=O)O"),
    ("Propionic acid", "CCC(=O)O"),
    ("Butyric acid", "CCCC(=O)O"),
    ("Valeric acid", "CCCCC(=O)O"),
    ("Hexanoic acid", "CCCCCC(=O)O"),
    ("Methyl acetate", "COC(=O)C"),
    ("Ethyl acetate", "CCOC(=O)C"),
    ("Propyl acetate", "CCCOC(=O)C"),
    ("Butyl acetate", "CCCCOC(=O)C"),
    # Ketones & ethers
    ("Acetone", "CC(=O)C"),
    ("Butanone", "CCC(=O)C"),
    ("Pentan-2-one", "CCCC(=O)C"),
    ("Hexan-2-one", "CCCCC(=O)C"),
    ("Diethyl ether", "CCOCC"),
    ("Dipropyl ether", "CCCOCCC"),
    ("Dibutyl ether", "CCCCOCCCC"),
    ("Tetrahydrofuran", "C1CCOC1"),
    ("Tetrahydropyran", "C1CCOCC1"),
    ("1,4-Dioxane", "C1COCCO1"),
    # Aromatics
    ("Benzene", "C1=CC=CC=C1"),
    ("Toluene", "CC1=CC=CC=C1"),
    ("Ethylbenzene", "CCC1=CC=CC=C1"),
    ("o-Xylene", "CC1=CC=CC=C(C)1"),
    ("m-Xylene", "CC1=CC=CC(C)=C1"),
    ("p-Xylene", "CC1=CC=C(C)C=C1"),
    ("Chlorobenzene", "ClC1=CC=CC=C1"),
    ("Bromobenzene", "BrC1=CC=CC=C1"),
    ("Fluorobenzene", "FC1=CC=CC=C1"),
    ("Iodobenzene", "IC1=CC=CC=C1"),
    ("Phenol", "OC1=CC=CC=C1"),
    ("Aniline", "NC1=CC=CC=C1"),
    ("Benzoic acid", "OC(=O)C1=CC=CC=C1"),
    ("Benzonitrile", "N#CC1=CC=CC=C1"),
    ("Benzamide", "NC(=O)C1=CC=CC=C1"),
    ("Nitrobenzene", "[O-][N+](=O)C1=CC=CC=C1"),
    ("Anisole", "COC1=CC=CC=C1"),
    ("Acetophenone", "CC(=O)C1=CC=CC=C1"),
    ("Naphthalene", "C1=CC=C2C=CC=CC2=C1"),
    ("Biphenyl", "C1=CC=CC=C1C2=CC=CC=C2"),
    # Heterocycles
    ("Pyridine", "C1=CC=NC=C1"),
    ("Pyrimidine", "C1=NC=NC=C1"),
    ("Pyrazine", "C1=CN=CC=N1"),
    ("Pyridazine", "C1=CC=NN=C1"),
    ("Quinoline", "C1=CC=C2C(=C1)C=CC=N2"),
    ("Isoquinoline", "C1=CC=C2C(=C1)C=NC=C2"),
    ("Pyrrole", "C1=CNC=C1"),
    ("Furan", "C1=COC=C1"),
    ("Thiophene", "C1=CSC=C1"),
    ("Imidazole", "C1=CN=CN1"),
    ("Pyrazole", "C1=CNN=C1"),
    ("Oxazole", "C1=CN=CO1"),
    ("Thiazole", "C1=CN=CS1"),
    ("Indole", "C1=CC=C2C(=C1)C=CN2"),
    ("Benzofuran", "C1=CC=C2C(=C1)C=CO2"),
    ("Benzothiophene", "C1=CC=C2C(=C1)C=CS2"),
    # Amines & saturated heterocycles
    ("Methylamine", "CN"),
    ("Ethylamine", "CCN"),
    ("Propylamine", "CCCN"),
    ("Butylamine", "CCCCN"),
    ("Diethylamine", "CCNCC"),
    ("Triethylamine", "CCN(CC)CC"),
    ("Piperidine", "C1CCNCC1"),
    ("Piperazine", "C1CNCCN1"),
    ("Morpholine", "C1COCCN1"),
    ("Thiomorpholine", "C1CSCCN1"),
    ("Pyrrolidine", "C1CCNC1"),
    ("Piperidin-4-ol", "OC1CCNCC1"),
    # Halogenated alkanes
    ("Dichloromethane", "ClCCl"),
    ("Chloroform", "ClC(Cl)Cl"),
    ("Carbon tetrachloride", "ClC(Cl)(Cl)Cl"),
    ("1,2-Dichloroethane", "ClCCCl"),
    ("1,1,1-Trichloroethane", "CC(Cl)(Cl)Cl"),
    ("Fluorocyclohexane", "FC1CCCCC1"),
    ("Chlorocyclohexane", "ClC1CCCCC1"),
    ("Bromocyclohexane", "BrC1CCCCC1"),
    # Diverse extras
    ("Acetonitrile", "CC#N"),
    ("Dimethyl sulfoxide", "CS(=O)C"),
    ("Dimethylformamide", "CN(C)C=O"),
    ("Urea", "NC(N)=O"),
    ("Thiourea", "NC(N)=S"),
    ("Sulfolane", "O=S1(=O)CCCC1"),
    ("Cyclohexanone", "O=C1CCCCC1"),
    ("Cyclopentanone", "O=C1CCCC1"),
    ("p-Quinone", "O=C1C=CC(=O)C=C1"),
    ("Isopropanol", "CC(C)O"),
    ("tert-Butanol", "CC(C)(C)O")
]

# Guarantee seeds
np.random.seed(101)

# --- 1. Generate solubility_regression.csv (80 compounds) ---
# We use standard column header "activity"
regression_lines = ["name,smiles,activity\n"]
for name, smiles in compounds[:80]:
    mol = Chem.MolFromSmiles(smiles)
    mw = Descriptors.MolWt(mol)
    logp = Descriptors.MolLogP(mol)
    logs = 0.5 - 0.012 * mw - 0.75 * logp + np.random.randn() * 0.25
    regression_lines.append(f"{name},{smiles},{logs:.4f}\n")

with open("test_data/solubility_regression.csv", "w") as f:
    f.writelines(regression_lines)

# --- 2. Generate solubility_imbalanced_classification.csv (100 compounds) ---
# We use standard column header "activity"
classification_lines = ["name,smiles,activity\n"]

compounds_with_logp = []
for name, smiles in compounds:
    mol = Chem.MolFromSmiles(smiles)
    logp = Descriptors.MolLogP(mol)
    compounds_with_logp.append((logp, name, smiles))

# Sort by LogP ascending (most polar/water-soluble first)
compounds_sorted = sorted(compounds_with_logp, key=lambda x: x[0])

# Mark the first 10 as soluble (Class 1) and the remaining 90 as insoluble (Class 0)
for idx, (logp, name, smiles) in enumerate(compounds_sorted):
    label = 1 if idx < 10 else 0
    classification_lines.append(f"{name},{smiles},{label}\n")

with open("test_data/solubility_imbalanced_classification.csv", "w") as f:
    f.writelines(classification_lines)

print("Regenerated test CSV datasets with correct 'activity' headers.")
