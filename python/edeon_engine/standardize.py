"""
Edeon Engine — SMILES Standardization

Canonicalizes SMILES strings using RDKit:
- Parse SMILES → RDKit Mol object
- Strip salts (keep largest fragment)
- Canonicalize
- Flag invalid SMILES
"""

from rdkit import Chem
from rdkit.Chem.SaltRemover import SaltRemover

# Pre-initialize salt remover (reused across calls)
_salt_remover = SaltRemover()


def standardize_single(smiles: str) -> dict:
    """Standardize a single SMILES string.

    Returns dict with:
        original: input SMILES
        canonical: standardized SMILES (or None if invalid)
        valid: bool
        error: error message if invalid
    """
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return {
                "original": smiles,
                "canonical": None,
                "valid": False,
                "error": "Failed to parse SMILES",
            }

        # Strip salts (remove counterions, keep largest fragment)
        try:
            mol = _salt_remover.StripMol(mol)
        except Exception:
            # If salt stripping fails, use the original mol
            pass

        # Canonicalize
        canonical = Chem.MolToSmiles(mol, canonical=True)

        return {
            "original": smiles,
            "canonical": canonical,
            "valid": True,
            "error": None,
        }

    except Exception as e:
        return {
            "original": smiles,
            "canonical": None,
            "valid": False,
            "error": str(e),
        }


def standardize_batch(smiles_list: list[str]) -> list[dict]:
    """Standardize a batch of SMILES strings."""
    return [standardize_single(s) for s in smiles_list]
