"""
Edeon Engine — Molecular Property Calculation

Computes physicochemical properties using RDKit Descriptors:
- MW (molecular weight)
- LogP (Crippen)
- TPSA (topological polar surface area)
- HBD (hydrogen bond donors)
- HBA (hydrogen bond acceptors)
- RotatableBonds
"""

from rdkit import Chem
from rdkit.Chem import Descriptors, Crippen


def compute_properties_single(smiles: str) -> dict:
    """Compute molecular properties for a single SMILES.

    Returns dict with property values, or None values if SMILES is invalid.
    """
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {
            "smiles": smiles,
            "valid": False,
            "mol_weight": None,
            "logp": None,
            "tpsa": None,
            "hbd": None,
            "hba": None,
            "rotatable_bonds": None,
        }

    return {
        "smiles": smiles,
        "valid": True,
        "mol_weight": round(Descriptors.MolWt(mol), 2),
        "logp": round(Crippen.MolLogP(mol), 2),
        "tpsa": round(Descriptors.TPSA(mol), 1),
        "hbd": Descriptors.NumHDonors(mol),
        "hba": Descriptors.NumHAcceptors(mol),
        "rotatable_bonds": Descriptors.NumRotatableBonds(mol),
    }


def compute_properties_batch(smiles_list: list[str]) -> list[dict]:
    """Compute properties for a batch of SMILES strings."""
    return [compute_properties_single(s) for s in smiles_list]
