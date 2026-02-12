"""
Molecule Thumbnail Renderer Module
"""
import base64
from rdkit import Chem
from rdkit.Chem.Draw import rdMolDraw2D

def render_thumbnail(smiles: str, size: tuple[int, int] = (200, 150)) -> str:
    """
    Renders RDKit canonical SMILES into a base64 encoded PNG or SVG data URI.
    Disables stereo R/S labels to prevent image overlaps on hover.
    """
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return ""
            
        try:
            drawer = rdMolDraw2D.MolDraw2DCairo(*size)
            drawer.drawOptions().clearBackground = False
            drawer.drawOptions().addStereoAnnotation = False
            drawer.DrawMolecule(mol)
            drawer.FinishDrawing()
            png_bytes = drawer.GetDrawingText()
            return "data:image/png;base64," + base64.b64encode(png_bytes).decode()
        except Exception:
            # Fallback to standard SVG drawer
            drawer = rdMolDraw2D.MolDraw2DSVG(*size)
            drawer.drawOptions().clearBackground = False
            drawer.drawOptions().addStereoAnnotation = False
            drawer.DrawMolecule(mol)
            drawer.FinishDrawing()
            svg_text = drawer.GetDrawingText()
            return "data:image/svg+xml;base64," + base64.b64encode(svg_text.encode()).decode()
    except Exception:
        return ""
