"""
Edeon Engine — Protonation Variant Enumeration (Dimorphite-DL Wrapper)
"""

from typing import List, Dict, Any, Tuple
from rdkit import Chem


def enumerate_protonation_states(
    smiles: str,
    ph_min: float = 4.0,
    ph_max: float = 8.0,
    max_variants: int = 8
) -> Tuple[List[Dict[str, Any]], str]:
    """Enumerate protonation states over the pH range [ph_min, ph_max].

    Returns:
        (variants_list, method_used)
        where variants_list is a list of dicts: {"smiles": str, "charge": int}
    """
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return ([], "error")

    # 1. Try dimorphite_dl if installed
    try:
        from dimorphite_dl import DimorphiteDL  # type: ignore
        dimorphite = DimorphiteDL(
            min_ph=ph_min,
            max_ph=ph_max,
            max_variants=max_variants,
            label_states=False
        )
        protonated_smiles = dimorphite.charged_smiles_given_smiles(smiles)
        variants = []
        for p_smi in protonated_smiles:
            p_mol = Chem.MolFromSmiles(p_smi)
            if p_mol:
                charge = Chem.GetFormalCharge(p_mol)
                variants.append({"smiles": p_smi, "charge": charge})
        if variants:
            return (variants, "dimorphite_dl")
    except Exception:
        pass

    # 2. Empirical RDKit protonation state fallback
    # Neutral state
    charge = Chem.GetFormalCharge(mol)
    variants = [{"smiles": Chem.MolToSmiles(mol), "charge": charge}]

    # Simple acidic/basic site ionization heuristic for empirical fallback
    # Carboxylic acids -> deprotonated (-1) if ph_max >= 4.0
    # Primary/Secondary amines -> protonated (+1) if ph_min <= 9.0
    carboxyl = Chem.MolFromSmarts("C(=O)[OH]")
    amine = Chem.MolFromSmarts("[NX3;H1,H2;!$(N-C=O)]")

    if carboxyl and mol.HasSubstructMatch(carboxyl) and ph_max >= 4.0:
        deprotonated = Chem.RWMol(mol)
        matches = mol.GetSubstructMatches(carboxyl)
        for match in matches:
            oh_oxygen_idx = match[2]
            atom = deprotonated.GetAtomWithIdx(oh_oxygen_idx)
            if atom.GetNumExplicitHs() > 0:
                atom.SetNumExplicitHs(atom.GetNumExplicitHs() - 1)
            atom.SetFormalCharge(-1)
        try:
            dep_smi = Chem.MolToSmiles(deprotonated)
            if dep_smi not in [v["smiles"] for v in variants]:
                variants.append({"smiles": dep_smi, "charge": Chem.GetFormalCharge(deprotonated)})
        except Exception:
            pass

    if amine and mol.HasSubstructMatch(amine) and ph_min <= 9.0:
        protonated = Chem.RWMol(mol)
        matches = mol.GetSubstructMatches(amine)
        for match in matches:
            nitrogen_idx = match[0]
            atom = protonated.GetAtomWithIdx(nitrogen_idx)
            atom.SetFormalCharge(1)
        try:
            prot_smi = Chem.MolToSmiles(protonated)
            if prot_smi not in [v["smiles"] for v in variants]:
                variants.append({"smiles": prot_smi, "charge": Chem.GetFormalCharge(protonated)})
        except Exception:
            pass

    return (variants[:max_variants], "empirical_fallback")
