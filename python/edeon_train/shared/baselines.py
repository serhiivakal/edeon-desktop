"""Baseline training and HPO module for Edeon Phase 2.

Implements Random Forest and XGBoost baseline training with Optuna HPO
using greedy, scaffold-grouped cross-validation.
"""

import os
import json
import logging
import pickle
import numpy as np
import optuna
from typing import Dict, Any, List, Tuple, Literal
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.base import BaseEstimator
from sklearn.metrics import root_mean_squared_error, balanced_accuracy_score
from xgboost import XGBRegressor, XGBClassifier
from rdkit import Chem
from rdkit.Chem.Scaffolds import MurckoScaffold
from collections import defaultdict

logger = logging.getLogger("edeon_train.baselines")

# Silence optuna logs to avoid cluttering output
optuna.logging.set_verbosity(optuna.logging.WARNING)

def get_scaffold(smiles: str) -> str:
    """Extracts Bemis-Murcko scaffold Smiles for a given SMILES string."""
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return "__invalid__"
        sc = MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=False)
        return sc if sc else "__empty__"
    except Exception:
        return "__invalid__"

class ScaffoldKFold:
    """K-Fold cross-validator that splits compounds by Bemis-Murcko scaffold.
    
    Ensures that all compounds sharing a scaffold are placed in the same fold
    and folds have roughly equal size.
    """
    def __init__(self, n_splits: int = 5, random_state: int = 42):
        self.n_splits = n_splits
        self.random_state = random_state

    def split(self, X: np.ndarray, y: np.ndarray = None, smiles: List[str] = None, groups: List[str] = None):
        if smiles is None:
            raise ValueError("SMILES list must be provided for ScaffoldKFold")
            
        scaffold_to_indices = defaultdict(list)
        
        if groups is not None:
            # Group-level splitting (e.g. by InChIKey for multi-record datasets)
            # Find scaffold for each group first
            group_to_scaffold = {}
            group_to_indices = defaultdict(list)
            for i, (s, g) in enumerate(zip(smiles, groups)):
                group_to_indices[g].append(i)
                if g not in group_to_scaffold:
                    group_to_scaffold[g] = get_scaffold(s)
            
            scaffold_to_groups = defaultdict(list)
            for g, sc in group_to_scaffold.items():
                scaffold_to_groups[sc].append(g)
                
            sorted_scaffolds = sorted(scaffold_to_groups.items(), key=lambda x: sum(len(group_to_indices[g]) for g in x[1]), reverse=True)
            
            folds = [[] for _ in range(self.n_splits)]
            fold_sizes = [0] * self.n_splits
            
            for sc, grps in sorted_scaffolds:
                min_fold_idx = np.argmin(fold_sizes)
                for g in grps:
                    indices = group_to_indices[g]
                    folds[min_fold_idx].extend(indices)
                    fold_sizes[min_fold_idx] += len(indices)
        else:
            for i, s in enumerate(smiles):
                sc = get_scaffold(s)
                scaffold_to_indices[sc].append(i)
                
            # Sort groups by size for greedy assignment (largest first)
            sorted_groups = sorted(scaffold_to_indices.items(), key=lambda x: len(x[1]), reverse=True)
            
            # Greedy assignment to folds to keep them balanced
            folds = [[] for _ in range(self.n_splits)]
            fold_sizes = [0] * self.n_splits
            
            for sc, indices in sorted_groups:
                # Find the fold with the smallest current size
                min_fold_idx = np.argmin(fold_sizes)
                folds[min_fold_idx].extend(indices)
                fold_sizes[min_fold_idx] += len(indices)
            
        for val_fold_idx in range(self.n_splits):
            val_idx = folds[val_fold_idx]
            train_idx = []
            for f_idx in range(self.n_splits):
                if f_idx != val_fold_idx:
                    train_idx.extend(folds[f_idx])
            yield np.array(train_idx), np.array(val_idx)

def train_baseline_with_hpo(
    X_train: np.ndarray,
    y_train: np.ndarray,
    smiles_train: List[str],
    model_type: Literal["rf", "xgb"],
    task_kind: Literal["regression", "classification"] = "regression",
    n_trials: int = 50,
    cv_folds: int = 5,
    random_state: int = 42
) -> Tuple[BaseEstimator, Dict[str, Any]]:
    """Performs HPO via Optuna with scaffold-stratified CV on train partition,
    then refits best model on full training partition.
    
    For regression, minimizes RMSE. For classification, maximizes balanced accuracy.
    
    Returns:
        Tuple of (fitted_best_model, HPO_metadata_dict)
    """
    logger.info(f"Starting HPO for model type: {model_type} ({task_kind}, {n_trials} trials, {cv_folds}-fold Scaffold CV)")
    
    # Exclude invalid compounds (NaN features or target)
    valid_mask = ~np.isnan(X_train).any(axis=1) & ~np.isnan(y_train)
    X_valid = X_train[valid_mask]
    y_valid = y_train[valid_mask]
    smiles_valid = [smiles_train[i] for i, v in enumerate(valid_mask) if v]
    
    if len(X_valid) == 0:
        raise ValueError("No valid compounds in training set after dropping NaNs!")
        
    def objective(trial: optuna.Trial) -> float:
        # Define hyperparameter suggestions
        if model_type == "rf":
            params = {
                "n_estimators": trial.suggest_int("n_estimators", 100, 500),
                "max_depth": trial.suggest_int("max_depth", 5, 30),
                "min_samples_leaf": trial.suggest_int("min_samples_leaf", 1, 10),
                "min_samples_split": trial.suggest_int("min_samples_split", 2, 20),
                "max_features": trial.suggest_categorical("max_features", ["sqrt", "log2", 0.3, 0.5]),
                "random_state": random_state,
                "n_jobs": -1
            }
            if task_kind == "classification":
                params["class_weight"] = trial.suggest_categorical("class_weight", ["balanced", "balanced_subsample", None])
        else:  # xgb
            params = {
                "n_estimators": trial.suggest_int("n_estimators", 100, 1000),
                "max_depth": trial.suggest_int("max_depth", 3, 12),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
                "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
                "subsample": trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
                "random_state": random_state,
                "n_jobs": -1
            }
            if task_kind == "classification":
                # Compute scale_pos_weight from training data
                n_pos = int(y_valid.sum())
                n_neg = len(y_valid) - n_pos
                params["scale_pos_weight"] = n_neg / max(n_pos, 1)
            
        # Evaluate using ScaffoldKFold
        kf = ScaffoldKFold(n_splits=cv_folds, random_state=random_state)
        fold_scores = []
        
        for train_idx, val_idx in kf.split(X_valid, y_valid, smiles_valid):
            X_tr, y_tr = X_valid[train_idx], y_valid[train_idx]
            X_va, y_va = X_valid[val_idx], y_valid[val_idx]
            
            if task_kind == "classification":
                if model_type == "rf":
                    model = RandomForestClassifier(**params)
                else:
                    model = XGBClassifier(**params, use_label_encoder=False, eval_metric="logloss")
            else:
                if model_type == "rf":
                    model = RandomForestRegressor(**params)
                else:
                    model = XGBRegressor(**params)
                
            model.fit(X_tr, y_tr)
            
            if task_kind == "classification":
                preds = model.predict(X_va)
                score = balanced_accuracy_score(y_va, preds)
                fold_scores.append(score)
            else:
                preds = model.predict(X_va)
                rmse = root_mean_squared_error(y_va, preds)
                fold_scores.append(rmse)
            
        return float(np.mean(fold_scores))

    # Run HPO study — classification maximizes balanced accuracy, regression minimizes RMSE
    direction = "maximize" if task_kind == "classification" else "minimize"
    study = optuna.create_study(direction=direction)
    study.optimize(objective, n_trials=n_trials)
    
    best_params = study.best_params
    best_value = study.best_value
    metric_name = "Balanced Accuracy" if task_kind == "classification" else "CV RMSE"
    logger.info(f"HPO Completed for {model_type}. Best {metric_name}: {best_value:.4f}")
    logger.info(f"Best parameters: {best_params}")
    
    # Refit best model on full training set
    if task_kind == "classification":
        if model_type == "rf":
            best_model = RandomForestClassifier(**best_params, random_state=random_state, n_jobs=-1)
        else:
            # Remove scale_pos_weight if it was in the original params but not in best_params from trial
            refit_params = {k: v for k, v in best_params.items()}
            n_pos = int(y_valid.sum())
            n_neg = len(y_valid) - n_pos
            refit_params["scale_pos_weight"] = n_neg / max(n_pos, 1)
            best_model = XGBClassifier(**refit_params, random_state=random_state, n_jobs=-1,
                                       use_label_encoder=False, eval_metric="logloss")
    else:
        if model_type == "rf":
            best_model = RandomForestRegressor(**best_params, random_state=random_state, n_jobs=-1)
        else:
            best_model = XGBRegressor(**best_params, random_state=random_state, n_jobs=-1)
        
    best_model.fit(X_valid, y_valid)
    
    metadata = {
        "model_type": model_type,
        "task_kind": task_kind,
        "best_cv_score": best_value,
        "best_cv_rmse": best_value if task_kind == "regression" else None,
        "best_cv_balanced_accuracy": best_value if task_kind == "classification" else None,
        "best_params": best_params,
        "n_trials": n_trials,
        "cv_folds": cv_folds,
        "trials_history": [
            {"trial_num": t.number, "value": t.value, "params": t.params}
            for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE
        ]
    }
    
    return best_model, metadata

def save_baseline_checkpoint(
    model: BaseEstimator,
    metadata: Dict[str, Any],
    checkpoint_dir: str
) -> None:
    """Saves the fitted model pickle and HPO metadata JSON sidecar."""
    os.makedirs(checkpoint_dir, exist_ok=True)
    
    model_type = metadata["model_type"]
    model_path = os.path.join(checkpoint_dir, f"{model_type}.pkl")
    json_path = os.path.join(checkpoint_dir, f"{model_type}_hpo_results.json")
    
    with open(model_path, "wb") as f:
        pickle.dump(model, f, protocol=4)
        
    with open(json_path, "w") as f:
        json.dump(metadata, f, indent=2)
        
    logger.info(f"Saved {model_type} checkpoint and HPO sidecar to {checkpoint_dir}")

def load_baseline_checkpoint(checkpoint_dir: str, model_type: Literal["rf", "xgb"]) -> Tuple[BaseEstimator, Dict[str, Any]]:
    """Loads a baseline model and its corresponding metadata sidecar."""
    model_path = os.path.join(checkpoint_dir, f"{model_type}.pkl")
    json_path = os.path.join(checkpoint_dir, f"{model_type}_hpo_results.json")
    
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Checkpoint not found: {model_path}")
        
    with open(model_path, "rb") as f:
        model = pickle.load(f)
        
    with open(json_path, "r") as f:
        metadata = json.load(f)
        
    return model, metadata
