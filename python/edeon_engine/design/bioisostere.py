"""
Bioisosteric replacement rules for agrochemical lead optimization.
Contains curated, permissively licensed rules for functional group swaps
designed to improve environmental fate, selectivity, or safety profiles.
"""

from rdkit import Chem
from rdkit.Chem import AllChem

# Curated bioisosteric replacement rules (SMIRKS transforms)
# Each rule has: name, smirks, description, and target_liability it addresses
BIOISOSTERE_RULES = [
    {
        "name": "Ester to Oxadiazole",
        "smirks": "[C:1](=[O:2])-[O:3][C:4]>>[c:1]1n[o:3]c([C:4])n1",
        "description": "Replaces hydrolytically unstable ester with a stable 1,2,4-oxadiazole bioisostere to reduce rapid soil degradation (increase DT50).",
        "target_liability": "persistence"
    },
    {
        "name": "Amide to Triazole",
        "smirks": "[C:1](=[O:2])-[NH:3][C:4]>>[c:1]1n[nH:3]c([C:4])n1",
        "description": "Replaces amide linkage with a 1,2,4-triazole to increase metabolic stability and alter soil sorption.",
        "target_liability": "persistence"
    },
    {
        "name": "Halogen Swap: Cl to F",
        "smirks": "[c:1][Cl:2]>>[c:1][F:2]",
        "description": "Replaces chlorine with fluorine to block metabolic oxidation sites, reducing toxicity or altering persistence.",
        "target_liability": "toxicity"
    },
    {
        "name": "Halogen Swap: Cl to CF3",
        "smirks": "[c:1][Cl:2]>>[c:1](C([F])([F])[F])",
        "description": "Replaces chlorine with trifluoromethyl to increase lipophilicity and soil sorption (Koc), reducing leaching risk.",
        "target_liability": "leaching"
    },
    {
        "name": "Ether to Fluoromethyl",
        "smirks": "[c:1]-[O:2]-[C:3]>>[c:1]-C([F])([F])",
        "description": "Replaces an ether linkage with a difluoromethyl group to prevent metabolic O-dealkylation and reduce toxicity.",
        "target_liability": "toxicity"
    },
    {
        "name": "Carboxylic Acid to Tetrazole",
        "smirks": "[C:1](=[O:2])-[O:3][H:4]>>[c:1]1nn[nH]n1",
        "description": "Replaces carboxylic acid with tetrazole bioisostere to maintain acidity/charge while reducing mobility (leaching risk).",
        "target_liability": "leaching"
    },
    {
        "name": "Benzene to Pyridine",
        "smirks": "[c:1]1[cH:2][cH:3][cH:4][cH:5][cH:6]1>>[c:1]1[n:2][cH:3][cH:4][cH:5][cH:6]1",
        "description": "Replaces benzene with pyridine to lower LogP, reduce bioaccumulation (BCF), and increase water solubility.",
        "target_liability": "bioaccumulation"
    }
]

def apply_bioisostere_rules(smiles: str) -> list[dict]:
    """
    Applies the curated bioisosteric replacement rules to a starting SMILES.
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

    for rule in BIOISOSTERE_RULES:
        try:
            rxn = AllChem.ReactionFromSmarts(rule["smirks"])
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
                            "rule_name": rule["name"],
                            "description": rule["description"],
                            "target_liability": rule["target_liability"]
                        })
                except Exception:
                    continue
        except Exception as e:
            print(f"Error applying rule {rule['name']}: {e}")
            continue

    return analogs
