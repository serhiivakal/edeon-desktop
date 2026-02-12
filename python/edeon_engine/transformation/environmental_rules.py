"""
Edeon Engine — Environmental Transformation SMIRKS Rules Library
Curated rule sets for soil microbial, photolysis, and abiotic hydrolysis pathways.
"""

from typing import List, Dict, Any
from rdkit import Chem
from rdkit.Chem import AllChem


ENVIRONMENTAL_SMIRKS_RULES: List[Dict[str, Any]] = [
    # Soil Microbial Rules
    {
        "id": "soil_n_dealkylation",
        "name": "Soil N-Dealkylation",
        "class": "soil_microbial",
        "smarts": "[#6:1][N:2]([C:3][H:4])>>[#6:1][N:2][H].[C:3]=[O:4]",
    },
    {
        "id": "soil_o_demethylation",
        "name": "Soil O-Demethylation",
        "class": "soil_microbial",
        "smarts": "[c:1][O:2][CH3:3]>>[c:1][O:2][H].[CH2:3]=O",
    },
    {
        "id": "soil_nitroreduction",
        "name": "Soil Nitroreduction",
        "class": "soil_microbial",
        "smarts": "[c:1][N+:2](=[O:3])[O-:4]>>[c:1][N:2]([H])[H]",
    },
    {
        "id": "soil_aromatic_hydroxylation",
        "name": "Soil Aromatic Hydroxylation",
        "class": "soil_microbial",
        "smarts": "[c:1][H:2]>>[c:1][OH:2]",
    },

    # Photolysis Rules
    {
        "id": "photo_dehalogenation",
        "name": "Photolytic Dehalogenation",
        "class": "photolysis",
        "smarts": "[c:1][Cl,Br:2]>>[c:1][H:2]",
    },
    {
        "id": "photo_ether_cleavage",
        "name": "Photolytic Diaryl Ether Cleavage",
        "class": "photolysis",
        "smarts": "[c:1][O:2][c:3]>>[c:1][OH:2].[c:3][OH]",
    },

    # Hydrolysis Rules
    {
        "id": "ester_hydrolysis",
        "name": "Ester Hydrolysis",
        "class": "hydrolysis",
        "smarts": "[C:1](=[O:2])[O:3][C:4]>>[C:1](=[O:2])[OH].[O:3][C:4]",
    },
    {
        "id": "carbamate_hydrolysis",
        "name": "Carbamate Hydrolysis",
        "class": "hydrolysis",
        "smarts": "[C:1](=[O:2])([N:3])[O:4][C:5]>>[N:3][H].[O:4][C:5]",
    },
    {
        "id": "nitrile_hydrolysis",
        "name": "Nitrile Hydrolysis",
        "class": "hydrolysis",
        "smarts": "[C:1]#[N:2]>>[C:1](=[O])[N:2]([H])[H]",
    },
]


def get_environmental_rules(sources: List[str] = None) -> List[Dict[str, Any]]:
    """Return compiled reaction SMIRKS for selected source classes."""
    if not sources:
        sources = ["soil_microbial", "photolysis", "hydrolysis"]

    compiled_rules = []
    for r in ENVIRONMENTAL_SMIRKS_RULES:
        if r["class"] in sources:
            try:
                rxn = AllChem.ReactionFromSmarts(r["smarts"])
                compiled_rules.append({
                    "id": r["id"],
                    "name": r["name"],
                    "class": r["class"],
                    "rxn": rxn
                })
            except Exception:
                continue

    return compiled_rules
