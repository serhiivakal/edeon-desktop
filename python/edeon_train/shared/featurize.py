"""Featurization module for Edeon Phase 2 reference models.

Concatenates filtered RDKit 2D descriptors, Morgan fingerprints, and MACCS keys
to produce a high-dimensional compound representation for baseline models.
"""

import logging
import numpy as np
from typing import List, Dict, Tuple, Optional, Any
from rdkit import Chem
from rdkit.Chem import rdFingerprintGenerator, MACCSkeys, Descriptors

logger = logging.getLogger("edeon_train.featurize")

# Cache all available RDKit descriptors
ALL_DESCRIPTORS_DICT = {name: func for name, func in Descriptors._descList}

def compute_morgan_fps(smiles_list: List[str], radius: int = 2, n_bits: int = 2048) -> np.ndarray:
    """Computes Morgan (ECFP) fingerprints for a list of SMILES strings.
    
    Returns:
        np.ndarray of shape (n_compounds, n_bits). If a compound is invalid,
        returns a row of NaNs.
    """
    matrix = np.zeros((len(smiles_list), n_bits))
    gen = rdFingerprintGenerator.GetMorganGenerator(radius=radius, fpSize=n_bits)
    
    for i, smiles in enumerate(smiles_list):
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol is not None:
                matrix[i] = gen.GetFingerprintAsNumPy(mol)
            else:
                matrix[i] = np.nan
        except Exception as e:
            logger.debug(f"Failed to compute Morgan FP for SMILES {smiles}: {e}")
            matrix[i] = np.nan
            
    return matrix

def compute_maccs_fps(smiles_list: List[str]) -> np.ndarray:
    """Computes MACCS keys (167 bits) for a list of SMILES strings.
    
    Returns:
        np.ndarray of shape (n_compounds, 167). If a compound is invalid,
        returns a row of NaNs.
    """
    matrix = np.zeros((len(smiles_list), 167))
    
    for i, smiles in enumerate(smiles_list):
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol is not None:
                fp = MACCSkeys.GenMACCSKeys(mol)
                matrix[i] = np.array(list(fp))
            else:
                matrix[i] = np.nan
        except Exception as e:
            logger.debug(f"Failed to compute MACCS FP for SMILES {smiles}: {e}")
            matrix[i] = np.nan
            
    return matrix

def compute_rdkit_descriptors(smiles_list: List[str], descriptor_names: List[str]) -> np.ndarray:
    """Computes specified RDKit 2D descriptors for a list of SMILES strings.
    
    Returns:
        np.ndarray of shape (n_compounds, len(descriptor_names)). If a compound is invalid,
        returns a row of NaNs.
    """
    n_compounds = len(smiles_list)
    n_features = len(descriptor_names)
    matrix = np.zeros((n_compounds, n_features))
    
    for i, smiles in enumerate(smiles_list):
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol is not None:
                for j, name in enumerate(descriptor_names):
                    func = ALL_DESCRIPTORS_DICT.get(name)
                    if func is not None:
                        # Safety override for slow Ipc descriptor to prevent overflow/hang
                        if name == "Ipc":
                            val = func(mol, avg=True)
                        else:
                            val = func(mol)
                        matrix[i, j] = float(val) if val is not None else np.nan
                    else:
                        matrix[i, j] = np.nan
            else:
                matrix[i, :] = np.nan
        except Exception as e:
            logger.debug(f"Failed to compute descriptors for SMILES {smiles}: {e}")
            matrix[i, :] = np.nan
            
    return matrix

def select_uncorrelated_descriptors(smiles_list: List[str], threshold: float = 0.95) -> List[str]:
    """Fits a descriptor filter based on a list of SMILES (typically training set).
    
    Filters out descriptors that are constant, contain too many NaNs,
    or have pairwise Pearson correlation > threshold.
    
    Returns:
        List of selected (uncorrelated) descriptor names.
    """
    logger.info("Computing all available RDKit descriptors for correlation filtering...")
    # Exclude Ipc from raw computation or handle with avg=True
    all_names = list(ALL_DESCRIPTORS_DICT.keys())
    
    # Calculate descriptors
    X_raw = compute_rdkit_descriptors(smiles_list, all_names)
    
    # Drop rows with parse failures for variance/correlation calculation
    valid_mask = ~np.isnan(X_raw).any(axis=1)
    if not np.any(valid_mask):
        logger.warning("No valid compounds found for descriptor selection, falling back to Lipinski descriptors.")
        return ["MolWt", "MolLogP", "NumHDonors", "NumHAcceptors", "TPSA", "NumRotatableBonds"]
        
    X_valid = X_raw[valid_mask]
    
    # 1. Filter out constant columns
    variances = np.var(X_valid, axis=0)
    non_constant_indices = np.where(variances > 1e-6)[0]
    
    selected_indices = []
    
    # 2. Greedy correlation filtering
    # Order by name for determinism
    ordered_candidates = sorted(non_constant_indices, key=lambda idx: all_names[idx])
    
    for idx in ordered_candidates:
        col = X_valid[:, idx]
        # Check correlation with already selected columns
        is_correlated = False
        for sel_idx in selected_indices:
            sel_col = X_valid[:, sel_idx]
            r = np.corrcoef(col, sel_col)[0, 1]
            if np.isnan(r) or abs(r) > threshold:
                is_correlated = True
                break
        if not is_correlated:
            selected_indices.append(idx)
            
    selected_names = [all_names[idx] for idx in selected_indices]
    logger.info(f"Selected {len(selected_names)} / {len(all_names)} uncorrelated descriptors.")
    return selected_names

def featurize_for_baseline(
    smiles_list: List[str],
    descriptors_selected: List[str],
    morgan_radius: int = 2,
    morgan_nbits: int = 2048,
    ionizable_flags: Optional[List[int]] = None
) -> np.ndarray:
    """Concatenates selected RDKit 2D descriptors, Morgan FPs, MACCS keys, and optional ionizable flags.
    
    Args:
        smiles_list: List of SMILES strings.
        descriptors_selected: Pre-selected list of RDKit 2D descriptor names.
        morgan_radius: Radius for Morgan fingerprints.
        morgan_nbits: Number of bits for Morgan fingerprints.
        ionizable_flags: Optional list of binary flags (0 or 1) indicating if compound is ionizable.
        
    Returns:
        np.ndarray of shape (n_compounds, n_features) where
        n_features = len(descriptors_selected) + morgan_nbits + 167 (+ 1 if ionizable_flags provided).
        Invalid SMILES will have NaN rows.
    """
    if not smiles_list:
        extra_dim = 1 if ionizable_flags is not None else 0
        return np.zeros((0, len(descriptors_selected) + morgan_nbits + 167 + extra_dim))
        
    desc_matrix = compute_rdkit_descriptors(smiles_list, descriptors_selected)
    morgan_matrix = compute_morgan_fps(smiles_list, radius=morgan_radius, n_bits=morgan_nbits)
    maccs_matrix = compute_maccs_fps(smiles_list)
    
    # If any row is completely NaN in one matrix due to parse failure, ensure it's NaN in all
    nan_rows = np.isnan(desc_matrix).any(axis=1) | np.isnan(morgan_matrix).any(axis=1) | np.isnan(maccs_matrix).any(axis=1)
    
    # Concatenate features
    matrices = [desc_matrix, morgan_matrix, maccs_matrix]
    if ionizable_flags is not None:
        ion_matrix = np.array(ionizable_flags, dtype=float).reshape(-1, 1)
        matrices.append(ion_matrix)
        
    X = np.hstack(matrices)
    X[nan_rows, :] = np.nan
    
    return X

class FeatureRegistry:
    """Tracks feature configurations and column indices to ensure reproducibility at inference time."""
    
    def __init__(self, descriptors_selected: List[str], morgan_radius: int = 2, morgan_nbits: int = 2048):
        self.descriptors_selected = sorted(descriptors_selected)
        self.morgan_radius = morgan_radius
        self.morgan_nbits = morgan_nbits
        self.maccs_bits = 167
        
        # Build layout indices
        self.desc_slice = slice(0, len(self.descriptors_selected))
        self.morgan_slice = slice(len(self.descriptors_selected), len(self.descriptors_selected) + self.morgan_nbits)
        self.maccs_slice = slice(
            len(self.descriptors_selected) + self.morgan_nbits,
            len(self.descriptors_selected) + self.morgan_nbits + self.maccs_bits
        )
        
    def to_dict(self) -> Dict[str, Any]:
        """Serializes registry settings to a dictionary."""
        return {
            "descriptors_selected": self.descriptors_selected,
            "morgan_radius": self.morgan_radius,
            "morgan_nbits": self.morgan_nbits,
            "maccs_bits": self.maccs_bits,
        }
        
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FeatureRegistry":
        """Deserializes registry settings from a dictionary."""
        return cls(
            descriptors_selected=d["descriptors_selected"],
            morgan_radius=d.get("morgan_radius", 2),
            morgan_nbits=d.get("morgan_nbits", 2048)
        )
        
    def get_feature_names(self) -> List[str]:
        """Returns the list of all feature names in order of concatenation."""
        names = []
        names.extend(self.descriptors_selected)
        names.extend([f"morgan_{self.morgan_radius}:{i}" for i in range(self.morgan_nbits)])
        names.extend([f"maccs:{i}" for i in range(self.maccs_bits)])
        return names
