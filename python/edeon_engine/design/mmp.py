"""
Matched Molecular Pairs (MMP) transforms for agrochemical lead optimization.
Provides standard single-point structural transformations to address common liabilities.
"""

from rdkit import Chem
from rdkit.Chem import AllChem

# Standard single-point transformations derived from common agrochemical optimization pathways
MMP_TRANSFORMS = [
    {
        "name": "Dealkylation",
        "smirks": "[C:1][O:2][C:3]>>[C:1][O:2][H]",
        "description": "O-dealkylation to increase water solubility, lower LogP, and reduce bioaccumulation.",
        "target_liability": "bioaccumulation"
    },
    {
        "name": "Fluorination (aromatic)",
        "smirks": "[c:1][H]>>[c:1][F]",
        "description": "Aromatic fluorination to block metabolic oxidation sites, reducing toxic metabolites.",
        "target_liability": "toxicity"
    },
    {
        "name": "Hydroxylation (aromatic)",
        "smirks": "[c:1][H]>>[c:1][O][H]",
        "description": "Aromatic hydroxylation to facilitate rapid phase II conjugation and excretion.",
        "target_liability": "persistence"
    },
    {
        "name": "Methylation (aromatic)",
        "smirks": "[c:1][H]>>[c:1][C]",
        "description": "Aromatic methylation to increase lipophilicity and soil sorption (Koc).",
        "target_liability": "leaching"
    },
    {
        "name": "Chlorine to Methyl",
        "smirks": "[c:1][Cl]>>[c:1][C]",
        "description": "Replaces chlorine with a methyl group to reduce aquatic toxicity and persistence.",
        "target_liability": "toxicity"
    }
]

def apply_mmp_transforms(smiles: str) -> list[dict]:
    """
    Applies common MMP single-point transformations to the starting SMILES.
    Returns a list of unique generated analog dicts:
      {
        "smiles": "...",
        "rule_name": "...",
        "description": "..."
      }
    """
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return []

    analogs = []
    seen_smiles = {Chem.MolToSmiles(mol, canonical=True)}

    for transform in MMP_TRANSFORMS:
        try:
            rxn = AllChem.ReactionFromSmarts(transform["smirks"])
            products = rxn.RunReactants((mol,))
            for prod_tuple in products:
                prod_mol = prod_tuple[0]
                try:
                    Chem.SanitizeMol(prod_mol)
                    prod_smiles = Chem.MolToSmiles(prod_mol, canonical=True)
                    if prod_smiles not in seen_smiles:
                        seen_smiles.add(prod_smiles)
                        analogs.append({
                            "smiles": prod_smiles,
                            "rule_name": transform["name"],
                            "description": transform["description"],
                            "target_liability": transform["target_liability"]
                        })
                except Exception:
                    continue
        except Exception as e:
            print(f"Error applying MMP transform {transform['name']}: {e}")
            continue

    return analogs
