"""
Edeon Engine — Data Curation Pipeline
Implements canonicalisation, salt stripping, largest fragment chooser,
neutralisation, disallowed atoms checking, and duplicate aggregation logic.
"""

from rdkit import Chem
from rdkit.Chem import AllChem, SaltRemover
from rdkit.Chem.MolStandardize import rdMolStandardize
from collections import defaultdict
import statistics

ALLOWED_ATOMS = {"H", "B", "C", "N", "O", "F", "Si", "P", "S", "Cl", "Br", "I"}

def curate_dataset(smiles_list: list[str],
                   activities: list[float],
                   model_type: str  # 'regression' | 'classification'
                   ) -> dict:
    """
    Returns a CurationResult dict:
    {
      "smiles":           [str, ...],   # cleaned, canonical, deduplicated
      "activities":       [float, ...], # aggregated values aligned with smiles
      "original_indices": [[int,...]],  # which input rows produced each output row
      "report": {
        "n_input": int,
        "n_invalid": int,
        "n_salts_stripped": int,
        "n_neutralised": int,
        "n_disallowed_atoms": int,
        "n_duplicates_merged": int,
        "n_final": int,
        "warnings": [ {"level": "info|warn|error", "message": str, "smiles": str|None}, ... ],
        "duplicate_conflicts": [
            {"canonical_smiles": str,
             "values": [float,...],
             "resolution": "mean|majority",
             "resolved_value": float,
             "spread": float}   # max-min for regression, ratio for classification
        ]
      }
    }
    """
    n_input = len(smiles_list)
    n_invalid = 0
    n_salts_stripped = 0
    n_neutralised = 0
    n_disallowed_atoms = 0
    n_duplicates_merged = 0
    
    warnings = []
    
    remover = SaltRemover.SaltRemover()
    chooser = rdMolStandardize.LargestFragmentChooser()
    uncharger = rdMolStandardize.Uncharger()
    
    valid_compounds = []  # list of dict: {canonical_smiles, original_index, activity}
    
    for idx, (smiles, act) in enumerate(zip(smiles_list, activities)):
        # 1. Parse + canonicalise
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                n_invalid += 1
                warnings.append({
                    "level": "error",
                    "message": f"Failed to parse SMILES structure: {smiles}",
                    "smiles": smiles
                })
                continue
        except Exception as e:
            n_invalid += 1
            warnings.append({
                "level": "error",
                "message": f"Exception during SMILES parsing: {str(e)}",
                "smiles": smiles
            })
            continue
            
        # 2. Salt strip
        try:
            num_atoms_before = mol.GetNumAtoms()
            stripped_mol = remover.StripMol(mol)
            if stripped_mol.GetNumAtoms() == 0:
                frags = Chem.GetMolFrags(mol, asMols=True)
                if frags:
                    frags = sorted(frags, key=lambda f: f.GetNumHeavyAtoms(), reverse=True)
                    if len(frags) > 1:
                        n_salts_stripped += 1
                    mol = frags[0]
            else:
                if stripped_mol.GetNumAtoms() < num_atoms_before:
                    n_salts_stripped += 1
                mol = stripped_mol
        except Exception as e:
            warnings.append({
                "level": "info",
                "message": f"Salt remover exception: {str(e)}",
                "smiles": smiles
            })
            
        # 3. Largest fragment
        try:
            largest_mol = chooser.choose(mol)
            if largest_mol is not None:
                mol = largest_mol
        except Exception as e:
            warnings.append({
                "level": "info",
                "message": f"Largest fragment chooser exception: {str(e)}",
                "smiles": smiles
            })
            
        # 4. Neutralisation
        try:
            smiles_before = Chem.MolToSmiles(mol)
            neutral_mol = uncharger.uncharge(mol)
            if neutral_mol is not None:
                smiles_after = Chem.MolToSmiles(neutral_mol)
                if smiles_before != smiles_after:
                    n_neutralised += 1
                mol = neutral_mol
        except Exception as e:
            warnings.append({
                "level": "info",
                "message": f"Uncharger exception: {str(e)}",
                "smiles": smiles
            })
            
        # 5. Disallowed atoms
        has_disallowed = False
        try:
            for atom in mol.GetAtoms():
                symbol = atom.GetSymbol()
                if symbol not in ALLOWED_ATOMS:
                    has_disallowed = True
                    n_disallowed_atoms += 1
                    warnings.append({
                        "level": "error",
                        "message": f"Compound dropped due to disallowed atom symbol: '{symbol}'",
                        "smiles": smiles
                    })
                    break
        except Exception as e:
            has_disallowed = True
            warnings.append({
                "level": "error",
                "message": f"Exception checking atoms symbols: {str(e)}",
                "smiles": smiles
            })
            
        if has_disallowed:
            continue
            
        # 6. Canonical SMILES
        try:
            canonical_smiles = Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)
            if not canonical_smiles:
                n_invalid += 1
                warnings.append({
                    "level": "error",
                    "message": "Generated empty canonical SMILES",
                    "smiles": smiles
                })
                continue
            
            valid_compounds.append({
                "canonical_smiles": canonical_smiles,
                "original_index": idx,
                "activity": float(act)
            })
        except Exception as e:
            n_invalid += 1
            warnings.append({
                "level": "error",
                "message": f"Failed to canonicalize molecule structure: {str(e)}",
                "smiles": smiles
            })
            continue
            
    # 7. Aggregate duplicates
    groups = defaultdict(list)
    for comp in valid_compounds:
        groups[comp["canonical_smiles"]].append((comp["original_index"], comp["activity"]))
        
    final_smiles = []
    final_activities = []
    final_original_indices = []
    
    duplicate_conflicts = []
    
    # Sort keys of dictionary to guarantee strict determinism (alphabetical sorted order)
    sorted_keys = sorted(groups.keys())
    
    for canonical_smiles in sorted_keys:
        items = groups[canonical_smiles]
        # Preserve input order of indices within groups
        items_sorted = sorted(items, key=lambda x: x[0])
        idxs = [x[0] for x in items_sorted]
        values = [x[1] for x in items_sorted]
        
        if len(items) == 1:
            final_smiles.append(canonical_smiles)
            final_activities.append(values[0])
            final_original_indices.append(idxs)
        else:
            n_duplicates_merged += (len(items) - 1)
            
            if model_type == "regression":
                resolved_value = sum(values) / len(values)
                spread = max(values) - min(values)
                
                if spread > 1.0:
                    warnings.append({
                        "level": "warn",
                        "message": f"High duplicate activity spread: {spread:.2f} log units",
                        "smiles": canonical_smiles
                    })
                    
                duplicate_conflicts.append({
                    "canonical_smiles": canonical_smiles,
                    "values": values,
                    "resolution": "mean",
                    "resolved_value": float(resolved_value),
                    "spread": float(spread)
                })
                
                final_smiles.append(canonical_smiles)
                final_activities.append(resolved_value)
                final_original_indices.append(idxs)
                
            else:  # classification
                int_values = [int(round(v)) for v in values]
                ones = sum(1 for v in int_values if v == 1)
                zeros = sum(1 for v in int_values if v == 0)
                
                if ones == zeros:
                    # Perfect tie: drop the compound entirely
                    warnings.append({
                        "level": "error",
                        "message": f"Tie in classification duplicate votes for {canonical_smiles}",
                        "smiles": canonical_smiles
                    })
                    # Report conflict details
                    duplicate_conflicts.append({
                        "canonical_smiles": canonical_smiles,
                        "values": values,
                        "resolution": "tie_dropped",
                        "resolved_value": -1.0,
                        "spread": 0.5
                    })
                else:
                    if ones > zeros:
                        resolved_value = 1.0
                        minority = zeros
                    else:
                        resolved_value = 0.0
                        minority = ones
                        
                    spread = float(minority) / len(values)
                    
                    duplicate_conflicts.append({
                        "canonical_smiles": canonical_smiles,
                        "values": values,
                        "resolution": "majority",
                        "resolved_value": float(resolved_value),
                        "spread": float(spread)
                    })
                    
                    final_smiles.append(canonical_smiles)
                    final_activities.append(resolved_value)
                    final_original_indices.append(idxs)
                    
    # Strict deterministic sorting of conflicts and warnings for byte-identical reports
    duplicate_conflicts.sort(key=lambda x: (-x["spread"], x["canonical_smiles"]))
    warnings.sort(key=lambda x: (x["level"], x["message"] or "", x["smiles"] or ""))
    
    n_final = len(final_smiles)
    
    # Calculate Activity Distribution Statistics & Warnings (Task 2)
    import numpy as np
    
    activity_stats = {
        "model_type": model_type
    }
    
    if len(final_activities) > 0:
        if model_type == "regression":
            acts = np.array(final_activities, dtype=float)
            vmin = float(np.min(acts))
            vmax = float(np.max(acts))
            vmean = float(np.mean(acts))
            vmedian = float(np.median(acts))
            q1 = float(np.percentile(acts, 25))
            q3 = float(np.percentile(acts, 75))
            iqr = q3 - q1
            vstd = float(np.std(acts))
            dynamic_range = vmax - vmin
            
            # Use 20 equal-width bins
            counts, bin_edges = np.histogram(acts, bins=20)
            bins_list = [float((bin_edges[i] + bin_edges[i+1]) / 2) for i in range(20)]
            counts_list = [int(c) for c in counts]
            
            activity_stats.update({
                "min": vmin,
                "max": vmax,
                "median": vmedian,
                "mean": vmean,
                "q1": q1,
                "q3": q3,
                "iqr": iqr,
                "std": vstd,
                "dynamic_range": dynamic_range,
                "histogram": {
                    "bins": bins_list,
                    "counts": counts_list
                },
                "range_warning": bool(dynamic_range < 2.0)
            })
        else:  # classification
            acts = [int(round(v)) for v in final_activities]
            count_0 = sum(1 for v in acts if v == 0)
            count_1 = sum(1 for v in acts if v == 1)
            
            majority = max(count_0, count_1)
            minority = min(count_0, count_1)
            
            imbalance_ratio = float(majority) / float(minority) if minority > 0 else float(majority)
            imbalance_warning = bool(imbalance_ratio > 3.0)
            
            imbalance_recommendation = None
            if imbalance_warning:
                imbalance_recommendation = "smote" if imbalance_ratio > 5.0 else "class_weight"
                
            activity_stats.update({
                "class_counts": {
                    "0": count_0,
                    "1": count_1
                },
                "imbalance_ratio": imbalance_ratio,
                "imbalance_warning": imbalance_warning,
                "imbalance_recommendation": imbalance_recommendation
            })
            
    return {
        "smiles": final_smiles,
        "activities": final_activities,
        "original_indices": final_original_indices,
        "report": {
            "n_input": int(n_input),
            "n_invalid": int(n_invalid),
            "n_salts_stripped": int(n_salts_stripped),
            "n_neutralised": int(n_neutralised),
            "n_disallowed_atoms": int(n_disallowed_atoms),
            "n_duplicates_merged": int(n_duplicates_merged),
            "n_final": int(n_final),
            "warnings": warnings,
            "duplicate_conflicts": duplicate_conflicts,
            "activity_stats": activity_stats
        }
    }
