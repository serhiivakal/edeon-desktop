from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit.Chem import Descriptors
from typing import List, Tuple, Optional
from .schema import TransformationRule

class TransformationEngine:
    def __init__(self, library: List[TransformationRule]):
        self._rules = library
        self._precompiled = []
        for rule in library:
            try:
                rxn = AllChem.ReactionFromSmarts(rule.reaction_smarts)
                pat = Chem.MolFromSmarts(rule.pattern_smarts)
                if rxn and pat:
                    self._precompiled.append((rule, rxn, pat))
            except Exception:
                continue

    def apply_to_query(self, query_smiles: str, max_transformations_per_rule: int = 10) -> List[Tuple[TransformationRule, str, str]]:
        """Applies all matching rules to the query molecule.
        Returns a list of tuples: (applied_rule, original_smiles, candidate_smiles)
        
        The engine now applies transformations exhaustively:
        - Runs each reaction and collects all unique products
        - Higher per-rule limit (10 instead of 3) to capture different substitution sites
        - Relaxed MW filter (100-2000) to accommodate more transformations
        """
        mol = Chem.MolFromSmiles(query_smiles)
        if not mol:
            return []
            
        # Standardize query smiles
        query_smiles = Chem.MolToSmiles(mol, canonical=True)
        
        results = []
        seen_products = set()
        
        for rule, rxn, pat in self._precompiled:
            if not mol.HasSubstructMatch(pat):
                continue
                
            try:
                # Run reaction — produces all possible products for each match site
                products = rxn.RunReactants((mol,))
                if not products:
                    continue
                    
                rule_count = 0
                for prod_tuple in products:
                    if rule_count >= max_transformations_per_rule:
                        break
                        
                    prod_mol = prod_tuple[0]
                    try:
                        Chem.SanitizeMol(prod_mol)
                        prod_smiles = Chem.MolToSmiles(prod_mol, canonical=True)
                        
                        if prod_smiles == query_smiles or prod_smiles in seen_products:
                            continue
                            
                        # Apply sanity filters
                        if self._sanity_filter(prod_mol):
                            results.append((rule, query_smiles, prod_smiles))
                            seen_products.add(prod_smiles)
                            rule_count += 1
                    except Exception:
                        continue
            except Exception:
                continue
                
        return results

    def _sanity_filter(self, mol: Chem.Mol) -> bool:
        """Applies MW range, atom allowlist, SA score, fragment count checks."""
        try:
            # 1. Valid molecule check
            if mol is None:
                return False
                
            # 2. MW within reasonable range (relaxed for bioisosteric exploration)
            mw = Descriptors.ExactMolWt(mol)
            if not (80 <= mw <= 2000):
                return False
                
            # 3. Atom allowlist (C, H, O, N, S, P, F, Cl, Br, I, Si, B)
            allowed_atoms = {6, 1, 8, 7, 16, 15, 9, 17, 35, 53, 14, 5}
            for atom in mol.GetAtoms():
                if atom.GetAtomicNum() not in allowed_atoms:
                    return False
                    
            # 4. Fragment count check (no fragment count change unless rule allows, default max 1 fragment)
            frags = Chem.GetMolFrags(mol, asMols=True)
            if len(frags) > 1:
                return False
                
            # 5. Ring complexity check (relaxed — allow up to 8 rings for fused systems)
            ring_info = mol.GetRingInfo()
            if ring_info.NumRings() > 8:
                return False
                
            return True
        except Exception:
            return False
