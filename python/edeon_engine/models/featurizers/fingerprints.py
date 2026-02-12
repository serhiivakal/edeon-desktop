"""
Edeon Engine — Fingerprints
Standard circular, path, and key-based molecular fingerprints from RDKit.
"""

import numpy as np
from rdkit import Chem
from rdkit.Chem import rdFingerprintGenerator, MACCSkeys
from rdkit.Avalon import pyAvalonTools
from .base import FeaturizerSpec, register

def compute_morgan_fp(smiles_list: list[str], params: dict) -> np.ndarray:
    radius = params.get("radius", 2)
    n_bits = params.get("n_bits", 2048)
    use_features = params.get("use_features", False)
    
    invGen = None
    if use_features:
        invGen = rdFingerprintGenerator.GetMorganFeatureAtomInvGen()
        
    gen = rdFingerprintGenerator.GetMorganGenerator(radius=radius, fpSize=n_bits, atomInvariantsGenerator=invGen)
    matrix = np.zeros((len(smiles_list), n_bits))
    
    for i, smiles in enumerate(smiles_list):
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol is not None:
                matrix[i] = gen.GetFingerprintAsNumPy(mol)
        except Exception:
            pass
    return matrix

def compute_maccs_fp(smiles_list: list[str], params: dict) -> np.ndarray:
    matrix = np.zeros((len(smiles_list), 167))
    for i, smiles in enumerate(smiles_list):
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol is not None:
                fp = MACCSkeys.GenMACCSKeys(mol)
                matrix[i] = np.array(list(fp))
        except Exception:
            pass
    return matrix

def compute_avalon_fp(smiles_list: list[str], params: dict) -> np.ndarray:
    n_bits = params.get("n_bits", 1024)
    matrix = np.zeros((len(smiles_list), n_bits))
    for i, smiles in enumerate(smiles_list):
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol is not None:
                fp = pyAvalonTools.GetAvalonFP(mol, nBits=n_bits)
                matrix[i] = np.array(list(fp))
        except Exception:
            pass
    return matrix

def compute_rdkit_topological_fp(smiles_list: list[str], params: dict) -> np.ndarray:
    n_bits = params.get("n_bits", 2048)
    max_path = params.get("max_path", 7)
    gen = rdFingerprintGenerator.GetRDKitFPGenerator(maxPath=max_path, fpSize=n_bits)
    matrix = np.zeros((len(smiles_list), n_bits))
    for i, smiles in enumerate(smiles_list):
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol is not None:
                matrix[i] = gen.GetFingerprintAsNumPy(mol)
        except Exception:
            pass
    return matrix

def compute_atom_pair_fp(smiles_list: list[str], params: dict) -> np.ndarray:
    n_bits = params.get("n_bits", 2048)
    gen = rdFingerprintGenerator.GetAtomPairGenerator(fpSize=n_bits)
    matrix = np.zeros((len(smiles_list), n_bits))
    for i, smiles in enumerate(smiles_list):
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol is not None:
                matrix[i] = gen.GetFingerprintAsNumPy(mol)
        except Exception:
            pass
    return matrix

def compute_topological_torsion_fp(smiles_list: list[str], params: dict) -> np.ndarray:
    n_bits = params.get("n_bits", 2048)
    gen = rdFingerprintGenerator.GetTopologicalTorsionGenerator(fpSize=n_bits)
    matrix = np.zeros((len(smiles_list), n_bits))
    for i, smiles in enumerate(smiles_list):
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol is not None:
                matrix[i] = gen.GetFingerprintAsNumPy(mol)
        except Exception:
            pass
    return matrix

# For backward compatibility
def compute_morgan_fingerprints(mols, radius=2, n_bits=1024):
    fps = []
    for mol in mols:
        try:
            gen = rdFingerprintGenerator.GetMorganGenerator(radius=radius, fpSize=n_bits)
            fps.append(list(gen.GetFingerprintAsNumPy(mol)))
        except Exception:
            fps.append([0] * n_bits)
    return fps

# Register Specs
register(FeaturizerSpec(
    id="morgan",
    category="fingerprints",
    label="Morgan (ECFP)",
    description="Extended-Connectivity Fingerprints (ECFP) representing circular atom neighborhoods.",
    dimensionality=lambda params: params.get("n_bits", 2048),
    cost_estimate=lambda params, n: n * 0.001,
    compute=lambda smiles_list, params: compute_morgan_fp(smiles_list, {**params, "use_features": False}),
    param_schema={
        "radius": {"type": "integer", "minimum": 1, "maximum": 4, "default": 2},
        "n_bits": {"type": "integer", "enum": [512, 1024, 2048], "default": 2048}
    },
    default_params={"radius": 2, "n_bits": 2048}
))

register(FeaturizerSpec(
    id="fcfp",
    category="fingerprints",
    label="FCFP",
    description="Feature Extended-Connectivity Fingerprints circular representation using chemical feature definitions.",
    dimensionality=lambda params: params.get("n_bits", 2048),
    cost_estimate=lambda params, n: n * 0.0012,
    compute=lambda smiles_list, params: compute_morgan_fp(smiles_list, {**params, "use_features": True}),
    param_schema={
        "radius": {"type": "integer", "minimum": 1, "maximum": 4, "default": 2},
        "n_bits": {"type": "integer", "enum": [512, 1024, 2048], "default": 2048}
    },
    default_params={"radius": 2, "n_bits": 2048}
))

register(FeaturizerSpec(
    id="maccs",
    category="fingerprints",
    label="MACCS Keys",
    description="MACCS structural keys defining 167 specific, predefined structural substructure fragments.",
    dimensionality=lambda params: 167,
    cost_estimate=lambda params, n: n * 0.0008,
    compute=compute_maccs_fp,
    param_schema={},
    default_params={}
))

register(FeaturizerSpec(
    id="avalon",
    category="fingerprints",
    label="Avalon",
    description="Avalon fingerprints combining substructure path queries and structural feature keys.",
    dimensionality=lambda params: params.get("n_bits", 1024),
    cost_estimate=lambda params, n: n * 0.0015,
    compute=compute_avalon_fp,
    param_schema={
        "n_bits": {"type": "integer", "enum": [512, 1024, 2048], "default": 1024}
    },
    default_params={"n_bits": 1024}
))

register(FeaturizerSpec(
    id="rdkit_topological",
    category="fingerprints",
    label="RDKit Topological",
    description="Topological linear path-based substructure fingerprints.",
    dimensionality=lambda params: params.get("n_bits", 2048),
    cost_estimate=lambda params, n: n * 0.005 * (params.get("max_path", 7) / 7.0),
    compute=compute_rdkit_topological_fp,
    param_schema={
        "n_bits": {"type": "integer", "enum": [512, 1024, 2048], "default": 2048},
        "max_path": {"type": "integer", "minimum": 1, "maximum": 7, "default": 7}
    },
    default_params={"n_bits": 2048, "max_path": 7}
))

register(FeaturizerSpec(
    id="atom_pair",
    category="fingerprints",
    label="Atom Pairs",
    description="Atom pair distance-based molecular fingerprints capturing atomic environments and topological distance.",
    dimensionality=lambda params: params.get("n_bits", 2048),
    cost_estimate=lambda params, n: n * 0.002,
    compute=compute_atom_pair_fp,
    param_schema={
        "n_bits": {"type": "integer", "enum": [512, 1024, 2048], "default": 2048}
    },
    default_params={"n_bits": 2048}
))

register(FeaturizerSpec(
    id="topological_torsion",
    category="fingerprints",
    label="Topological Torsions",
    description="Topological torsion-based molecular fingerprints representing path lengths of four bonded non-hydrogen atoms.",
    dimensionality=lambda params: params.get("n_bits", 2048),
    cost_estimate=lambda params, n: n * 0.002,
    compute=compute_topological_torsion_fp,
    param_schema={
        "n_bits": {"type": "integer", "enum": [512, 1024, 2048], "default": 2048}
    },
    default_params={"n_bits": 2048}
))
