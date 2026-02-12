"""
Edeon Engine — Maximum Common Substructure (MCS)

Computes the MCS across a set of molecules using RDKit's rdFMCS,
then generates SVG depictions with MCS atoms/bonds highlighted.
"""

from rdkit import Chem
from rdkit.Chem import AllChem, rdFMCS
from rdkit.Chem.Draw import rdMolDraw2D


def compute_mcs(smiles_list: list[str], timeout: int = 30) -> dict:
    """Compute the Maximum Common Substructure for a list of SMILES.

    Args:
        smiles_list: list of SMILES strings
        timeout: MCS search timeout in seconds

    Returns:
        dict with:
            mcs_smarts: SMARTS pattern of the MCS
            num_atoms: number of atoms in MCS
            num_bonds: number of bonds in MCS
            num_molecules: how many input molecules were valid
            canceled: whether the search timed out
    """
    # Parse molecules, skip invalid ones
    mols = []
    valid_indices = []
    for i, smi in enumerate(smiles_list):
        mol = Chem.MolFromSmiles(smi)
        if mol is not None:
            mols.append(mol)
            valid_indices.append(i)

    if len(mols) < 2:
        return {
            "mcs_smarts": None,
            "num_atoms": 0,
            "num_bonds": 0,
            "num_molecules": len(mols),
            "canceled": False,
            "error": "Need at least 2 valid molecules for MCS",
        }

    # Run MCS search
    mcs_result = rdFMCS.FindMCS(
        mols,
        timeout=timeout,
        threshold=0.8,  # MCS must be present in 80% of molecules
        ringMatchesRingOnly=True,
        completeRingsOnly=True,
        matchValences=False,
        atomCompare=rdFMCS.AtomCompare.CompareElements,
        bondCompare=rdFMCS.BondCompare.CompareOrder,
    )

    mcs_smarts = mcs_result.smartsString if mcs_result.smartsString else None

    return {
        "mcs_smarts": mcs_smarts,
        "num_atoms": mcs_result.numAtoms,
        "num_bonds": mcs_result.numBonds,
        "num_molecules": len(mols),
        "canceled": mcs_result.canceled,
    }


def depict_with_mcs(
    smiles: str,
    mcs_smarts: str,
    width: int = 250,
    height: int = 180,
) -> dict:
    """Generate SVG depiction of a molecule with MCS atoms highlighted.

    Args:
        smiles: SMILES of the molecule to depict
        mcs_smarts: SMARTS pattern of the MCS to highlight
        width: SVG width
        height: SVG height

    Returns:
        dict with svg string and match info
    """
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return {"svg": None, "valid": False, "error": "Invalid SMILES"}

        AllChem.Compute2DCoords(mol)

        # Find MCS match in this molecule
        mcs_mol = Chem.MolFromSmarts(mcs_smarts)
        highlight_atoms = []
        highlight_bonds = []

        if mcs_mol is not None:
            match = mol.GetSubstructMatch(mcs_mol)
            if match:
                highlight_atoms = list(match)
                # Find bonds between matched atoms
                for bond in mol.GetBonds():
                    a1 = bond.GetBeginAtomIdx()
                    a2 = bond.GetEndAtomIdx()
                    if a1 in highlight_atoms and a2 in highlight_atoms:
                        highlight_bonds.append(bond.GetIdx())

        # Draw with highlights
        drawer = rdMolDraw2D.MolDraw2DSVG(width, height)
        opts = drawer.drawOptions()
        opts.bondLineWidth = 1.5
        opts.padding = 0.15
        opts.clearBackground = False

        # Set highlight colors (green tint for MCS)
        highlight_atom_colors = {a: (0.2, 0.7, 0.4, 0.3) for a in highlight_atoms}
        highlight_bond_colors = {b: (0.2, 0.7, 0.4, 0.5) for b in highlight_bonds}
        highlight_radii = {a: 0.35 for a in highlight_atoms}

        drawer.DrawMolecule(
            mol,
            highlightAtoms=highlight_atoms,
            highlightBonds=highlight_bonds,
            highlightAtomColors=highlight_atom_colors,
            highlightBondColors=highlight_bond_colors,
            highlightAtomRadii=highlight_radii,
        )
        drawer.FinishDrawing()
        svg = drawer.GetDrawingText()

        return {
            "svg": svg,
            "valid": True,
            "matched_atoms": len(highlight_atoms),
            "total_atoms": mol.GetNumAtoms(),
        }

    except Exception as e:
        return {"svg": None, "valid": False, "error": str(e)}
