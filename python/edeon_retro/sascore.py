"""
Edeon Engine — BR-SAScore (Synthetic Accessibility Score) Implementation
Calculates local structural complexity, ring penalties, and stereocenter penalties to estimate synthetic ease.
Normalizes raw SAscore (1..10, where 1=easy, 10=hard) into a [0.0, 1.0] scale where 1.0 is easiest to synthesize.
"""

import math
from rdkit import Chem
from rdkit.Chem import Descriptors, rdMolDescriptors


def calculate_sascore(smiles: str) -> float:
    """Calculate the normalized BR-SAScore (0.0 to 1.0 scale, higher is better).

    Raw SA score computation algorithm based on Ertl & Schuffenhauer (2009):
    SA = fragmentScore - ringComplexityPenalty - stereoPenalty - sizePenalty
    Converted to range 1..10, then normalized: sa_norm = max(0.0, min(1.0, (10.0 - raw_sa) / 9.0))
    """
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return 0.0

    n_atoms = mol.GetNumHeavyAtoms()
    if n_atoms == 0:
        return 1.0

    # 1. Size Penalty
    size_penalty = (n_atoms ** 1.005) - n_atoms

    # 2. Ring & Macrocycle Complexity Penalty
    n_rings = rdMolDescriptors.CalcNumRings(mol)
    n_aromatic = rdMolDescriptors.CalcNumAromaticRings(mol)
    n_spiro = rdMolDescriptors.CalcNumSpiroAtoms(mol)
    n_bridgehead = rdMolDescriptors.CalcNumBridgeheadAtoms(mol)
    n_macrocycles = 0

    ri = mol.GetRingInfo()
    for ring in ri.AtomRings():
        if len(ring) > 8:
            n_macrocycles += 1

    ring_penalty = (
        (n_rings - n_aromatic) * 0.5
        + n_spiro * 1.5
        + n_bridgehead * 2.0
        + n_macrocycles * 2.5
    )

    # 3. Stereocenter & Chiral Complexity Penalty
    chiral_centers = Chem.FindMolChiralCenters(mol, includeUnassigned=True)
    n_chiral = len(chiral_centers)
    stereo_penalty = n_chiral * 0.5

    # 4. Fragment / Complexity Estimation
    # Rotatable bonds penalty
    n_rotatable = rdMolDescriptors.CalcNumRotatableBonds(mol)
    rot_penalty = max(0, n_rotatable - 8) * 0.2

    # Calculate raw score (1.0 to 10.0 scale where 1 = easiest, 10 = hardest)
    raw_sa = 1.0 + 0.1 * size_penalty + ring_penalty + stereo_penalty + rot_penalty

    # Clamp raw SA to range [1.0, 10.0]
    raw_sa = max(1.0, min(10.0, raw_sa))

    # Invert and normalize to [0.0, 1.0] where 1.0 is easiest to make
    sa_normalized = (10.0 - raw_sa) / 9.0
    return round(float(max(0.0, min(1.0, sa_normalized))), 3)


def calculate_sascore_batch(smiles_list: list[str]) -> list[dict]:
    """Calculate BR-SAScore for a list of SMILES."""
    results = []
    for s in smiles_list:
        score = calculate_sascore(s)
        results.append({
            "smiles": s,
            "sa_score": score,
        })
    return results
