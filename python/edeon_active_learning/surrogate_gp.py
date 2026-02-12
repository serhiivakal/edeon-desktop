"""
Edeon Active Learning — Gaussian Process Surrogate Model Solver
"""

from typing import List, Dict, Any, Tuple
import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel as C


def smiles_to_fps(smiles_list: List[str], n_bits: int = 1024) -> Tuple[np.ndarray, List[int]]:
    """Convert SMILES list to Morgan fingerprint matrix."""
    valid_idx = []
    fp_list = []

    for idx, smi in enumerate(smiles_list):
        m = Chem.MolFromSmiles(smi)
        if m:
            fp = AllChem.GetMorganFingerprintAsBitVect(m, 2, nBits=n_bits)
            fp_list.append(list(fp))
            valid_idx.append(idx)

    if not fp_list:
        return np.zeros((0, n_bits)), []

    return np.array(fp_list, dtype=np.float32), valid_idx


def fit_gp_surrogate(
    train_smiles: List[str],
    train_y: List[float],
    candidate_smiles: List[str]
) -> Tuple[np.ndarray, np.ndarray, float]:
    """Fit a Gaussian Process model on train_smiles and predict (mean, std_dev) on candidate_smiles.

    Returns:
        Tuple of (means, std_devs, R2_train_score).
    """
    X_train, valid_tr_idx = smiles_to_fps(train_smiles)
    X_cand, valid_cand_idx = smiles_to_fps(candidate_smiles)

    if len(valid_tr_idx) < 2 or len(valid_cand_idx) == 0:
        return np.zeros(len(candidate_smiles)), np.ones(len(candidate_smiles)), 0.0

    y_train = np.array([train_y[i] for i in valid_tr_idx], dtype=np.float32)

    # GP kernel setup
    kernel = C(1.0, (1e-3, 1e3)) * RBF(length_scale=10.0, length_scale_bounds=(1e-2, 1e2))
    gp = GaussianProcessRegressor(kernel=kernel, n_restarts_optimizer=2, alpha=1e-2, random_state=42)

    try:
        gp.fit(X_train, y_train)
        r2 = float(gp.score(X_train, y_train))
    except Exception:
        r2 = 0.0

    means, stds = gp.predict(X_cand, return_std=True)

    # Map back to full candidate_smiles length
    full_means = np.zeros(len(candidate_smiles))
    full_stds = np.ones(len(candidate_smiles))

    for idx_in_valid, orig_idx in enumerate(valid_cand_idx):
        full_means[orig_idx] = float(means[idx_in_valid])
        full_stds[orig_idx] = float(stds[idx_in_valid])

    return full_means, full_stds, max(0.0, min(1.0, r2))
