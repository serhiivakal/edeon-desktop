"""
Edeon Engine — 2D Molecule Depiction

Generates SVG images of molecular structures from SMILES using RDKit's
MolDraw2DSVG renderer. Produces clean, publication-quality 2D depictions.
"""

from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit.Chem.Draw import rdMolDraw2D


def depict_molecule(smiles: str, width: int = 250, height: int = 180) -> dict:
    """Generate an SVG depiction of a molecule from SMILES.

    Args:
        smiles: SMILES string
        width: SVG width in pixels
        height: SVG height in pixels

    Returns:
        dict with:
            svg: SVG string (or None if invalid)
            valid: bool
            error: error message if invalid
    """
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return {"svg": None, "valid": False, "error": "Failed to parse SMILES"}

        # Compute 2D coordinates
        AllChem.Compute2DCoords(mol)

        # Set up the drawer
        drawer = rdMolDraw2D.MolDraw2DSVG(width, height)

        # Style options for a clean, modern look
        opts = drawer.drawOptions()
        opts.bondLineWidth = 1.5
        opts.padding = 0.15
        opts.additionalAtomLabelPadding = 0.05
        opts.fixedBondLength = 25
        opts.clearBackground = False  # Transparent background

        drawer.DrawMolecule(mol)
        drawer.FinishDrawing()

        svg = drawer.GetDrawingText()

        return {"svg": svg, "valid": True, "error": None}

    except Exception as e:
        return {"svg": None, "valid": False, "error": str(e)}


def depict_batch(smiles_list: list[str], width: int = 250, height: int = 180) -> list[dict]:
    """Generate SVG depictions for a batch of SMILES."""
    return [depict_molecule(s, width, height) for s in smiles_list]
