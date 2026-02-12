from typing import Optional, Tuple, Set, List
import pandas as pd
from rdkit import Chem
from rdkit.Chem import Descriptors
from rdkit.Chem.MolStandardize import rdMolStandardize
from chembl_structure_pipeline import standardizer

ATOM_ALLOWLIST_DEFAULT = {"H", "B", "C", "N", "O", "F", "Si", "P", "S", "Cl", "Se", "Br", "I"}
METAL_ALLOWLIST_AGRO = {"Cu", "Zn", "Mn", "Sn", "Hg"}  # used by some legacy pesticides

def standardize_smiles(
    smiles: str,
    atom_allowlist: Set[str] = None,
    mw_min: float = 50.0,
    mw_max: float = 1500.0,
    canonicalize_tautomer: bool = True,
) -> Tuple[Optional[str], Optional[str], List[str]]:
    """
    Returns (canonical_smiles, inchikey, flags) where flags is a list of
    quality flags. If the structure is rejected, returns (None, None, [reason]).
    """
    if not isinstance(smiles, str) or not smiles.strip():
        return None, None, ["empty_smiles"]

    flags = []
    
    # 1. SMILES parsing
    try:
        mol = Chem.MolFromSmiles(smiles, sanitize=True)
        if mol is None:
            return None, None, ["parse_failed"]
    except Exception as e:
        return None, None, [f"parse_failed:{e.__class__.__name__}"]

    # 1.5. RDKit FragmentParent pre-strip to ensure charged salt stripping (e.g. Na+) works perfectly
    try:
        mol = rdMolStandardize.FragmentParent(mol)
    except Exception as e:
        pass

    # 2. ChEMBL pipeline
    try:
        mol_std = standardizer.standardize_mol(mol)
        parent_res = standardizer.get_parent_mol(mol_std)
        if not parent_res or len(parent_res) == 0:
            return None, None, ["chembl_pipeline_failed:no_parent"]
        mol_parent = parent_res[0]
    except Exception as e:
        return None, None, [f"chembl_pipeline_failed:{e.__class__.__name__}"]

    # 3. Atom allowlist
    try:
        atoms = {a.GetSymbol() for a in mol_parent.GetAtoms()}
    except Exception as e:
        return None, None, [f"atom_extraction_failed:{e.__class__.__name__}"]
        
    allowed = atom_allowlist if atom_allowlist is not None else ATOM_ALLOWLIST_DEFAULT
    disallowed = atoms - allowed
    if disallowed:
        return None, None, [f"disallowed_atoms:{','.join(sorted(disallowed))}"]

    # 4. MW range
    try:
        mw = Descriptors.ExactMolWt(mol_parent)
    except Exception as e:
        return None, None, [f"mw_calculation_failed:{e.__class__.__name__}"]
        
    if mw < mw_min or mw > mw_max:
        return None, None, [f"mw_out_of_range:{mw:.1f}"]

    # 5. Tautomer canonicalisation
    if canonicalize_tautomer:
        try:
            enumerator = rdMolStandardize.TautomerEnumerator()
            mol_parent = enumerator.Canonicalize(mol_parent)
        except Exception:
            flags.append("tautomer_canonicalization_failed")

    # 6. InChIKey & Canonical SMILES generation
    try:
        smi = Chem.MolToSmiles(mol_parent, canonical=True, isomericSmiles=True)
        ikey = Chem.MolToInchiKey(mol_parent)
        if not ikey:
            return None, None, ["inchikey_generation_failed"]
    except Exception as e:
        return None, None, [f"generation_failed:{e.__class__.__name__}"]

    return smi, ikey, flags


def standardize_dataframe(
    df: pd.DataFrame, 
    smiles_col: str,
    atom_allowlist: Set[str] = None,
    mw_min: float = 50.0,
    mw_max: float = 1500.0,
    canonicalize_tautomer: bool = True,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Processes a DataFrame's SMILES column and returns (curated_df, rejections_df).
    
    The curated_df will have new columns:
      - smiles_canonical
      - inchikey
      - quality_flags
    The rejections_df will have columns from df plus:
      - smiles_original (copied from the smiles_col)
      - stage
      - reason
    """
    curated_records = []
    rejection_records = []

    for idx, row in df.iterrows():
        smi = row[smiles_col]
        smi_str = str(smi) if pd.notna(smi) else ""
        
        smi_canon, ikey, flags = standardize_smiles(
            smi_str,
            atom_allowlist=atom_allowlist,
            mw_min=mw_min,
            mw_max=mw_max,
            canonicalize_tautomer=canonicalize_tautomer,
        )
        
        if smi_canon is None:
            # It was rejected. Let's analyze the reason to find stage and reason
            reason_str = flags[0] if flags else "unknown_reason"
            stage = "parse"
            if "chembl" in reason_str:
                stage = "chembl_pipeline"
            elif "disallowed_atoms" in reason_str:
                stage = "atom_filter"
            elif "mw_out_of_range" in reason_str:
                stage = "size_filter"
            elif "generation_failed" in reason_str:
                stage = "generation"
            elif "empty_smiles" in reason_str:
                stage = "parse"
                
            rej_row = row.copy()
            rej_row["smiles_original"] = smi_str
            rej_row["stage"] = stage
            rej_row["reason"] = reason_str
            rejection_records.append(rej_row)
        else:
            cur_row = row.copy()
            cur_row["smiles_canonical"] = smi_canon
            cur_row["inchikey"] = ikey
            cur_row["quality_flags"] = flags
            curated_records.append(cur_row)

    if curated_records:
        curated_df = pd.DataFrame(curated_records).reset_index(drop=True)
    else:
        # Create empty DataFrame with expected columns
        curated_df = pd.DataFrame(columns=list(df.columns) + ["smiles_canonical", "inchikey", "quality_flags"])

    if rejection_records:
        rejections_df = pd.DataFrame(rejection_records).reset_index(drop=True)
    else:
        rejections_df = pd.DataFrame(columns=list(df.columns) + ["smiles_original", "stage", "reason"])

    return curated_df, rejections_df
