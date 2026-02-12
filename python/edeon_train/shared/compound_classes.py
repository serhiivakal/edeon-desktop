"""Agrochemical compound class tagger for Edeon Phase 2.

Uses SMARTS-based substructure matching to label compounds with their major
agrochemical classes (insecticides, fungicides, herbicides) for audit breakdowns.
"""

import logging
from typing import List
from rdkit import Chem

logger = logging.getLogger("edeon_train.compound_classes")

# Standard SMARTS patterns for major agrochemistry functional classes.
# Note: These are intentionally approximate to classify compounds for per-class performance auditing.
COMPOUND_CLASS_SMARTS = {
    # Insecticides
    "neonicotinoid": "[C,N]=N[N+](=O)[O-]",  # Nitroguanidine/nitroimine group
    "organophosphate": "[P,p](=[O,S])([O,S])([O,S])[O,S]",  # Phosphate/thiophosphate ester
    "pyrethroid": "C1CC1(C(=O)O)",  # Cyclopropane carboxylate core
    "carbamate": "[N,n]-C(=O)-[O,o]",  # Carbamate core
    "diamide": "C(=O)N[c,C]C(=O)N",  # Anthranilic diamide core
    
    # Fungicides
    "triazole": "n1cncn1",  # 1,2,4-triazole ring
    "strobilurin": "C(=C/OC)C(=O)OC",  # Methoxyacrylate / methoxyiminoacetate
    "sdhi": "[C,c]-C(=O)N-[C,c]",  # Carboxamide/succinate dehydrogenase inhibitor link
    
    # Herbicides
    "sulfonylurea": "S(=O)(=O)NC(=O)N",  # Sulfonylurea bridge
    "phenoxyacid": "c1ccccc1OCC(=O)O",  # Phenoxyacetic acid core
    "imidazolinone": "C1(=NC(C(C)C)(C)C(=O)N1)",  # Imidazolinone heterocyclic ring
    "triazine": "n1cncnc1",  # Triazine heterocyclic ring
}

# Compile SMARTS patterns at import time for fast matching
COMPILED_SMARTS = {}
for name, smarts in COMPOUND_CLASS_SMARTS.items():
    pat = Chem.MolFromSmarts(smarts)
    if pat is not None:
        COMPILED_SMARTS[name] = pat
    else:
        logger.warning(f"Failed to compile SMARTS for class {name}: {smarts}")

def tag_compound_classes(smiles: str) -> List[str]:
    """Classifies a compound's SMILES string into its matching chemical classes.
    
    Args:
        smiles: Compound SMILES string.
        
    Returns:
        List of matched class names (e.g. ["triazole", "sdhi"]).
        If no class matches, returns ["unclassified"].
        Invalid SMILES return ["unclassified"].
    """
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return ["unclassified"]
            
        matched = []
        for name, pat in COMPILED_SMARTS.items():
            if mol.HasSubstructMatch(pat):
                matched.append(name)
                
        if not matched:
            return ["unclassified"]
            
        return matched
    except Exception as e:
        logger.debug(f"Failed to tag classes for SMILES {smiles}: {e}")
        return ["unclassified"]
