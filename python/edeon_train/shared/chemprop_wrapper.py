"""Chemprop D-MPNN ensemble wrapper for Edeon Phase 2.

Wrapper for training, predicting, and optimizing 5-seed D-MPNN ensembles
using Chemprop v2 and PyTorch Lightning.
"""

import os
import logging
import numpy as np
import torch
import lightning as L
import optuna
from typing import List, Dict, Any, Tuple, Optional
from rdkit import Chem
from chemprop.nn import BondMessagePassing, MeanAggregation, RegressionFFN, BinaryClassificationFFN, MveFFN, MVELoss
from chemprop.models import MPNN, save_model, load_model
from chemprop.data import MoleculeDataset, MoleculeDatapoint, build_dataloader
from edeon_train.shared.baselines import ScaffoldKFold
from sklearn.metrics import balanced_accuracy_score

logger = logging.getLogger("edeon_train.chemprop")

# Disable pytorch lightning logs to prevent clutter
logging.getLogger("lightning.pytorch").setLevel(logging.WARNING)

def train_chemprop_ensemble(
    train_smiles: List[str],
    train_y: np.ndarray,
    cal_smiles: List[str],
    cal_y: np.ndarray,
    config: Dict[str, Any],
    output_dir: str,
    seeds: List[int] = [0, 1, 2, 3, 4],
    task_kind: str = "regression",
    train_x_d: Optional[List[np.ndarray]] = None,
    cal_x_d: Optional[List[np.ndarray]] = None
) -> Dict[str, Any]:
    """Trains a 5-seed Chemprop D-MPNN ensemble.
    
    Args:
        train_smiles: List of training SMILES.
        train_y: np.ndarray of training targets.
        cal_smiles: List of calibration SMILES (used as early-stopping validation).
        cal_y: np.ndarray of calibration targets.
        config: Chemprop model configuration dictionary.
        output_dir: Directory where checkpoints will be saved.
        seeds: List of seeds to train.
        task_kind: 'regression' or 'classification'.
        train_x_d: Optional list of extra feature arrays for training compounds.
        cal_x_d: Optional list of extra feature arrays for calibration compounds.
        
    Returns:
        Dict containing training metadata and validation performance.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Filter out invalid SMILES/targets from training/calibration
    train_mols_valid = []
    train_y_valid = []
    train_x_d_valid = []
    for i, (s, y) in enumerate(zip(train_smiles, train_y)):
        if np.isnan(y):
            continue
        try:
            mol = Chem.MolFromSmiles(s)
            if mol is not None:
                train_mols_valid.append(mol)
                train_y_valid.append(y)
                if train_x_d is not None:
                    train_x_d_valid.append(train_x_d[i])
        except Exception:
            continue
            
    cal_mols_valid = []
    cal_y_valid = []
    cal_x_d_valid = []
    for i, (s, y) in enumerate(zip(cal_smiles, cal_y)):
        if np.isnan(y):
            continue
        try:
            mol = Chem.MolFromSmiles(s)
            if mol is not None:
                cal_mols_valid.append(mol)
                cal_y_valid.append(y)
                if cal_x_d is not None:
                    cal_x_d_valid.append(cal_x_d[i])
        except Exception:
            continue
            
    if not train_mols_valid or not cal_mols_valid:
        raise ValueError("No valid compounds in train/calibration sets for Chemprop!")
        
    logger.info(f"Training Chemprop ensemble ({len(seeds)} seeds) with config: {config}")
    
    # Build MoleculeDatasets
    if train_x_d is not None:
        train_dps = [
            MoleculeDatapoint(mol=m, y=np.array([y]), x_d=np.array([float(val)]) if isinstance(xd, (int, float, np.number)) else np.array(xd, dtype=float))
            for m, y, xd in zip(train_mols_valid, train_y_valid, train_x_d_valid)
        ]
    else:
        train_dps = [MoleculeDatapoint(mol=m, y=np.array([y])) for m, y in zip(train_mols_valid, train_y_valid)]
    train_ds = MoleculeDataset(train_dps)
    
    if cal_x_d is not None:
        cal_dps = [
            MoleculeDatapoint(mol=m, y=np.array([y]), x_d=np.array([float(val)]) if isinstance(xd, (int, float, np.number)) else np.array(xd, dtype=float))
            for m, y, xd in zip(cal_mols_valid, cal_y_valid, cal_x_d_valid)
        ]
    else:
        cal_dps = [MoleculeDatapoint(mol=m, y=np.array([y])) for m, y in zip(cal_mols_valid, cal_y_valid)]
    cal_ds = MoleculeDataset(cal_dps)
    
    batch_size = config.get("batch_size", 50)
    epochs = config.get("epochs", 50)
    
    # Determine accelerator
    accelerator = "gpu" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using Chemprop accelerator: {accelerator}")
    
    seed_val_losses = {}
    
    for seed in seeds:
        logger.info(f"--- Training Chemprop Seed {seed} ---")
        L.seed_everything(seed)
        torch.manual_seed(seed)
        
        # Build dataloaders
        train_dl = build_dataloader(train_ds, batch_size=batch_size, shuffle=True, seed=seed)
        cal_dl = build_dataloader(cal_ds, batch_size=batch_size, shuffle=False)
        
        # Instantiate model architecture
        hidden_size = config.get("hidden_size", 300)
        ffn_hidden_size = config.get("ffn_hidden_size", 300)
        
        extra_dim = 0
        if train_x_d is not None and len(train_x_d_valid) > 0:
            xd_sample = train_x_d_valid[0]
            extra_dim = 1 if isinstance(xd_sample, (int, float, np.number)) else len(xd_sample)
            
        input_dim = hidden_size + extra_dim
        
        mp = BondMessagePassing(
            d_h=hidden_size,
            depth=config.get("depth", 3),
            dropout=config.get("dropout", 0.0),
            activation=config.get("activation", "relu")
        )
        agg = MeanAggregation()
        
        if task_kind == "classification":
            predictor = BinaryClassificationFFN(
                input_dim=input_dim,
                hidden_dim=ffn_hidden_size,
                n_layers=config.get("ffn_num_layers", 2),
                dropout=config.get("dropout", 0.0),
                activation=config.get("activation", "relu")
            )
        else:
            predictor = RegressionFFN(
                input_dim=input_dim,
                hidden_dim=ffn_hidden_size,
                n_layers=config.get("ffn_num_layers", 2),
                dropout=config.get("dropout", 0.0),
                activation=config.get("activation", "relu")
            )
        
        model = MPNN(
            mp, 
            agg, 
            predictor,
            warmup_epochs=config.get("warmup_epochs", 2),
            init_lr=config.get("init_lr", 1e-4),
            max_lr=config.get("max_lr", 1e-3),
            final_lr=config.get("final_lr", 1e-4)
        )
        
        # Setup trainer
        # Use simple progress bar/logger disabling to avoid massive output logs
        trainer = L.Trainer(
            max_epochs=epochs,
            accelerator=accelerator,
            enable_checkpointing=False,
            logger=False,
            enable_progress_bar=False
        )
        
        trainer.fit(model, train_dl, cal_dl)
        
        # Save model
        model_path = os.path.join(output_dir, f"seed_{seed}.pt")
        save_model(model_path, model)
        
        # Evaluate validation loss for early confirmation
        val_preds_list = trainer.predict(model, cal_dl)
        val_preds = np.concatenate([p.numpy() for p in val_preds_list], axis=0).flatten()
        if task_kind == "classification":
            # For binary classification, Chemprop returns logits; apply sigmoid
            val_probs = 1.0 / (1.0 + np.exp(-val_preds))
            val_binary = (val_probs >= 0.5).astype(int)
            val_ba = float(balanced_accuracy_score(np.array(cal_y_valid), val_binary))
            seed_val_losses[seed] = val_ba
            logger.info(f"Seed {seed} completed. Validation Balanced Accuracy: {val_ba:.4f}")
        else:
            val_rmse = float(np.sqrt(np.mean((np.array(cal_y_valid) - val_preds) ** 2)))
            seed_val_losses[seed] = val_rmse
            logger.info(f"Seed {seed} completed. Validation RMSE: {val_rmse:.4f}")
        
    metadata = {
        "config": config,
        "seeds": seeds,
        "task_kind": task_kind,
        "seed_val_losses": seed_val_losses,
        "mean_val_rmse": float(np.mean(list(seed_val_losses.values()))) if task_kind == "regression" else None,
        "mean_val_balanced_accuracy": float(np.mean(list(seed_val_losses.values()))) if task_kind == "classification" else None,
        "mean_val_score": float(np.mean(list(seed_val_losses.values()))),
        "accelerator": accelerator
    }
    
    return metadata

def predict_chemprop_ensemble(
    smiles: List[str],
    checkpoint_dir: str,
    seeds: List[int] = [0, 1, 2, 3, 4],
    task_kind: str = "regression",
    x_d: Optional[List[np.ndarray]] = None
) -> Tuple[np.ndarray, np.ndarray]:
    """Computes arithmetic mean and standard deviation across the 5 ensemble seeds.
    
    Args:
        smiles: List of SMILES strings to predict.
        checkpoint_dir: Directory containing the seed_{seed}.pt files.
        seeds: List of seeds to include in prediction.
        task_kind: 'regression' or 'classification'. For classification, returns
                   (mean_probability, std_probability) after sigmoid.
        x_d: Optional list of extra feature arrays for query compounds.
        
    Returns:
        Tuple of (mean_predictions, std_predictions)
    """
    n_compounds = len(smiles)
    if n_compounds == 0:
        return np.zeros(0), np.zeros(0)
        
    # Map valid molecules, track parse failures
    valid_mols = []
    invalid_indices = []
    placeholder_mol = Chem.MolFromSmiles("C")
    
    for i, s in enumerate(smiles):
        try:
            mol = Chem.MolFromSmiles(s)
            if mol is not None:
                valid_mols.append((i, mol))
            else:
                invalid_indices.append(i)
                valid_mols.append((i, placeholder_mol))
        except Exception:
            invalid_indices.append(i)
            valid_mols.append((i, placeholder_mol))
            
    # Build MoleculeDataset with mols in original order
    if x_d is not None:
        dps = [
            MoleculeDatapoint(mol=m, x_d=np.array([float(val)]) if isinstance(x_d[idx], (int, float, np.number)) else np.array(x_d[idx], dtype=float))
            for idx, m in valid_mols
        ]
    else:
        dps = [MoleculeDatapoint(mol=m) for _, m in valid_mols]
    ds = MoleculeDataset(dps)
    
    # Predict using each seed model
    accelerator = "gpu" if torch.cuda.is_available() else "cpu"
    all_preds = []
    
    for seed in seeds:
        model_path = os.path.join(checkpoint_dir, f"seed_{seed}.pt")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Chemprop checkpoint not found for seed {seed} at {model_path}")
            
        model = load_model(model_path)
        dl = build_dataloader(ds, batch_size=64, shuffle=False)
        
        trainer = L.Trainer(
            accelerator=accelerator,
            logger=False,
            enable_checkpointing=False,
            enable_progress_bar=False
        )
        
        preds_list = trainer.predict(model, dl)
        preds = np.concatenate([p.numpy() for p in preds_list], axis=0).flatten()
        
        if task_kind == "classification":
            # Apply sigmoid to convert logits to probabilities
            preds = 1.0 / (1.0 + np.exp(-preds))
        
        all_preds.append(preds)
        
    all_preds = np.array(all_preds)  # Shape: (n_seeds, n_compounds)
    
    mean_preds = np.mean(all_preds, axis=0)
    std_preds = np.std(all_preds, axis=0)
    
    # Overwrite invalid SMILES with NaNs
    if invalid_indices:
        mean_preds[invalid_indices] = np.nan
        std_preds[invalid_indices] = np.nan
        
    return mean_preds, std_preds

def chemprop_hpo(
    train_smiles: List[str],
    train_y: np.ndarray,
    smiles_scaffolds: List[str],
    n_trials: int = 20,
    cv_folds: int = 3,
    random_state: int = 42,
    task_kind: str = "regression",
    train_x_d: Optional[List[np.ndarray]] = None
) -> Dict[str, Any]:
    """HPO for Chemprop hyperparameters over the train partition only.
    
    Optimizes {depth, hidden_size, dropout, ffn_num_layers} using Scaffold CV.
    For classification, maximizes balanced accuracy. For regression, minimizes RMSE.
    """
    logger.info(f"Starting Chemprop HPO ({task_kind}): {n_trials} trials, {cv_folds}-fold Scaffold CV")
    
    # Filter valid compounds
    valid_mask = ~np.isnan(train_y)
    train_y_valid = train_y[valid_mask]
    train_smiles_valid = [train_smiles[i] for i, v in enumerate(valid_mask) if v]
    
    # Keep only those that parse
    mols_valid = []
    y_valid = []
    smiles_clean = []
    train_x_d_valid = []
    
    for i, (s, y) in enumerate(zip(train_smiles_valid, train_y_valid)):
        try:
            mol = Chem.MolFromSmiles(s)
            if mol is not None:
                mols_valid.append(mol)
                y_valid.append(y)
                smiles_clean.append(s)
                if train_x_d is not None:
                    # Map back to the original index in train_smiles
                    orig_idx = [j for j, val in enumerate(valid_mask) if val][i]
                    train_x_d_valid.append(train_x_d[orig_idx])
        except Exception:
            continue
            
    if len(mols_valid) == 0:
        raise ValueError("No valid compounds for Chemprop HPO!")
        
    y_valid = np.array(y_valid)
    
    def objective(trial: optuna.Trial) -> float:
        params = {
            "depth": trial.suggest_int("depth", 2, 5),
            "hidden_size": trial.suggest_categorical("hidden_size", [150, 300, 500]),
            "ffn_num_layers": trial.suggest_int("ffn_num_layers", 1, 3),
            "dropout": trial.suggest_float("dropout", 0.0, 0.3),
            "epochs": 15,  # Short epochs for fast HPO
            "batch_size": 50
        }
        
        kf = ScaffoldKFold(n_splits=cv_folds, random_state=random_state)
        fold_scores = []
        
        for fold_tr_idx, fold_va_idx in kf.split(np.zeros((len(mols_valid), 1)), y_valid, smiles_clean):
            tr_mols = [mols_valid[i] for i in fold_tr_idx]
            tr_y = y_valid[fold_tr_idx]
            va_mols = [mols_valid[i] for i in fold_va_idx]
            va_y = y_valid[fold_va_idx]
            
            if train_x_d is not None:
                tr_dps = [
                    MoleculeDatapoint(mol=m, y=np.array([y]), x_d=np.array([float(val)]) if isinstance(train_x_d_valid[idx], (int, float, np.number)) else np.array(train_x_d_valid[idx], dtype=float))
                    for idx, (m, y) in zip(fold_tr_idx, zip(tr_mols, tr_y))
                ]
                va_dps = [
                    MoleculeDatapoint(mol=m, y=np.array([y]), x_d=np.array([float(val)]) if isinstance(train_x_d_valid[idx], (int, float, np.number)) else np.array(train_x_d_valid[idx], dtype=float))
                    for idx, (m, y) in zip(fold_va_idx, zip(va_mols, va_y))
                ]
            else:
                tr_dps = [MoleculeDatapoint(mol=m, y=np.array([y])) for m, y in zip(tr_mols, tr_y)]
                va_dps = [MoleculeDatapoint(mol=m, y=np.array([y])) for m, y in zip(va_mols, va_y)]
            
            tr_ds = MoleculeDataset(tr_dps)
            va_ds = MoleculeDataset(va_dps)
            
            tr_dl = build_dataloader(tr_ds, batch_size=params["batch_size"], shuffle=True)
            va_dl = build_dataloader(va_ds, batch_size=params["batch_size"], shuffle=False)
            
            extra_dim = 0
            if train_x_d is not None and len(train_x_d_valid) > 0:
                xd_sample = train_x_d_valid[0]
                extra_dim = 1 if isinstance(xd_sample, (int, float, np.number)) else len(xd_sample)
            input_dim = params["hidden_size"] + extra_dim
            
            mp = BondMessagePassing(d_h=params["hidden_size"], depth=params["depth"], dropout=params["dropout"])
            agg = MeanAggregation()
            
            if task_kind == "classification":
                predictor = BinaryClassificationFFN(
                    input_dim=input_dim, hidden_dim=params["hidden_size"],
                    n_layers=params["ffn_num_layers"], dropout=params["dropout"]
                )
            else:
                predictor = RegressionFFN(
                    input_dim=input_dim, hidden_dim=params["hidden_size"],
                    n_layers=params["ffn_num_layers"], dropout=params["dropout"]
                )
            
            model = MPNN(mp, agg, predictor)
            
            trainer = L.Trainer(
                max_epochs=params["epochs"],
                accelerator="gpu" if torch.cuda.is_available() else "cpu",
                enable_checkpointing=False,
                logger=False,
                enable_progress_bar=False
            )
            
            trainer.fit(model, tr_dl)
            
            preds_list = trainer.predict(model, va_dl)
            preds = np.concatenate([p.numpy() for p in preds_list], axis=0).flatten()
            
            if task_kind == "classification":
                probs = 1.0 / (1.0 + np.exp(-preds))
                binary_preds = (probs >= 0.5).astype(int)
                score = balanced_accuracy_score(va_y, binary_preds)
                fold_scores.append(score)
            else:
                rmse = np.sqrt(np.mean((va_y - preds) ** 2))
                fold_scores.append(rmse)
            
        return float(np.mean(fold_scores))
        
    direction = "maximize" if task_kind == "classification" else "minimize"
    study = optuna.create_study(direction=direction)
    study.optimize(objective, n_trials=n_trials)
    
    metric_name = "Balanced Accuracy" if task_kind == "classification" else "RMSE"
    logger.info(f"Chemprop HPO completed. Best HPO CV {metric_name}: {study.best_value:.4f}")
    return study.best_params


def train_chemprop_mve_ensemble(
    train_smiles: List[str],
    train_y: np.ndarray,
    cal_smiles: List[str],
    cal_y: np.ndarray,
    config: Dict[str, Any],
    output_dir: str,
    seeds: List[int] = [0, 1, 2, 3, 4],
    train_x_d: Optional[List[np.ndarray]] = None,
    cal_x_d: Optional[List[np.ndarray]] = None
) -> Dict[str, Any]:
    """Trains a 5-seed Chemprop D-MPNN ensemble with MveLoss for Soil DT50."""
    os.makedirs(output_dir, exist_ok=True)
    
    # Filter out invalid SMILES/targets
    train_mols_valid = []
    train_y_valid = []
    train_x_d_valid = []
    for i, (s, y) in enumerate(zip(train_smiles, train_y)):
        if np.isnan(y):
            continue
        try:
            mol = Chem.MolFromSmiles(s)
            if mol is not None:
                train_mols_valid.append(mol)
                train_y_valid.append(y)
                if train_x_d is not None:
                    train_x_d_valid.append(train_x_d[i])
        except Exception:
            continue
            
    cal_mols_valid = []
    cal_y_valid = []
    cal_x_d_valid = []
    for i, (s, y) in enumerate(zip(cal_smiles, cal_y)):
        if np.isnan(y):
            continue
        try:
            mol = Chem.MolFromSmiles(s)
            if mol is not None:
                cal_mols_valid.append(mol)
                cal_y_valid.append(y)
                if cal_x_d is not None:
                    cal_x_d_valid.append(cal_x_d[i])
        except Exception:
            continue
            
    if not train_mols_valid or not cal_mols_valid:
        raise ValueError("No valid compounds in train/calibration sets for Chemprop MVE!")
        
    logger.info(f"Training Chemprop MVE ensemble ({len(seeds)} seeds) with config: {config}")
    
    # Build MoleculeDatasets
    if train_x_d is not None:
        train_dps = [
            MoleculeDatapoint(mol=m, y=np.array([y]), x_d=np.array([float(val)]) if isinstance(xd, (int, float, np.number)) else np.array(xd, dtype=float))
            for m, y, xd in zip(train_mols_valid, train_y_valid, train_x_d_valid)
        ]
    else:
        train_dps = [MoleculeDatapoint(mol=m, y=np.array([y])) for m, y in zip(train_mols_valid, train_y_valid)]
    train_ds = MoleculeDataset(train_dps)
    
    if cal_x_d is not None:
        cal_dps = [
            MoleculeDatapoint(mol=m, y=np.array([y]), x_d=np.array([float(val)]) if isinstance(xd, (int, float, np.number)) else np.array(xd, dtype=float))
            for m, y, xd in zip(cal_mols_valid, cal_y_valid, cal_x_d_valid)
        ]
    else:
        cal_dps = [MoleculeDatapoint(mol=m, y=np.array([y])) for m, y in zip(cal_mols_valid, cal_y_valid)]
    cal_ds = MoleculeDataset(cal_dps)
    
    batch_size = config.get("batch_size", 64)
    epochs = config.get("epochs", 80)
    
    accelerator = "gpu" if torch.cuda.is_available() else "cpu"
    seed_val_losses = {}
    
    for seed in seeds:
        logger.info(f"--- Training Chemprop MVE Seed {seed} ---")
        L.seed_everything(seed)
        torch.manual_seed(seed)
        
        train_dl = build_dataloader(train_ds, batch_size=batch_size, shuffle=True, seed=seed)
        cal_dl = build_dataloader(cal_ds, batch_size=batch_size, shuffle=False)
        
        hidden_size = config.get("hidden_size", 300)
        ffn_hidden_size = config.get("ffn_hidden_size", 300)
        
        extra_dim = 0
        if train_x_d is not None and len(train_x_d_valid) > 0:
            xd_sample = train_x_d_valid[0]
            extra_dim = 1 if isinstance(xd_sample, (int, float, np.number)) else len(xd_sample)
            
        input_dim = hidden_size + extra_dim
        
        mp = BondMessagePassing(
            d_h=hidden_size,
            depth=config.get("depth", 3),
            dropout=config.get("dropout", 0.1),
            activation=config.get("activation", "relu")
        )
        agg = MeanAggregation()
        
        predictor = MveFFN(
            input_dim=input_dim,
            hidden_dim=ffn_hidden_size,
            n_layers=config.get("ffn_num_layers", 2),
            dropout=config.get("dropout", 0.1),
            activation=config.get("activation", "relu")
        )
        
        model = MPNN(
            mp, 
            agg, 
            predictor,
            warmup_epochs=config.get("warmup_epochs", 2),
            init_lr=config.get("init_lr", 1e-4),
            max_lr=config.get("max_lr", 1e-3),
            final_lr=config.get("final_lr", 1e-4)
        )
        
        trainer = L.Trainer(
            max_epochs=epochs,
            accelerator=accelerator,
            enable_checkpointing=False,
            logger=False,
            enable_progress_bar=False
        )
        
        trainer.fit(model, train_dl, cal_dl)
        
        model_path = os.path.join(output_dir, f"seed_{seed}.pt")
        save_model(model_path, model)
        
        # Evaluate validation loss (NLL)
        val_preds_list = trainer.predict(model, cal_dl)
        val_preds = np.concatenate([p.numpy() for p in val_preds_list], axis=0)  # shape (N, 1, 2)
        val_means = val_preds[:, 0, 0]
        val_vars = val_preds[:, 0, 1]
        
        # Compute Gaussian NLL
        val_nll = float(0.5 * (np.log(val_vars) + (np.array(cal_y_valid) - val_means)**2 / val_vars).mean())
        seed_val_losses[seed] = val_nll
        logger.info(f"Seed {seed} completed. Validation NLL: {val_nll:.4f}")
        
    metadata = {
        "config": config,
        "seeds": seeds,
        "task_kind": "regression_heteroscedastic",
        "seed_val_losses": seed_val_losses,
        "mean_val_nll": float(np.mean(list(seed_val_losses.values()))),
        "mean_val_score": float(np.mean(list(seed_val_losses.values()))),
        "accelerator": accelerator
    }
    
    return metadata


def predict_chemprop_mve_ensemble(
    smiles: List[str],
    checkpoint_dir: str,
    seeds: List[int] = [0, 1, 2, 3, 4],
    x_d: Optional[List[np.ndarray]] = None
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Predicts using a Chemprop MVE ensemble.
    
    Returns (mu_combined, var_combined, var_epistemic, var_aleatoric)
    """
    n_compounds = len(smiles)
    if n_compounds == 0:
        return np.zeros(0), np.zeros(0), np.zeros(0), np.zeros(0)
        
    # Map valid molecules, track parse failures
    valid_mols = []
    invalid_indices = []
    placeholder_mol = Chem.MolFromSmiles("C")
    
    for i, smi in enumerate(smiles):
        try:
            mol = Chem.MolFromSmiles(smi)
            if mol is not None:
                valid_mols.append((i, mol))
            else:
                invalid_indices.append(i)
                valid_mols.append((i, placeholder_mol))
        except Exception:
            invalid_indices.append(i)
            valid_mols.append((i, placeholder_mol))
            
    if x_d is not None:
        dps = [
            MoleculeDatapoint(mol=m, x_d=np.array([float(val)]) if isinstance(x_d[idx], (int, float, np.number)) else np.array(x_d[idx], dtype=float))
            for idx, m in valid_mols
        ]
    else:
        dps = [MoleculeDatapoint(mol=m) for _, m in valid_mols]
    ds = MoleculeDataset(dps)
    
    accelerator = "gpu" if torch.cuda.is_available() else "cpu"
    all_means = []
    all_vars = []
    
    for seed in seeds:
        model_path = os.path.join(checkpoint_dir, f"seed_{seed}.pt")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Chemprop MVE checkpoint not found for seed {seed} at {model_path}")
            
        model = load_model(model_path)
        dl = build_dataloader(ds, batch_size=64, shuffle=False)
        
        trainer = L.Trainer(
            accelerator=accelerator,
            logger=False,
            enable_checkpointing=False,
            enable_progress_bar=False
        )
        
        preds_list = trainer.predict(model, dl)
        preds = np.concatenate([p.numpy() for p in preds_list], axis=0)  # shape (N, 1, 2)
        
        all_means.append(preds[:, 0, 0])
        all_vars.append(preds[:, 0, 1])
        
    all_means = np.stack(all_means, axis=0)  # (K, N)
    all_vars = np.stack(all_vars, axis=0)    # (K, N)
    
    # Mixture of Gaussians combination
    mu_combined = np.mean(all_means, axis=0)
    var_epistemic = np.var(all_means, axis=0)
    var_aleatoric = np.mean(all_vars, axis=0)
    var_combined = var_epistemic + var_aleatoric
    
    # Overwrite invalid SMILES with NaNs
    if invalid_indices:
        mu_combined[invalid_indices] = np.nan
        var_combined[invalid_indices] = np.nan
        var_epistemic[invalid_indices] = np.nan
        var_aleatoric[invalid_indices] = np.nan
        
    return mu_combined, var_combined, var_epistemic, var_aleatoric


def chemprop_mve_hpo(
    train_smiles: List[str],
    train_y: np.ndarray,
    smiles_scaffolds: List[str],
    inchikeys: List[str],
    n_trials: int = 20,
    cv_folds: int = 3,
    random_state: int = 42,
    train_x_d: Optional[List[np.ndarray]] = None
) -> Dict[str, Any]:
    """HPO for Chemprop MVE model over train partition using grouped scaffold CV."""
    logger.info(f"Starting Chemprop MVE HPO: {n_trials} trials, {cv_folds}-fold grouped Scaffold CV")
    
    valid_mask = ~np.isnan(train_y)
    train_y_valid = train_y[valid_mask]
    train_smiles_valid = [train_smiles[i] for i, v in enumerate(valid_mask) if v]
    train_inchikeys_valid = [inchikeys[i] for i, v in enumerate(valid_mask) if v]
    
    mols_valid = []
    y_valid = []
    smiles_clean = []
    inchikeys_clean = []
    train_x_d_valid = []
    
    for i, (s, y) in enumerate(zip(train_smiles_valid, train_y_valid)):
        try:
            mol = Chem.MolFromSmiles(s)
            if mol is not None:
                mols_valid.append(mol)
                y_valid.append(y)
                smiles_clean.append(s)
                inchikeys_clean.append(train_inchikeys_valid[i])
                if train_x_d is not None:
                    orig_idx = [j for j, val in enumerate(valid_mask) if val][i]
                    train_x_d_valid.append(train_x_d[orig_idx])
        except Exception:
            continue
            
    if len(mols_valid) == 0:
        raise ValueError("No valid compounds for Chemprop MVE HPO!")
        
    y_valid = np.array(y_valid)
    
    def objective(trial: optuna.Trial) -> float:
        params = {
            "depth": trial.suggest_int("depth", 2, 5),
            "hidden_size": trial.suggest_categorical("hidden_size", [150, 300, 500]),
            "ffn_num_layers": trial.suggest_int("ffn_num_layers", 1, 3),
            "dropout": trial.suggest_float("dropout", 0.0, 0.3),
            "epochs": 15,
            "batch_size": 64
        }
        
        kf = ScaffoldKFold(n_splits=cv_folds, random_state=random_state)
        fold_scores = []
        
        # Scaffold split using InChIKey grouping
        for fold_tr_idx, fold_va_idx in kf.split(np.zeros((len(mols_valid), 1)), y_valid, smiles_clean, groups=inchikeys_clean):
            tr_mols = [mols_valid[i] for i in fold_tr_idx]
            tr_y = y_valid[fold_tr_idx]
            va_mols = [mols_valid[i] for i in fold_va_idx]
            va_y = y_valid[fold_va_idx]
            
            if train_x_d is not None:
                tr_dps = [
                    MoleculeDatapoint(mol=m, y=np.array([y]), x_d=np.array([float(val)]) if isinstance(train_x_d_valid[idx], (int, float, np.number)) else np.array(train_x_d_valid[idx], dtype=float))
                    for idx, (m, y) in zip(fold_tr_idx, zip(tr_mols, tr_y))
                ]
                va_dps = [
                    MoleculeDatapoint(mol=m, y=np.array([y]), x_d=np.array([float(val)]) if isinstance(train_x_d_valid[idx], (int, float, np.number)) else np.array(train_x_d_valid[idx], dtype=float))
                    for idx, (m, y) in zip(fold_va_idx, zip(va_mols, va_y))
                ]
            else:
                tr_dps = [MoleculeDatapoint(mol=m, y=np.array([y])) for m, y in zip(tr_mols, tr_y)]
                va_dps = [MoleculeDatapoint(mol=m, y=np.array([y])) for m, y in zip(va_mols, va_y)]
                
            tr_ds = MoleculeDataset(tr_dps)
            va_ds = MoleculeDataset(va_dps)
            
            tr_dl = build_dataloader(tr_ds, batch_size=params["batch_size"], shuffle=True)
            va_dl = build_dataloader(va_ds, batch_size=params["batch_size"], shuffle=False)
            
            extra_dim = 0
            if train_x_d is not None and len(train_x_d_valid) > 0:
                xd_sample = train_x_d_valid[0]
                extra_dim = 1 if isinstance(xd_sample, (int, float, np.number)) else len(xd_sample)
            input_dim = params["hidden_size"] + extra_dim
            
            mp = BondMessagePassing(d_h=params["hidden_size"], depth=params["depth"], dropout=params["dropout"])
            agg = MeanAggregation()
            
            predictor = MveFFN(
                input_dim=input_dim, hidden_dim=params["hidden_size"],
                n_layers=params["ffn_num_layers"], dropout=params["dropout"]
            )
            
            model = MPNN(mp, agg, predictor)
            
            trainer = L.Trainer(
                max_epochs=params["epochs"],
                accelerator="gpu" if torch.cuda.is_available() else "cpu",
                enable_checkpointing=False,
                logger=False,
                enable_progress_bar=False
            )
            
            trainer.fit(model, tr_dl)
            
            preds_list = trainer.predict(model, va_dl)
            preds = np.concatenate([p.numpy() for p in preds_list], axis=0)  # shape (N, 1, 2)
            val_means = preds[:, 0, 0]
            val_vars = preds[:, 0, 1]
            
            # Compute NLL
            nll = float(0.5 * (np.log(val_vars) + (va_y - val_means)**2 / val_vars).mean())
            fold_scores.append(nll)
            
        return float(np.mean(fold_scores))
        
    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=n_trials)
    
    logger.info(f"Chemprop MVE HPO completed. Best HPO CV NLL: {study.best_value:.4f}")
    return study.best_params
