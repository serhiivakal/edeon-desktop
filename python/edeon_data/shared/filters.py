"""Common compound filters (atoms, MW range, etc.)."""
from rdkit import Chem
from rdkit.Chem import Descriptors
from typing import Set

ATOM_ALLOWLIST_DEFAULT = {"H", "B", "C", "N", "O", "F", "Si", "P", "S", "Cl", "Se", "Br", "I"}

def check_atom_allowlist(mol: Chem.Mol, allowlist: Set[str] = ATOM_ALLOWLIST_DEFAULT) -> bool:
    """Returns True if the molecule contains only allowed atoms."""
    for atom in mol.GetAtoms():
        if atom.GetSymbol() not in allowlist:
            return False
    return True

def check_mw_range(mol: Chem.Mol, mw_min: float = 50.0, mw_max: float = 1500.0) -> bool:
    """Returns True if exact molecular weight is within the range."""
    mw = Descriptors.ExactMolWt(mol)
    return mw_min <= mw <= mw_max
