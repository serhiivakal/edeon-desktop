"""
Edeon Shape — Conformer Generation & Open3DAlign Shape Overlap Engine
"""

from typing import Tuple, Optional
from rdkit import Chem
from rdkit.Chem import AllChem, rdMolAlign, rdShapeHelpers


def prepare_3d_conformer(smiles: str, num_conformers: int = 10) -> Optional[Chem.Mol]:
    """Generate 3D conformers for a SMILES using ETKDGv3 and MMFF minimization."""
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return None

    mol = Chem.AddHs(mol)
    try:
        params = AllChem.ETKDGv3()
        params.randomSeed = 42
        cids = AllChem.EmbedMultipleConfs(mol, numConfs=num_conformers, params=params)
        if not cids:
            return None

        # MMFF minimization
        for cid in cids:
            try:
                AllChem.MMFFOptimizeMolecule(mol, confId=cid, maxIters=200)
            except Exception:
                pass
        return mol
    except Exception:
        return None


def calculate_shape_overlap(probe_mol: Chem.Mol, ref_mol: Chem.Mol) -> Tuple[float, Optional[Chem.Mol]]:
    """Align probe molecule onto reference molecule using Open3DAlign (O3A).

    Returns:
        Tuple of (shape_similarity [0.0, 1.0], aligned_probe_mol).
    """
    if not probe_mol or not ref_mol:
        return 0.0, None

    try:
        # Create MMFF properties for Open3DAlign
        py_probe = AllChem.MMFFGetMoleculeProperties(probe_mol)
        py_ref = AllChem.MMFFGetMoleculeProperties(ref_mol)

        if py_probe and py_ref:
            o3a = rdMolAlign.GetO3A(probe_mol, ref_mol, py_probe, py_ref)
            o3a.Align()
            # Calculate shape Tanimoto similarity
            shape_sim = float(rdShapeHelpers.ShapeTanimotoDist(probe_mol, ref_mol))
            shape_score = max(0.0, min(1.0, 1.0 - shape_sim))
            return shape_score, probe_mol
    except Exception:
        pass

    # Basic centroid alignment fallback
    try:
        rmsd = rdMolAlign.AlignMol(probe_mol, ref_mol)
        shape_score = max(0.0, min(1.0, 1.0 / (1.0 + rmsd)))
        return shape_score, probe_mol
    except Exception:
        return 0.0, probe_mol
