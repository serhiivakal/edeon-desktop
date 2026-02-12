"""
Edeon Engine — 2D Descriptors
Standard 2D molecular property and structural counts descriptors from RDKit.
"""

import os
import json
import time
import numpy as np
from rdkit import Chem
from rdkit.Chem import Descriptors
from .base import FeaturizerSpec, register

# Subsets
ALL_DESCRIPTORS = {name for name, _ in Descriptors._descList}

LIPINSKI = {"MolWt", "MolLogP", "NumHDonors", "NumHAcceptors", "TPSA", "NumRotatableBonds"}
# Tice (2001) subset for agrochemical design target ranges (MW <= 500, LogP <= 5.0, HBD <= 3, HBA <= 12, RotBonds <= 12).
# Citation: Tice, M. J. (2001). "Selecting the right compounds for screening: does Lipinski's Rule of 5 for pharmaceuticals apply to agrochemicals?" Pest Management Science, 57(10), 897-905.
TICE = {"MolWt", "MolLogP", "NumHDonors", "NumHAcceptors", "TPSA", "NumRotatableBonds"}

CONSTITUTIONAL = ALL_DESCRIPTORS.intersection({
    "HeavyAtomCount", "NHOHCount", "NOCount", "NumHAcceptors", "NumHDonors", 
    "NumHeteroatoms", "NumRotatableBonds", "NumValenceElectrons", "RingCount"
})

TOPOLOGICAL = ALL_DESCRIPTORS.intersection({
    "BertzCT", "BalabanJ", "HallKierAlpha", "Ipc", "Kappa1", "Kappa2", "Kappa3", 
    "LabuteASA", "PEOE_VSA1", "PEOE_VSA2", "PEOE_VSA3", "PEOE_VSA4", "PEOE_VSA5", 
    "PEOE_VSA6", "PEOE_VSA7", "PEOE_VSA8", "PEOE_VSA9", "PEOE_VSA10", "PEOE_VSA11", 
    "PEOE_VSA12", "PEOE_VSA13", "PEOE_VSA14", "SMR_VSA1", "SMR_VSA2", "SMR_VSA3", 
    "SMR_VSA4", "SMR_VSA5", "SMR_VSA6", "SMR_VSA7", "SMR_VSA8", "SMR_VSA9", 
    "SMR_VSA10", "SlogP_VSA1", "SlogP_VSA2", "SlogP_VSA3", "SlogP_VSA4", "SlogP_VSA5", 
    "SlogP_VSA6", "SlogP_VSA7", "SlogP_VSA8", "SlogP_VSA9", "SlogP_VSA10", "SlogP_VSA11", 
    "SlogP_VSA12", "TPSA"
})

ELECTROTOPOLOGICAL = ALL_DESCRIPTORS.intersection({
    "MaxEStateIndex", "MinEStateIndex", "MaxAbsEStateIndex", "MinAbsEStateIndex", 
    "EState_VSA1", "EState_VSA2", "EState_VSA3", "EState_VSA4", "EState_VSA5", 
    "EState_VSA6", "EState_VSA7", "EState_VSA8", "EState_VSA9", "EState_VSA10", 
    "EState_VSA11", "VSA_EState1", "VSA_EState2", "VSA_EState3", "VSA_EState4", 
    "VSA_EState5", "VSA_EState6", "VSA_EState7", "VSA_EState8", "VSA_EState9", 
    "VSA_EState10"
})

# Compile active descriptor functions dictionary
DESCRIPTORS_DICT = {name: func for name, func in Descriptors._descList}

# Cache and factor logic
BENCHMARK_CACHE_FILE = os.path.join(os.path.dirname(__file__), "benchmark_cache.json")

def get_descriptor_cost_factor():
    if os.path.exists(BENCHMARK_CACHE_FILE):
        try:
            with open(BENCHMARK_CACHE_FILE, "r") as f:
                cache = json.load(f)
                if "descriptor_factor" in cache:
                    return cache["descriptor_factor"]
        except Exception:
            pass
            
    mol = Chem.MolFromSmiles("CC(C)CC1=CC=C(C=C1)C(C)C(=O)O")
    descs = [x[1] for x in Descriptors._descList[:10]]
    start_time = time.perf_counter()
    for _ in range(50):
        for desc in descs:
            try:
                desc(mol)
            except Exception:
                pass
    end_time = time.perf_counter()
    total_evals = 50 * len(descs)
    factor = (end_time - start_time) / total_evals
    factor = max(1e-6, min(1e-4, factor))
    try:
        with open(BENCHMARK_CACHE_FILE, "w") as f:
            json.dump({"descriptor_factor": factor}, f)
    except Exception:
        pass
    return factor

def compute_descriptors_2d(smiles_list: list[str], params: dict) -> np.ndarray:
    selected = params.get("selected", list(LIPINSKI))
    if not selected:
        selected = list(LIPINSKI)
        
    n_compounds = len(smiles_list)
    n_features = len(selected)
    matrix = np.zeros((n_compounds, n_features))
    
    for i, smiles in enumerate(smiles_list):
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol is not None:
                for j, name in enumerate(selected):
                    func = DESCRIPTORS_DICT.get(name)
                    if func is not None:
                        matrix[i, j] = float(func(mol))
        except Exception:
            pass
            
    return matrix

# For backward compatibility
def extract_descriptors(smiles_list):
    """
    Extract legacy RDKit descriptors.
    """
    features = []
    valid_indices = []
    mols = []
    for idx, smiles in enumerate(smiles_list):
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol is not None:
                mw = Descriptors.MolWt(mol)
                logp = Descriptors.MolLogP(mol)
                tpsa = Descriptors.TPSA(mol)
                hbd = Descriptors.NumHDonors(mol)
                hba = Descriptors.NumHAcceptors(mol)
                rot = Descriptors.NumRotatableBonds(mol)
                features.append({
                    "MW": mw, "LogP": logp, "TPSA": tpsa,
                    "HBD": hbd, "HBA": hba, "RotBonds": rot
                })
                valid_indices.append(idx)
                mols.append(mol)
        except Exception:
            continue
    return features, valid_indices, mols

register(FeaturizerSpec(
    id="descriptors_2d",
    category="descriptors_2d",
    label="2D Descriptors",
    description="Standard molecular descriptors from RDKit including Lipinski properties, constitutional attributes, and topological descriptors.",
    dimensionality=lambda params: len(params.get("selected", list(LIPINSKI))),
    cost_estimate=lambda params, n: n * len(params.get("selected", list(LIPINSKI))) * get_descriptor_cost_factor(),
    compute=compute_descriptors_2d,
    param_schema={
        "selected": {
            "type": "array",
            "items": {"type": "string", "enum": sorted(list(ALL_DESCRIPTORS))},
            "default": sorted(list(LIPINSKI))
        }
    },
    default_params={"selected": sorted(list(LIPINSKI))}
))
