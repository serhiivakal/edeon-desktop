"""
Edeon Engine — 2D Pharmacophores
2D pharmacophore fingerprints using Gobbi and default 5-feature signature factories.
"""

import numpy as np
from rdkit import Chem
from rdkit.Chem.Pharm2D import Gobbi_Pharm2D, DefaultSigFactory, Generate
from .base import FeaturizerSpec, register

def compute_pharmacophore_fp(smiles_list: list[str], params: dict, use_gobbi=True) -> np.ndarray:
    n_bits = params.get("n_bits", 2048)
    matrix = np.zeros((len(smiles_list), n_bits))
    
    # Initialize factory once
    if use_gobbi:
        factory = Gobbi_Pharm2D.factory
    else:
        factory = DefaultSigFactory()
        
    for i, smiles in enumerate(smiles_list):
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol is not None:
                fp = Generate.Gen2DFingerprint(mol, factory)
                # Fold the fingerprint modulo n_bits
                if hasattr(fp, "GetNonzeroElements"):
                    # IntSparseIntVect from Gobbi
                    for idx, val in fp.GetNonzeroElements().items():
                        matrix[i, idx % n_bits] += float(val)
                elif hasattr(fp, "GetOnBits"):
                    # SparseBitVect from DefaultSigFactory
                    for bit_idx in fp.GetOnBits():
                        matrix[i, bit_idx % n_bits] = 1.0
        except Exception:
            pass
            
    return matrix

register(FeaturizerSpec(
    id="pharm2d_gobbi",
    category="pharmacophore",
    label="2D Pharmacophore (Gobbi)",
    description="2D pharmacophore fingerprints utilizing Gobbi feature definitions (folded to fixed-width bits).",
    dimensionality=lambda params: params.get("n_bits", 2048),
    cost_estimate=lambda params, n: n * 0.006,
    compute=lambda smiles_list, params: compute_pharmacophore_fp(smiles_list, params, use_gobbi=True),
    param_schema={
        "n_bits": {"type": "integer", "enum": [1024, 2048, 4096], "default": 2048}
    },
    default_params={"n_bits": 2048}
))

register(FeaturizerSpec(
    id="pharm2d_basic",
    category="pharmacophore",
    label="2D Pharmacophore (Basic)",
    description="2D pharmacophore fingerprints utilizing standard 5-feature definitions (Acceptor, Donor, Hydrophobic, Positive, Negative).",
    dimensionality=lambda params: params.get("n_bits", 2048),
    cost_estimate=lambda params, n: n * 0.005,
    compute=lambda smiles_list, params: compute_pharmacophore_fp(smiles_list, params, use_gobbi=False),
    param_schema={
        "n_bits": {"type": "integer", "enum": [1024, 2048, 4096], "default": 2048}
    },
    default_params={"n_bits": 2048}
))
