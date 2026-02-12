"""
Edeon SAR — Matched Molecular Pair (MMP) Fragmentation & Indexing Engine
"""

from typing import List, Dict, Any, Tuple
from rdkit import Chem
from rdkit.Chem import rdMMPA


def fragment_molecule(smiles: str, min_heavies: int = 1, max_cuts: int = 2) -> List[Tuple[str, str]]:
    """Fragment a molecule using RDKit rdMMPA to yield (core, substituent) pairs.

    Returns:
        List of (core_smiles, variable_smiles) tuples.
    """
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return []

    try:
        frags = rdMMPA.FragmentMol(
            mol,
            minCuts=1,
            maxCuts=max_cuts,
            maxCutBonds=30
        )
    except Exception:
        frags = []

    res = []
    for f in frags:
        if not f or len(f) < 2:
            continue
        core_mol, var_mol = f[0], f[1]
        try:
            core_smi = Chem.MolToSmiles(core_mol) if isinstance(core_mol, Chem.Mol) else str(core_mol)
            if isinstance(var_mol, (tuple, list)):
                var_smi = ".".join(Chem.MolToSmiles(m) for m in var_mol if isinstance(m, Chem.Mol))
            elif isinstance(var_mol, Chem.Mol):
                var_smi = Chem.MolToSmiles(var_mol)
            else:
                var_smi = str(var_mol)

            if core_smi and var_smi:
                res.append((core_smi, var_smi))
        except Exception:
            continue

    return res


def index_matched_pairs(compounds: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Index matched molecular pairs across a dataset of compounds.

    Args:
        compounds: List of {"id": str, "smiles": str, "potency": float, "off_target": float}

    Returns:
        List of matched pair records:
        {"mol1": str, "mol2": str, "core": str, "r1": str, "r2": str,
         "delta_potency": float, "delta_off_target": float, "delta_selectivity": float}
    """
    mol_frags: Dict[str, List[Tuple[str, str]]] = {}
    for c in compounds:
        smi = c["smiles"]
        frags = fragment_molecule(smi)
        if frags:
            mol_frags[smi] = frags

    pairs = []
    smiles_list = list(mol_frags.keys())
    comp_map = {c["smiles"]: c for c in compounds}

    for i in range(len(smiles_list)):
        s1 = smiles_list[i]
        c1 = comp_map[s1]
        for j in range(i + 1, len(smiles_list)):
            s2 = smiles_list[j]
            c2 = comp_map[s2]

            f1 = mol_frags[s1]
            f2 = mol_frags[s2]

            # Find matching cores
            for core1, r1 in f1:
                for core2, r2 in f2:
                    if core1 == core2 and r1 != r2:
                        p1 = c1.get("potency", 0.0)
                        p2 = c2.get("potency", 0.0)
                        t1 = c1.get("off_target", 0.0)
                        t2 = c2.get("off_target", 0.0)

                        delta_p = p2 - p1
                        delta_t = t2 - t1
                        delta_sel = delta_p - delta_t

                        pairs.append({
                            "mol1": s1,
                            "mol2": s2,
                            "core": core1,
                            "r1": r1,
                            "r2": r2,
                            "delta_potency": round(delta_p, 4),
                            "delta_off_target": round(delta_t, 4),
                            "delta_selectivity": round(delta_sel, 4),
                            "transform": f"{r1} >> {r2}"
                        })

    return pairs
