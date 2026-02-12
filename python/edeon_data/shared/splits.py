import numpy as np
import pandas as pd
from typing import Tuple, Dict, Optional
from collections import defaultdict
from rdkit import Chem
from rdkit.Chem import AllChem, DataStructs
from rdkit.Chem.Scaffolds import MurckoScaffold
from sklearn.model_selection import train_test_split

def bemis_murcko_scaffold(smiles: str) -> str:
    """Computes the Bemis-Murcko scaffold for a SMILES string."""
    if not isinstance(smiles, str) or not smiles.strip():
        return ""
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return ""
        scaffold = MurckoScaffold.GetScaffoldForMol(mol)
        if scaffold is None:
            return ""
        return Chem.MolToSmiles(scaffold, canonical=True)
    except Exception:
        return ""


def calculate_scaffold_tightness(train_smiles: list, test_smiles: list) -> float:
    """
    Computes the mean Tanimoto similarity of each test compound to its nearest training compound
    using Morgan fingerprints (radius=2, 2048 bits).
    """
    if not train_smiles or not test_smiles:
        return 0.0
        
    train_fps = []
    for s in train_smiles:
        try:
            mol = Chem.MolFromSmiles(s)
            if mol:
                fp = AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=2048)
                train_fps.append(fp)
        except Exception:
            pass
            
    if not train_fps:
        return 0.0
        
    test_fps = []
    for s in test_smiles:
        try:
            mol = Chem.MolFromSmiles(s)
            if mol:
                fp = AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=2048)
                test_fps.append(fp)
        except Exception:
            pass
            
    if not test_fps:
        return 0.0
        
    similarities = []
    for tfp in test_fps:
        sims = DataStructs.BulkTanimotoSimilarity(tfp, train_fps)
        if sims:
            similarities.append(max(sims))
            
    return float(np.mean(similarities)) if similarities else 0.0


def check_leakage(train: pd.DataFrame, cal: pd.DataFrame, test: pd.DataFrame, key_col: str = "inchikey") -> None:
    """Verifies no overlap of the key column across the three splits, otherwise raises ValueError."""
    train_keys = set(train[key_col].dropna())
    cal_keys = set(cal[key_col].dropna())
    test_keys = set(test[key_col].dropna())
    
    overlap_train_cal = train_keys & cal_keys
    overlap_train_test = train_keys & test_keys
    overlap_cal_test = cal_keys & test_keys
    
    if overlap_train_cal or overlap_train_test or overlap_cal_test:
        reasons = []
        if overlap_train_cal:
            reasons.append(f"train-cal leakage ({len(overlap_train_cal)} keys)")
        if overlap_train_test:
            reasons.append(f"train-test leakage ({len(overlap_train_test)} keys)")
        if overlap_cal_test:
            reasons.append(f"cal-test leakage ({len(overlap_cal_test)} keys)")
        raise ValueError(f"Data leakage detected! {'; '.join(reasons)}")


def scaffold_split(
    df: pd.DataFrame,
    smiles_col: str = "smiles_canonical",
    ratios: Tuple[float, float, float] = (0.7, 0.15, 0.15),
    seed: int = 42
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """
    Groups compounds by Bemis-Murcko scaffold. Sorts scaffolds descending by group size
    (largest groups to train, singletons/smallest to test).
    """
    if len(df) == 0:
        return df.copy(), df.copy(), df.copy(), {}
        
    df_scaf = df.copy()
    # Compute scaffolds
    df_scaf["_scaffold"] = df_scaf[smiles_col].apply(bemis_murcko_scaffold)
    
    # Group by scaffold and sort groups by descending size
    scaffold_groups = df_scaf.groupby("_scaffold").groups
    sorted_scaffolds = sorted(scaffold_groups.keys(), key=lambda s: len(scaffold_groups[s]), reverse=True)
    
    total_size = len(df)
    train_target = ratios[0] * total_size
    cal_target = ratios[1] * total_size
    
    train_indices = []
    cal_indices = []
    test_indices = []
    
    for scaf in sorted_scaffolds:
        indices = list(scaffold_groups[scaf])
        if len(train_indices) < train_target:
            train_indices.extend(indices)
        elif len(cal_indices) < cal_target:
            cal_indices.extend(indices)
        else:
            test_indices.extend(indices)
            
    train_df = df_scaf.loc[train_indices].drop(columns=["_scaffold"]).reset_index(drop=True)
    cal_df = df_scaf.loc[cal_indices].drop(columns=["_scaffold"]).reset_index(drop=True)
    test_df = df_scaf.loc[test_indices].drop(columns=["_scaffold"]).reset_index(drop=True)
    
    # Leakage check
    check_leakage(train_df, cal_df, test_df)
    
    # Tightness metric
    tightness = calculate_scaffold_tightness(
        train_df[smiles_col].tolist(),
        test_df[smiles_col].tolist()
    )
    
    metadata = {
        "train": len(train_df),
        "cal": len(cal_df),
        "test": len(test_df),
        "test_to_train_nn_tanimoto_mean": tightness
    }
    
    return train_df, cal_df, test_df, metadata


def scaffold_split_by_group(
    df: pd.DataFrame,
    group_col: str,
    ratios: Tuple[float, float, float] = (0.7, 0.15, 0.15),
    seed: int = 42,
    smiles_col: str = "smiles_canonical"
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """
    Groups compounds by group_col (e.g. inchikey) first, then groups these groups by
    their Bemis-Murcko scaffold. Ensures all rows with the same group_col value
    land in the same split (train, cal, or test).
    """
    if len(df) == 0:
        return df.copy(), df.copy(), df.copy(), {}
        
    df_scaf = df.copy()
    
    # 1. Identify the scaffold for each unique group
    group_df = df_scaf.drop_duplicates(subset=[group_col])
    
    group_to_scaffold = {}
    for row in group_df.itertuples():
        grp = getattr(row, group_col)
        smi = getattr(row, smiles_col)
        group_to_scaffold[grp] = bemis_murcko_scaffold(smi)
        
    # Map scaffold -> list of groups
    scaffold_to_groups = defaultdict(list)
    for grp, scaf in group_to_scaffold.items():
        scaffold_to_groups[scaf].append(grp)
        
    # Map group -> list of original dataframe row indices
    group_to_indices = defaultdict(list)
    for idx, row in enumerate(df_scaf.itertuples()):
        grp = getattr(row, group_col)
        group_to_indices[grp].append(idx)
        
    # Sort scaffolds by the total number of rows they contain in descending order
    sorted_scaffolds = sorted(
        scaffold_to_groups.items(),
        key=lambda x: sum(len(group_to_indices[g]) for g in x[1]),
        reverse=True
    )
    
    total_size = len(df_scaf)
    train_target = ratios[0] * total_size
    cal_target = ratios[1] * total_size
    
    train_indices = []
    cal_indices = []
    test_indices = []
    
    for scaf, grps in sorted_scaffolds:
        scaf_indices = []
        for g in grps:
            scaf_indices.extend(group_to_indices[g])
            
        if len(train_indices) < train_target:
            train_indices.extend(scaf_indices)
        elif len(cal_indices) < cal_target:
            cal_indices.extend(scaf_indices)
        else:
            test_indices.extend(scaf_indices)
            
    train_df = df_scaf.iloc[train_indices].reset_index(drop=True)
    cal_df = df_scaf.iloc[cal_indices].reset_index(drop=True)
    test_df = df_scaf.iloc[test_indices].reset_index(drop=True)
    
    # Leakage check
    check_leakage(train_df, cal_df, test_df, key_col=group_col)
    
    # Tightness metric
    tightness = calculate_scaffold_tightness(
        train_df[smiles_col].tolist(),
        test_df[smiles_col].tolist()
    )
    
    metadata = {
        "train": len(train_df),
        "cal": len(cal_df),
        "test": len(test_df),
        "test_to_train_nn_tanimoto_mean": tightness
    }
    
    return train_df, cal_df, test_df, metadata


def random_split(
    df: pd.DataFrame,
    value_col: str,
    classification: bool = False,
    ratios: Tuple[float, float, float] = (0.7, 0.15, 0.15),
    seed: int = 42
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """
    Standard random split stratified by target.
    For classification, stratifies by value_col.
    For regression, stratifies by binned value_col (10 quantile bins).
    """
    if len(df) == 0:
        return df.copy(), df.copy(), df.copy(), {}
        
    df_split = df.copy()
    
    # Generate stratify column
    stratify_col = None
    if classification:
        if value_col in df_split.columns and df_split[value_col].notna().any():
            stratify_col = df_split[value_col].astype(str)
    else:
        if value_col in df_split.columns and df_split[value_col].notna().any():
            try:
                # Bin regression target into 10 quantile bins
                stratify_col = pd.qcut(df_split[value_col], q=10, labels=False, duplicates="drop")
            except Exception:
                pass

    try:
        # First split train vs temp (30% remaining)
        train_df, temp_df = train_test_split(
            df_split,
            test_size=(ratios[1] + ratios[2]),
            random_state=seed,
            stratify=stratify_col
        )
        
        # Then split temp into cal vs test (50% each of temp)
        temp_stratify = None
        if stratify_col is not None:
            temp_stratify = stratify_col.loc[temp_df.index]
            
        cal_df, test_df = train_test_split(
            temp_df,
            test_size=(ratios[2] / (ratios[1] + ratios[2])),
            random_state=seed,
            stratify=temp_stratify
        )
    except Exception:
        # Fallback to unstratified split in case of class imbalance or too few samples per bin
        train_df, temp_df = train_test_split(
            df_split,
            test_size=(ratios[1] + ratios[2]),
            random_state=seed
        )
        cal_df, test_df = train_test_split(
            temp_df,
            test_size=(ratios[2] / (ratios[1] + ratios[2])),
            random_state=seed
        )
        
    train_df = train_df.reset_index(drop=True)
    cal_df = cal_df.reset_index(drop=True)
    test_df = test_df.reset_index(drop=True)
    
    check_leakage(train_df, cal_df, test_df)
    
    metadata = {
        "train": len(train_df),
        "cal": len(cal_df),
        "test": len(test_df),
        "seed": seed
    }
    
    return train_df, cal_df, test_df, metadata


def time_split(
    df: pd.DataFrame,
    year_col: str = "year_reported",
    ratios: Tuple[float, float, float] = (0.7, 0.15, 0.15)
) -> Optional[Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]]:
    """
    Sorts by year ascending. Assigns first 70% to train, next 15% to cal, last 15% to test.
    If a year boundary falls inside a partition, assigns all records from that year to the earlier partition.
    Returns None if year metadata is too sparse (defined as < 50% non-null).
    """
    total_count = len(df)
    if total_count == 0:
        return df.copy(), df.copy(), df.copy(), {"status": "not_available"}
        
    non_null_years = df[year_col].dropna()
    if len(non_null_years) < 0.5 * total_count:
        return None
        
    # We will split the entire dataset. Let's place records with missing years in train.
    # The valid years will be sorted and split.
    df_valid = df[df[year_col].notna()].copy()
    df_missing = df[df[year_col].isna()].copy()
    
    # Sort valid records by year
    df_valid = df_valid.sort_values(by=year_col).reset_index(drop=True)
    
    # Unique years sorted
    unique_years = sorted(df_valid[year_col].unique())
    year_counts = df_valid[year_col].value_counts().to_dict()
    
    total_valid = len(df_valid)
    train_target = ratios[0] * total_valid
    cal_target = ratios[1] * total_valid
    
    train_years = []
    cal_years = []
    test_years = []
    
    current_cum = 0
    for yr in unique_years:
        count = year_counts[yr]
        next_cum = current_cum + count
        
        # If adding this year crosses the 70% threshold, assign it to train (earlier partition)
        if current_cum < train_target:
            train_years.append(yr)
        # If adding this year crosses the 85% threshold, assign it to cal (earlier partition)
        elif current_cum < (train_target + cal_target):
            cal_years.append(yr)
        else:
            test_years.append(yr)
            
        current_cum = next_cum
        
    train_valid = df_valid[df_valid[year_col].isin(train_years)]
    cal_valid = df_valid[df_valid[year_col].isin(cal_years)]
    test_valid = df_valid[df_valid[year_col].isin(test_years)]
    
    # Place missing years in train
    train_df = pd.concat([df_missing, train_valid], ignore_index=True)
    cal_df = cal_valid.reset_index(drop=True)
    test_df = test_valid.reset_index(drop=True)
    
    check_leakage(train_df, cal_df, test_df)
    
    metadata = {
        "train": len(train_df),
        "cal": len(cal_df),
        "test": len(test_df),
        "train_year_max": int(max(train_years)) if train_years else None,
        "cal_year_range": [int(min(cal_years)), int(max(cal_years))] if cal_years else None,
        "test_year_range": [int(min(test_years)), int(max(test_years))] if test_years else None
    }
    
    return train_df, cal_df, test_df, metadata
