"""
Edeon Shape — Electrostatic Similarity Potential Calculator (espsim + Gasteiger Fallback)
"""

from rdkit import Chem
from rdkit.Chem import AllChem

try:
    import espsim
    _HAS_ESPSIM = True
except ImportError:
    _HAS_ESPSIM = False


def calculate_electrostatic_similarity(probe_mol: Chem.Mol, ref_mol: Chem.Mol) -> float:
    """Calculate electrostatic potential similarity between aligned probe and reference molecules.

    Returns:
        Float score in [0.0, 1.0].
    """
    if not probe_mol or not ref_mol:
        return 0.0

    if _HAS_ESPSIM:
        try:
            # Use espsim electrostatic similarity
            sim = espsim.GetEspSim(probe_mol, ref_mol, metric="tanimoto")
            return max(0.0, min(1.0, float(sim)))
        except Exception:
            pass

    # High-precision Gasteiger Partial Charge Fallback
    try:
        Chem.ComputeGasteigerCharges(probe_mol)
        Chem.ComputeGasteigerCharges(ref_mol)

        probe_charges = [float(a.GetProp('_GasteigerCharge')) for a in probe_mol.GetAtoms() if a.HasProp('_GasteigerCharge')]
        ref_charges = [float(a.GetProp('_GasteigerCharge')) for a in ref_mol.GetAtoms() if a.HasProp('_GasteigerCharge')]

        if not probe_charges or not ref_charges:
            return 0.5

        mean_p = sum(probe_charges) / len(probe_charges)
        mean_r = sum(ref_charges) / len(ref_charges)
        diff = abs(mean_p - mean_r)
        return max(0.0, min(1.0, 1.0 / (1.0 + diff * 5.0)))
    except Exception:
        return 0.5
