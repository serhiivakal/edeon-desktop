"""
Atom Contribution Maps Plotting Module

Includes Morgan circular environment bit-info calculation, BFS projection of SHAP scores to atoms,
and similarity map rendering using RDKit and Matplotlib Agg backend.
"""

import io
import base64
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit.Chem.Draw import SimilarityMaps

def _to_array(fps):
    """Safely converts list of RDKit ExplicitBitVect to NumPy matrix."""
    if not fps:
        return np.zeros((0, 0))
    dim = fps[0].GetNumBits() if len(fps) > 0 and fps[0] is not None else 2048
    matrix = np.zeros((len(fps), dim))
    for i, fp in enumerate(fps):
        if fp is not None:
            for bit in fp.GetOnBits():
                matrix[i, bit] = 1.0
    return matrix

def compute_morgan_with_bitinfo(smiles: list[str], radius: int, n_bits: int, use_features: bool = False):
    """
    Computes Morgan circular fingerprints and returns NumPy matrix along with bit-info dicts.
    """
    fps, bit_infos = [], []
    for s in smiles:
        try:
            mol = Chem.MolFromSmiles(s)
            bi = {}
            if mol is not None:
                fp = AllChem.GetMorganFingerprintAsBitVect(
                    mol, radius, n_bits, useFeatures=use_features, bitInfo=bi
                )
                fps.append(fp)
                bit_infos.append(bi)
            else:
                fps.append(None)
                bit_infos.append({})
        except Exception:
            fps.append(None)
            bit_infos.append({})
    return _to_array(fps), bit_infos

def project_bits_to_atoms(mol, bit_info: dict, bit_shap: np.ndarray) -> np.ndarray:
    """
    bit_shap: shap value per bit, length n_bits.
    Returns a per-atom weight array of shape (n_atoms,).
    """
    atom_weights = np.zeros(mol.GetNumAtoms())
    for bit_idx, envs in bit_info.items():
        if bit_idx >= len(bit_shap):
            continue
        if bit_shap[bit_idx] == 0.0:
            continue
        for centre_atom, radius in envs:
            if radius == 0:
                atom_weights[centre_atom] += bit_shap[bit_idx]
            else:
                try:
                    env = Chem.FindAtomEnvironmentOfRadiusN(mol, radius, centre_atom)
                    atom_set = {centre_atom}
                    for bond_idx in env:
                        b = mol.GetBondWithIdx(bond_idx)
                        atom_set.add(b.GetBeginAtomIdx())
                        atom_set.add(b.GetEndAtomIdx())
                    share = bit_shap[bit_idx] / len(atom_set)
                    for a in atom_set:
                        atom_weights[a] += share
                except Exception:
                    # Fallback centre atom only
                    atom_weights[centre_atom] += bit_shap[bit_idx]
    return atom_weights

def render_contribution_png(mol, atom_weights: np.ndarray,
                            size: tuple[int, int] = (500, 500)) -> str:
    """
    Renders 2D Similarity Map projection of atom contribution weights.
    Returns standard Base64 Data URI.
    """
    try:
        fig = SimilarityMaps.GetSimilarityMapFromWeights(
            mol, atom_weights.tolist(), size=size,
            colorMap="bwr", contourLines=10
        )
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", dpi=120)
        plt.close(fig)
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        # Graceful fallback to standard RDKit depiction in case matplotlib/similarity fails
        from rdkit.Chem import Draw
        try:
            img = Draw.MolToImage(mol, size=size)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
        except Exception:
            return ""
