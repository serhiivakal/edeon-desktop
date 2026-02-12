"""
Edeon Engine — pKa Estimation Bridge & Empirical Fallbacks
"""

from typing import List, Optional
from rdkit import Chem


# Known functional group pKa approximations for empirical fallback
EMPIRICAL_PKA_PATTERNS = [
    # Acidic groups (pKa values)
    (Chem.MolFromSmarts("C(=O)[OH]"), 4.5, "Carboxylic Acid"),
    (Chem.MolFromSmarts("c1cc([OH])ccc1"), 9.9, "Phenol"),
    (Chem.MolFromSmarts("S(=O)(=O)[OH]"), 1.0, "Sulfonic Acid"),
    (Chem.MolFromSmarts("P(=O)([OH])[OH]"), 2.0, "Phosphonic Acid"),
    (Chem.MolFromSmarts("[NX3][CX3](=[OX1])[OH]"), 3.5, "Carbamic Acid"),
    (Chem.MolFromSmarts("c1n[nH]c2ccccc12"), 12.0, "Indole/Benzimidazole"),

    # Basic groups (conjugate acid pKa values)
    (Chem.MolFromSmarts("[NX3;H2;!$(N-C=O)]"), 9.8, "Primary Amine"),
    (Chem.MolFromSmarts("[NX3;H1;!$(N-C=O)]"), 10.5, "Secondary Amine"),
    (Chem.MolFromSmarts("[NX3;H0;!$(N-C=O)]"), 10.0, "Tertiary Amine"),
    (Chem.MolFromSmarts("c1ncccn1"), 5.2, "Pyridine"),
    (Chem.MolFromSmarts("c1ncncc1"), 6.8, "Imidazole"),
]


def estimate_pka(smiles: str) -> Optional[List[float]]:
    """Estimate pKa values for a molecule using pkasolver if available, or empirical SMARTS fallback.

    Returns a list of float pKa values or None if no ionizable groups match.
    """
    # 1. Try pkasolver if installed
    try:
        import pkasolver  # type: ignore
        # If pkasolver API is available:
        # (wrapped defensively)
        pka_model = pkasolver.query.query_pka(smiles)
        if pka_model and hasattr(pka_model, 'pkas'):
            return [float(p) for p in pka_model.pkas]
    except Exception:
        pass

    # 2. Empirical SMARTS match fallback
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None

    matched_pkas = []
    for pattern, pka_val, _ in EMPIRICAL_PKA_PATTERNS:
        if pattern and mol.HasSubstructMatch(pattern):
            matched_pkas.append(pka_val)

    return matched_pkas if matched_pkas else None
