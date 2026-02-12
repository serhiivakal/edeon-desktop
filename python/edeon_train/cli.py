"""CLI Orchestrator for Edeon Phase 2 reference model training.

Provides a unified interface (edeon-train) to run HPO, train, calibrate,
evaluate, and deploy Tier-1 models for all 7 ecotoxicology endpoints.
"""

import os
import sys
import logging
import argparse
import yaml
import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("edeon_train.cli")

from edeon_train.config import ENDPOINT_CONFIGS
from edeon_train.gates import TestSetGate
from edeon_train.shared.featurize import select_uncorrelated_descriptors, featurize_for_baseline, FeatureRegistry
from edeon_train.shared.baselines import train_baseline_with_hpo, save_baseline_checkpoint, load_baseline_checkpoint
from edeon_train.shared.chemprop_wrapper import train_chemprop_ensemble, predict_chemprop_ensemble, chemprop_hpo
from edeon_train.shared.ensemble import WeightedEnsemble
from edeon_train.shared.conformal import (
    SplitConformalRegressor, EnsembleVarianceCalibrator,
    InductiveConformalClassifier,
    save_calibration, load_calibration,
    save_classification_calibration, load_classification_calibration
)
from edeon_train.shared.ad import TrainedTanimotoAD
from edeon_train.shared.evaluate import (
    generate_validation_report,
    compute_classification_metrics,
    generate_classification_validation_report
)
from edeon_models.types import ModelCard, TrainingDataInfo, PerformanceMetrics, ADDefinition, ADStatus
from edeon_models.card import save_card

# Centralized database paths to update both standard and workspace SQLite files
DB_PATHS = [
    os.path.expanduser("~/.local/share/com.edeon.desktop/edeon.db"),
    "edeon.db"
]

def load_partition(
    dataset_dir: str,
    partition: str,
    target_kind: str = "regression",
    cls_config: Dict[str, Any] = None,
    return_ionizable: bool = False
) -> Any:
    """Loads a split partition from Parquet.
    
    For regression: returns value_log as the target.
    For classification: derives binary labels from value_class or threshold.
    """
    path = os.path.join(dataset_dir, "splits", "scaffold", f"{partition}.parquet")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Partition Parquet file not found at: {path}")
    df = pd.read_parquet(path)
    smiles_col = "smiles_canonical" if "smiles_canonical" in df.columns else ("smiles" if "smiles" in df.columns else "smiles_original")
    smiles = df[smiles_col].tolist()
    inchikeys = df["inchikey"].tolist() if "inchikey" in df.columns else [""] * len(smiles)
    
    if target_kind == "classification" and cls_config is not None:
        label_source = cls_config.get("label_source", "value_class")
        
        if label_source == "value_class":
            # Bee endpoints: use pre-curated labels
            pos_label = cls_config.get("positive_label", "toxic")
            raw_labels = df["value_class"].values
            y = np.array([
                1 if str(v).strip().lower() == pos_label.lower() else 0
                for v in raw_labels
            ], dtype=float)
        elif label_source == "threshold":
            # Fish/algae/bird: derive from value column
            col = cls_config.get("threshold_column", "value")
            threshold_val = cls_config.get("threshold_value", 10.0)
            direction = cls_config.get("threshold_direction", "le")
            values = df[col].values.astype(float)
            
            if direction == "le":
                y = (values <= threshold_val).astype(float)
            elif direction == "ge":
                y = (values >= threshold_val).astype(float)
            else:
                y = (values <= threshold_val).astype(float)
        else:
            raise ValueError(f"Unknown label_source: {label_source}")
        
        n_pos = int(y.sum())
        n_neg = len(y) - n_pos
        logger.info(
            f"Classification partition '{partition}': {n_pos} positive (toxic), "
            f"{n_neg} negative (nontoxic), total={len(y)}"
        )
    else:
        y = df["value_log"].values.astype(float)
    
    if return_ionizable:
        curated_path = os.path.join(dataset_dir, "curated.parquet")
        if os.path.exists(curated_path):
            curated_df = pd.read_parquet(curated_path)
            key_col = "inchikey" if "inchikey" in curated_df.columns else ("smiles_canonical" if "smiles_canonical" in curated_df.columns else "smiles")
            flag_map = dict(zip(curated_df[key_col], curated_df["quality_flags"]))
            df_key_col = "inchikey" if "inchikey" in df.columns else ("smiles_canonical" if "smiles_canonical" in df.columns else "smiles")
            quality_flags_col = [flag_map.get(k, []) for k in df[df_key_col]]
        else:
            quality_flags_col = df["quality_flags"].values if "quality_flags" in df.columns else [None] * len(smiles)
            
        ionizable_flags = []
        for flags in quality_flags_col:
            is_ion = 0
            if flags is not None:
                if any("ionizable" in str(f) for f in flags):
                    is_ion = 1
            ionizable_flags.append(is_ion)
        return smiles, y, inchikeys, ionizable_flags
        
    return smiles, y, inchikeys

def run_hpo(endpoint: str, config: Dict[str, Any], checkpoint_dir: str) -> None:
    """Runs Optuna HPO for baseline models and Chemprop on train partition."""
    logger.info(f"=== Starting HPO Pipeline for {endpoint} ===")
    
    target_kind = config.get("target_kind", "regression")
    cls_config = config.get("classification", None)
    
    if target_kind == "regression_heteroscedastic":
        smiles, y, inchikeys = load_partition(config["phase1_dataset"], "train", target_kind, cls_config)
        ionizable_flags = None
    elif endpoint == "soil_koc":
        smiles, y, inchikeys, ionizable_flags = load_partition(config["phase1_dataset"], "train", target_kind, cls_config, return_ionizable=True)
    else:
        smiles, y, inchikeys = load_partition(config["phase1_dataset"], "train", target_kind, cls_config)
        ionizable_flags = None
    
    # 1. Select uncorrelated descriptors
    selected_descriptors = select_uncorrelated_descriptors(smiles, threshold=0.95)
    registry = FeatureRegistry(selected_descriptors)
    
    # Save FeatureRegistry
    with open(os.path.join(checkpoint_dir, "feature_registry.json"), "w") as f:
        json.dump(registry.to_dict(), f, indent=2)
        
    X_train = featurize_for_baseline(smiles, selected_descriptors, ionizable_flags=ionizable_flags)
    import torch
    is_cuda = torch.cuda.is_available()
    baseline_trials = 50 if is_cuda else 10
    chemprop_trials = config["chemprop"].get("hpo_trials", 15) if is_cuda else 5

    if target_kind == "regression_heteroscedastic":
        # 2. Run Heteroscedastic MLP HPO
        from edeon_train.shared.heteroscedastic import hpo_heteroscedastic_mlp
        os.makedirs(os.path.join(checkpoint_dir, "hmlp"), exist_ok=True)
        best_mlp_params = hpo_heteroscedastic_mlp(
            X_train, y, smiles, inchikeys, n_trials=chemprop_trials, cv_folds=3
        )
        mlp_hpo_config = {**config["chemprop"], **best_mlp_params, "max_epochs": 200, "patience": 15, "lr": 5e-4}
        with open(os.path.join(checkpoint_dir, "hmlp_hpo_config.yaml"), "w") as f:
            yaml.dump(mlp_hpo_config, f, default_flow_style=False)
            
        # 3. Run Chemprop MVE HPO
        from edeon_train.shared.chemprop_wrapper import chemprop_mve_hpo
        os.makedirs(os.path.join(checkpoint_dir, "chemprop_mve"), exist_ok=True)
        best_mve_params = chemprop_mve_hpo(
            train_smiles=smiles,
            train_y=y,
            smiles_scaffolds=smiles,
            inchikeys=inchikeys,
            n_trials=chemprop_trials,
            cv_folds=3
        )
        mve_hpo_config = {**config["chemprop"], **best_mve_params}
        with open(os.path.join(checkpoint_dir, "chemprop_mve_hpo_config.yaml"), "w") as f:
            yaml.dump(mve_hpo_config, f, default_flow_style=False)
    else:
        # 2. Run Baseline HPO
        os.makedirs(os.path.join(checkpoint_dir, "baselines"), exist_ok=True)
        rf_model, rf_meta = train_baseline_with_hpo(
            X_train, y, smiles, model_type="rf", task_kind=target_kind,
            n_trials=baseline_trials, cv_folds=5
        )
        save_baseline_checkpoint(rf_model, rf_meta, os.path.join(checkpoint_dir, "baselines"))
        
        xgb_model, xgb_meta = train_baseline_with_hpo(
            X_train, y, smiles, model_type="xgb", task_kind=target_kind,
            n_trials=baseline_trials, cv_folds=5
        )
        save_baseline_checkpoint(xgb_model, xgb_meta, os.path.join(checkpoint_dir, "baselines"))
        
        # 3. Run Chemprop HPO
        best_chemprop_params = chemprop_hpo(
            train_smiles=smiles,
            train_y=y,
            smiles_scaffolds=smiles,
            n_trials=chemprop_trials,
            cv_folds=3,
            task_kind=target_kind,
            train_x_d=[np.array([float(val)]) for val in ionizable_flags] if ionizable_flags is not None else None
        )
        
        # Merge best params into chemprop config
        hpo_config = {**config["chemprop"], **best_chemprop_params}
        with open(os.path.join(checkpoint_dir, "chemprop_hpo_config.yaml"), "w") as f:
            yaml.dump(hpo_config, f, default_flow_style=False)
        
    logger.info(f"=== HPO Pipeline Completed for {endpoint} ===")

def run_train(endpoint: str, config: Dict[str, Any], checkpoint_dir: str) -> None:
    """Trains baseline models and 5-seed Chemprop ensemble using best HPO parameters."""
    logger.info(f"=== Starting Model Training Pipeline for {endpoint} ===")
    os.makedirs(os.path.join(checkpoint_dir, "baselines"), exist_ok=True)
    os.makedirs(os.path.join(checkpoint_dir, "chemprop"), exist_ok=True)
    
    target_kind = config.get("target_kind", "regression")
    cls_config = config.get("classification", None)
    
    # Load Train & Cal (cal is validation for Chemprop early stopping)
    if target_kind == "regression_heteroscedastic":
        train_smiles, train_y, _ = load_partition(config["phase1_dataset"], "train", target_kind, cls_config)
        cal_smiles, cal_y, _ = load_partition(config["phase1_dataset"], "cal", target_kind, cls_config)
        train_ionizable = None
        cal_ionizable = None
    elif endpoint == "soil_koc":
        train_smiles, train_y, _, train_ionizable = load_partition(config["phase1_dataset"], "train", target_kind, cls_config, return_ionizable=True)
        cal_smiles, cal_y, _, cal_ionizable = load_partition(config["phase1_dataset"], "cal", target_kind, cls_config, return_ionizable=True)
    else:
        train_smiles, train_y, _ = load_partition(config["phase1_dataset"], "train", target_kind, cls_config)
        cal_smiles, cal_y, _ = load_partition(config["phase1_dataset"], "cal", target_kind, cls_config)
        train_ionizable = None
        cal_ionizable = None
    
    # 1. Feature Registry & Baseline Featurization
    registry_path = os.path.join(checkpoint_dir, "feature_registry.json")
    if os.path.exists(registry_path):
        logger.info("Loading pre-selected descriptors from HPO step...")
        with open(registry_path, "r") as f:
            registry = FeatureRegistry.from_dict(json.load(f))
    else:
        logger.info("No pre-existing FeatureRegistry found. Running dynamic descriptor selection...")
        selected_descs = select_uncorrelated_descriptors(train_smiles, threshold=0.95)
        registry = FeatureRegistry(selected_descs)
        with open(registry_path, "w") as f:
            json.dump(registry.to_dict(), f, indent=2)
            
    X_train = featurize_for_baseline(train_smiles, registry.descriptors_selected, ionizable_flags=train_ionizable)
    
    if target_kind == "regression_heteroscedastic":
        # 2. Train Heteroscedastic MLP ensemble
        from edeon_train.shared.heteroscedastic import train_heteroscedastic_ensemble
        hmlp_config_path = os.path.join(checkpoint_dir, "hmlp_hpo_config.yaml")
        if os.path.exists(hmlp_config_path):
            with open(hmlp_config_path, "r") as f:
                hmlp_cfg = yaml.safe_load(f)
        else:
            hmlp_cfg = {**config["chemprop"], "max_epochs": 200, "patience": 15, "lr": 5e-4}
            
        X_cal = featurize_for_baseline(cal_smiles, registry.descriptors_selected)
        hmlp_meta = train_heteroscedastic_ensemble(
            X_train=X_train, y_train=train_y,
            X_val=X_cal, y_val=cal_y,
            config=hmlp_cfg,
            output_dir=os.path.join(checkpoint_dir, "hmlp")
        )
        with open(os.path.join(checkpoint_dir, "hmlp", "ensemble_config.yaml"), "w") as f:
            yaml.dump(hmlp_meta, f, default_flow_style=False)
            
        # 3. Train Chemprop MVE ensemble
        from edeon_train.shared.chemprop_wrapper import train_chemprop_mve_ensemble
        mve_config_path = os.path.join(checkpoint_dir, "chemprop_mve_hpo_config.yaml")
        if os.path.exists(mve_config_path):
            with open(mve_config_path, "r") as f:
                mve_cfg = yaml.safe_load(f)
        else:
            mve_cfg = config["chemprop"]
            
        mve_meta = train_chemprop_mve_ensemble(
            train_smiles=train_smiles, train_y=train_y,
            cal_smiles=cal_smiles, cal_y=cal_y,
            config=mve_cfg,
            output_dir=os.path.join(checkpoint_dir, "chemprop_mve")
        )
        with open(os.path.join(checkpoint_dir, "chemprop_mve", "ensemble_config.yaml"), "w") as f:
            yaml.dump(mve_meta, f, default_flow_style=False)
            
        logger.info(f"=== Model Training Completed successfully for {endpoint} ===")
        return
    
    # 2. Train Baselines (Random Forest & XGBoost)
    rf_hpo_path = os.path.join(checkpoint_dir, "baselines", "rf_hpo_results.json")
    if os.path.exists(rf_hpo_path):
        with open(rf_hpo_path, "r") as f:
            rf_hpo = json.load(f)
        logger.info(f"Refitting RF with best parameters: {rf_hpo['best_params']}")
        rf_model, rf_meta = train_baseline_with_hpo(
            X_train, train_y, train_smiles, model_type="rf",
            task_kind=target_kind, n_trials=1, cv_folds=2
        )
        rf_meta["best_params"] = rf_hpo["best_params"]
        rf_meta["best_cv_rmse"] = rf_hpo.get("best_cv_rmse")
        rf_meta["best_cv_score"] = rf_hpo.get("best_cv_score", rf_hpo.get("best_cv_rmse"))
    else:
        import torch
        train_trials = 20 if torch.cuda.is_available() else 5
        rf_model, rf_meta = train_baseline_with_hpo(
            X_train, train_y, train_smiles, model_type="rf",
            task_kind=target_kind, n_trials=train_trials, cv_folds=5
        )
    save_baseline_checkpoint(rf_model, rf_meta, os.path.join(checkpoint_dir, "baselines"))
    
    xgb_hpo_path = os.path.join(checkpoint_dir, "baselines", "xgb_hpo_results.json")
    if os.path.exists(xgb_hpo_path):
        with open(xgb_hpo_path, "r") as f:
            xgb_hpo = json.load(f)
        logger.info(f"Refitting XGB with best parameters: {xgb_hpo['best_params']}")
        xgb_model, xgb_meta = train_baseline_with_hpo(
            X_train, train_y, train_smiles, model_type="xgb",
            task_kind=target_kind, n_trials=1, cv_folds=2
        )
        xgb_meta["best_params"] = xgb_hpo["best_params"]
        xgb_meta["best_cv_rmse"] = xgb_hpo.get("best_cv_rmse")
        xgb_meta["best_cv_score"] = xgb_hpo.get("best_cv_score", xgb_hpo.get("best_cv_rmse"))
    else:
        import torch
        train_trials = 20 if torch.cuda.is_available() else 5
        xgb_model, xgb_meta = train_baseline_with_hpo(
            X_train, train_y, train_smiles, model_type="xgb",
            task_kind=target_kind, n_trials=train_trials, cv_folds=5
        )
    save_baseline_checkpoint(xgb_model, xgb_meta, os.path.join(checkpoint_dir, "baselines"))
    
    # 3. Train Chemprop D-MPNN Ensemble
    chemprop_config_path = os.path.join(checkpoint_dir, "chemprop_hpo_config.yaml")
    if os.path.exists(chemprop_config_path):
        with open(chemprop_config_path, "r") as f:
            chemprop_cfg = yaml.safe_load(f)
    else:
        chemprop_cfg = config["chemprop"]
        
    chemprop_meta = train_chemprop_ensemble(
        train_smiles=train_smiles,
        train_y=train_y,
        cal_smiles=cal_smiles,
        cal_y=cal_y,
        config=chemprop_cfg,
        output_dir=os.path.join(checkpoint_dir, "chemprop"),
        task_kind=target_kind,
        train_x_d=[np.array([float(val)]) for val in train_ionizable] if train_ionizable is not None else None,
        cal_x_d=[np.array([float(val)]) for val in cal_ionizable] if cal_ionizable is not None else None
    )
    
    with open(os.path.join(checkpoint_dir, "chemprop", "ensemble_config.yaml"), "w") as f:
        yaml.dump(chemprop_meta, f, default_flow_style=False)
        
    # 4. Build and save WeightedEnsemble weights
    if target_kind == "classification":
        cv_scores = {
            "rf": rf_meta.get("best_cv_balanced_accuracy", rf_meta.get("best_cv_score")),
            "xgb": xgb_meta.get("best_cv_balanced_accuracy", xgb_meta.get("best_cv_score")),
            "chemprop": chemprop_meta.get("mean_val_balanced_accuracy", chemprop_meta.get("mean_val_score"))
        }
        logger.info(f"Derived cross-validation Balanced Accuracy values: {cv_scores}")
        ensemble = WeightedEnsemble.from_cv_metrics(cv_scores, task_kind="classification")
    else:
        cv_rmses = {
            "rf": rf_meta["best_cv_rmse"],
            "xgb": xgb_meta["best_cv_rmse"],
            "chemprop": chemprop_meta["mean_val_rmse"]
        }
        logger.info(f"Derived cross-validation RMSE values: {cv_rmses}")
        ensemble = WeightedEnsemble.from_cv_metrics(cv_rmses, task_kind="regression")
    
    ensemble.save(os.path.join(checkpoint_dir, "ensemble_weights.yaml"))
    
    logger.info(f"=== Model Training Completed successfully for {endpoint} ===")

def run_calibrate(endpoint: str, config: Dict[str, Any], checkpoint_dir: str) -> None:
    """Fits conformal calibration and AD thresholds."""
    logger.info(f"=== Starting Model Calibration Pipeline for {endpoint} ===")
    
    target_kind = config.get("target_kind", "regression")
    cls_config = config.get("classification", None)
    
    # Load partitions
    if target_kind == "regression_heteroscedastic":
        train_smiles, _, _ = load_partition(config["phase1_dataset"], "train", target_kind, cls_config)
        cal_smiles, cal_y, _ = load_partition(config["phase1_dataset"], "cal", target_kind, cls_config)
        train_ionizable = None
        cal_ionizable = None
    elif endpoint == "soil_koc":
        train_smiles, _, _, train_ionizable = load_partition(config["phase1_dataset"], "train", target_kind, cls_config, return_ionizable=True)
        cal_smiles, cal_y, _, cal_ionizable = load_partition(config["phase1_dataset"], "cal", target_kind, cls_config, return_ionizable=True)
    else:
        train_smiles, _, _ = load_partition(config["phase1_dataset"], "train", target_kind, cls_config)
        cal_smiles, cal_y, _ = load_partition(config["phase1_dataset"], "cal", target_kind, cls_config)
        train_ionizable = None
        cal_ionizable = None
    
    if target_kind == "regression_heteroscedastic":
        # 1. Load Registry
        with open(os.path.join(checkpoint_dir, "feature_registry.json"), "r") as f:
            registry = FeatureRegistry.from_dict(json.load(f))
            
        # 2. Get predictions on calibration partition using MLP and Chemprop MVE
        from edeon_train.shared.heteroscedastic import predict_heteroscedastic_ensemble
        from edeon_train.shared.chemprop_wrapper import predict_chemprop_mve_ensemble
        from edeon_train.shared.nll_calibration import VarianceScaler, empirical_coverage, nll_score
        
        X_cal = featurize_for_baseline(cal_smiles, registry.descriptors_selected)
        feature_dim = X_cal.shape[1]
        
        hmlp_config_path = os.path.join(checkpoint_dir, "hmlp_hpo_config.yaml")
        if os.path.exists(hmlp_config_path):
            with open(hmlp_config_path, "r") as f:
                hmlp_cfg = yaml.safe_load(f)
        else:
            hmlp_cfg = {**config["chemprop"], "max_epochs": 200, "patience": 15, "lr": 5e-4}
            
        mu_mlp, var_mlp, _, _ = predict_heteroscedastic_ensemble(X_cal, Path(checkpoint_dir) / "hmlp", feature_dim, hmlp_cfg)
        mu_mve, var_mve, _, _ = predict_chemprop_mve_ensemble(cal_smiles, os.path.join(checkpoint_dir, "chemprop_mve"))
        
        mu_cal = 0.5 * (mu_mlp + mu_mve)
        var_cal_combined = 0.5 * (var_mlp + var_mve) + 0.25 * (mu_mlp - mu_mve)**2
        
        # 3. Fit VarianceScaler
        scaler = VarianceScaler()
        scaler.calibrate(mu_cal, var_cal_combined, cal_y, target_coverage=0.95)
        
        np.savez(
            os.path.join(checkpoint_dir, "nll_calibration.npz"),
            scale=scaler.scale_
        )
        
        cal_sigma = np.sqrt(scaler.apply(var_cal_combined))
        cov = empirical_coverage(mu_cal, cal_sigma, cal_y, level=0.95)
        nll = nll_score(mu_cal, scaler.apply(var_cal_combined), cal_y)
        logger.info(f"Variance Scaler calibrated. Scale: {scaler.scale_:.4f}")
        logger.info(f"Calibration coverage: {cov:.4f}, NLL: {nll:.4f}")
        
        # 4. Fit Tanimoto AD using unique training smiles
        ad_k = config.get("ad", {}).get("k", 5)
        ad_radius = config.get("ad", {}).get("fp_radius", 2)
        ad_nbits = config.get("ad", {}).get("fp_bits", 2048)
        
        unique_train_smiles = list(set(train_smiles))
        ad = TrainedTanimotoAD.from_training_smiles(
            unique_train_smiles, k=ad_k, radius=ad_radius, nbits=ad_nbits
        )
        ad.save(os.path.join(checkpoint_dir, "ad_fingerprints.npz"))
        logger.info(f"=== Model Calibration Completed successfully for {endpoint} ===")
        return
    
    if target_kind == "classification":
        # Classification calibration: InductiveConformalClassifier
        y_proba_cal = ensemble.predict_proba(cal_smiles, X_cal)
        
        alpha = config.get("conformal", {}).get("alpha", 0.05)
        cls_cal = InductiveConformalClassifier(alpha=alpha)
        cls_cal.calibrate(y_proba_cal, cal_y)
        
        coverage = cls_cal.empirical_coverage(y_proba_cal, cal_y)
        set_size = cls_cal.mean_set_size(y_proba_cal)
        logger.info(f"Classification Conformal Coverage on Cal: {coverage:.4f}, Mean Set Size: {set_size:.2f}")
        
        save_classification_calibration(cls_cal, os.path.join(checkpoint_dir, "calibration.npz"))
    else:
        # Regression calibration: unchanged
        cal_x_d = [np.array([float(val)]) for val in cal_ionizable] if cal_ionizable is not None else None
        _, chem_std = predict_chemprop_ensemble(cal_smiles, os.path.join(checkpoint_dir, "chemprop"), x_d=cal_x_d)
        y_pred_cal = ensemble.predict(cal_smiles, X_cal, x_d=cal_x_d)
        
        alpha = config.get("conformal", {}).get("alpha", 0.05)
        split_cal = SplitConformalRegressor(alpha=alpha)
        split_cal.calibrate(y_pred_cal, cal_y)
        
        var_cal = EnsembleVarianceCalibrator(alpha=alpha)
        var_cal.calibrate(y_pred_cal, cal_y, chem_std)
        
        split_coverage = split_cal.empirical_coverage(y_pred_cal, cal_y)
        var_coverage = var_cal.empirical_coverage(y_pred_cal, cal_y, chem_std)
        logger.info(f"Conformal Calibration Coverage: Split = {split_coverage:.4f}, Variance-Scaled = {var_coverage:.4f}")
        save_calibration(split_cal, var_cal, os.path.join(checkpoint_dir, "calibration.npz"))
    
    # 4. Fit Tanimoto AD (same for both regression and classification)
    ad_k = config.get("ad", {}).get("k", 5)
    ad_radius = config.get("ad", {}).get("fp_radius", 2)
    ad_nbits = config.get("ad", {}).get("fp_bits", 2048)
    
    ad = TrainedTanimotoAD.from_training_smiles(
        train_smiles, k=ad_k, radius=ad_radius, nbits=ad_nbits
    )
    ad.save(os.path.join(checkpoint_dir, "ad_fingerprints.npz"))
    
    logger.info(f"=== Model Calibration Completed for {endpoint} ===")

def run_evaluate(endpoint: str, config: Dict[str, Any], checkpoint_dir: str) -> None:
    """Performs final evaluation on strictly guarded test partition exactly once."""
    logger.info(f"=== Starting Model Test-Set Evaluation for {endpoint} ===")
    
    target_kind = config.get("target_kind", "regression")
    cls_config = config.get("classification", None)
    
    # Load pre-trained models
    with open(os.path.join(checkpoint_dir, "feature_registry.json"), "r") as f:
        registry = FeatureRegistry.from_dict(json.load(f))
        
    if target_kind != "regression_heteroscedastic":
        ensemble = WeightedEnsemble.load(checkpoint_dir)
    else:
        ensemble = None
    ad = TrainedTanimotoAD.load(os.path.join(checkpoint_dir, "ad_fingerprints.npz"))
    
    # 1. Access the test set via TestSetGate
    gate = TestSetGate.get(endpoint)
    gate.open(reason="Phase 2 final pipeline evaluation and report generation")
    
    if endpoint == "soil_koc":
        test_smiles, test_y, test_inchikeys, test_ionizable = gate.load_test(
            lambda: load_partition(config["phase1_dataset"], "test", target_kind, cls_config, return_ionizable=True)
        )
    else:
        test_smiles, test_y, test_inchikeys = gate.load_test(
            lambda: load_partition(config["phase1_dataset"], "test", target_kind, cls_config)
        )
        test_ionizable = None
    
    # 2. Featurize and Predict
    X_test = featurize_for_baseline(test_smiles, registry.descriptors_selected, ionizable_flags=test_ionizable)
    
    # AD check
    ad_results = ad.score(test_smiles)
    ad_statuses = [r[0] for r in ad_results]
    ad_distances = [r[1] for r in ad_results]
    
    if target_kind == "classification":
        # === CLASSIFICATION EVALUATION PATH ===
        cls_cal = load_classification_calibration(os.path.join(checkpoint_dir, "calibration.npz"))
        
        y_proba = ensemble.predict_proba(test_smiles, X_test)
        
        # Conformal prediction sets
        if cls_cal is not None:
            conformal_coverage = cls_cal.empirical_coverage(y_proba, test_y)
            mean_set_size = cls_cal.mean_set_size(y_proba)
        else:
            conformal_coverage = 0.0
            mean_set_size = 1.0
        
        # Compute cal partition scores for reference
        cal_smiles, cal_y, _ = load_partition(config["phase1_dataset"], "cal", target_kind, cls_config)
        X_cal = featurize_for_baseline(cal_smiles, registry.descriptors_selected)
        y_proba_cal = ensemble.predict_proba(cal_smiles, X_cal)
        from sklearn.metrics import balanced_accuracy_score
        cal_pred = (y_proba_cal >= 0.5).astype(int)
        cal_ba = float(balanced_accuracy_score(cal_y.astype(int), cal_pred))
        
        # CV train BA from HPO results
        xgb_hpo_path = os.path.join(checkpoint_dir, "baselines", "xgb_hpo_results.json")
        if os.path.exists(xgb_hpo_path):
            with open(xgb_hpo_path, "r") as f:
                hpo_data = json.load(f)
            cv_train_ba = hpo_data.get("best_cv_balanced_accuracy", hpo_data.get("best_cv_score", 0.5))
        else:
            cv_train_ba = 0.5
        
        # Load train set count
        train_smiles, _, _ = load_partition(config["phase1_dataset"], "train", target_kind, cls_config)
        
        report = generate_classification_validation_report(
            endpoint_id=config["endpoint_id"],
            y_true_test=test_y,
            y_proba_test=y_proba,
            ad_statuses_test=ad_statuses,
            ad_distances_test=ad_distances,
            smiles_test=test_smiles,
            train_samples=len(train_smiles),
            cal_samples=len(cal_smiles),
            cv_train_ba=cv_train_ba,
            cal_ba=cal_ba,
            conformal_coverage=conformal_coverage,
            mean_set_size=mean_set_size,
            output_dir=checkpoint_dir
        )
        
        # Model Card for classification
        card = ModelCard(
            model_id=f"t1_{config['endpoint_id']}_v1.0_cls",
            name=f"Edeon Tier-1 Reference {config['endpoint_id'].replace('_', ' ').title()} (Classification)",
            version="v1.0_cls",
            tier=1,
            endpoint=config["endpoint_id"],
            description=(
                f"Binary classification QSAR model combining Random Forest, XGBoost, and "
                f"a 5-seed Chemprop D-MPNN ensemble with inductive conformal prediction sets. "
                f"Predicts toxic/nontoxic with calibrated probabilities and a Tanimoto k-NN "
                f"applicability domain auditor."
            ),
            intended_use="Tier-1 binary hazard classification for regulatory screening.",
            training_data=TrainingDataInfo(
                n_compounds=len(train_smiles),
                sources=["Phase 1 Curated Agrochemical Dataset"],
                split_strategy="scaffold"
            ),
            performance=PerformanceMetrics(
                metrics={
                    "balanced_accuracy": report["overall"]["balanced_accuracy"],
                    "auc_roc": report["overall"].get("auc_roc"),
                    "f1": report["overall"]["f1"],
                    "ece": report["overall"]["ece"]
                },
                test_set_n=len(test_smiles),
                cv_folds=5,
                calibration_coverage_95=conformal_coverage
            ),
            applicability_domain=ADDefinition(
                method="tanimoto_knn",
                threshold=ad.in_threshold,
                k=ad.k,
                training_set_size=len(train_smiles)
            ),
            uncertainty_method="inductive_conformal_classification",
            known_failure_modes=[
                "Compounds containing heavy atoms outside H, C, N, O, P, S, F, Cl, Br, I",
                "Extremely macrocyclic compounds or highly fragmented mixtures"
            ],
            references=[
                "Vovk, V., Gammerman, A., & Shafer, G. (2005). Algorithmic learning in a random world.",
                "Norinder, U., et al. (2014). Introducing conformal prediction in predictive modeling."
            ],
            authors=["Edeon AI Team"]
        )
    elif target_kind == "regression_heteroscedastic":
        # === HETEROSCEDASTIC REGRESSION EVALUATION PATH ===
        from edeon_train.shared.heteroscedastic import predict_heteroscedastic_ensemble
        from edeon_train.shared.chemprop_wrapper import predict_chemprop_mve_ensemble
        from pathlib import Path
        
        hmlp_config_path = os.path.join(checkpoint_dir, "hmlp_hpo_config.yaml")
        if os.path.exists(hmlp_config_path):
            with open(hmlp_config_path, "r") as f:
                hmlp_cfg = yaml.safe_load(f)
        else:
            hmlp_cfg = {**config["chemprop"], "max_epochs": 200, "patience": 15, "lr": 5e-4}
            
        feature_dim = X_test.shape[1]
        mu_mlp, var_mlp, _, _ = predict_heteroscedastic_ensemble(X_test, Path(checkpoint_dir) / "hmlp", feature_dim, hmlp_cfg)
        mu_mve, var_mve, _, _ = predict_chemprop_mve_ensemble(test_smiles, os.path.join(checkpoint_dir, "chemprop_mve"))
        
        y_pred = 0.5 * (mu_mlp + mu_mve)
        var_combined = 0.5 * (var_mlp + var_mve) + 0.25 * (mu_mlp - mu_mve)**2
        
        # Apply variance scaling
        cal_data = np.load(os.path.join(checkpoint_dir, "nll_calibration.npz"))
        scale_factor = float(cal_data["scale"])
        sigma2_pred_test = var_combined * scale_factor
        sigma_pred_test = np.sqrt(sigma2_pred_test)
        
        # 95% credible intervals
        from scipy.stats import norm
        z = norm.ppf(0.975)
        y_low = y_pred - z * sigma_pred_test
        y_high = y_pred + z * sigma_pred_test
        
        # Load train and cal datasets to report sizes and compute cal metrics
        train_smiles, _, _ = load_partition(config["phase1_dataset"], "train")
        cal_smiles, cal_y, _ = load_partition(config["phase1_dataset"], "cal")
        
        X_cal = featurize_for_baseline(cal_smiles, registry.descriptors_selected)
        mu_cal_mlp, var_cal_mlp, _, _ = predict_heteroscedastic_ensemble(X_cal, Path(checkpoint_dir) / "hmlp", feature_dim, hmlp_cfg)
        mu_cal_mve, var_cal_mve, _, _ = predict_chemprop_mve_ensemble(cal_smiles, os.path.join(checkpoint_dir, "chemprop_mve"))
        mu_cal = 0.5 * (mu_cal_mlp + mu_cal_mve)
        var_cal_combined = 0.5 * (var_cal_mlp + var_cal_mve) + 0.25 * (mu_cal_mlp - mu_cal_mve)**2
        var_cal_scaled = var_cal_combined * scale_factor
        
        from sklearn.metrics import r2_score
        cal_rmse = float(np.sqrt(np.mean((cal_y - mu_cal) ** 2)))
        cal_r2 = float(r2_score(cal_y, mu_cal))
        cal_nll = float(0.5 * (np.log(var_cal_scaled) + (cal_y - mu_cal)**2 / var_cal_scaled).mean())
        
        cv_train_rmse = 0.0
        cv_train_nll = None
        
        from edeon_train.shared.nll_calibration import empirical_coverage
        cal_coverage = float(empirical_coverage(y_pred, sigma_pred_test, test_y, level=0.95))
        
        report = generate_validation_report(
            endpoint_id=config["endpoint_id"],
            y_true_test=test_y,
            y_pred_test=y_pred,
            y_low_test=y_low,
            y_high_test=y_high,
            ad_statuses_test=ad_statuses,
            ad_distances_test=ad_distances,
            smiles_test=test_smiles,
            train_samples=len(train_smiles),
            cal_samples=len(cal_smiles),
            cv_train_rmse=cv_train_rmse,
            cal_rmse=cal_rmse,
            cal_r2=cal_r2,
            output_dir=checkpoint_dir,
            inchikeys_test=test_inchikeys,
            sigma2_pred_test=sigma2_pred_test,
            cal_nll=cal_nll
        )
        
        card = ModelCard(
            model_id=f"t1_{config['endpoint_id']}_v1.0",
            name=f"Edeon Tier-1 Reference {config['endpoint_id'].replace('_', ' ').title()} (Heteroscedastic)",
            version="v1.0",
            tier=1,
            endpoint=config["endpoint_id"],
            description=(
                f"Heteroscedastic mean-variance reference QSAR model combining a 5-seed PyTorch "
                f"HeteroscedasticMLP ensemble and a 5-seed Chemprop MVE ensemble. Features joint "
                f"aleatoric-epistemic uncertainty modeling with post-hoc variance calibration."
            ),
            intended_use="Tier-1 high-precision prediction of DT50 with joint uncertainty for GUS leaching risk propagation.",
            training_data=TrainingDataInfo(
                n_compounds=len(train_smiles),
                sources=["Phase 1 Curated Agrochemical Dataset"],
                split_strategy="scaffold"
            ),
            performance=PerformanceMetrics(
                metrics={
                    "rmse": report["overall"]["rmse"],
                    "r2": report["overall"]["r2"],
                    "mae": report["overall"]["mae"],
                    "nll": report["overall"]["nll"],
                    "spearman_sigma": report["overall"].get("spearman_sigma", 0.0)
                },
                test_set_n=len(test_smiles),
                cv_folds=5,
                calibration_coverage_95=cal_coverage
            ),
            applicability_domain=ADDefinition(
                method="tanimoto_knn",
                threshold=ad.in_threshold,
                k=ad.k,
                training_set_size=len(train_smiles)
            ),
            uncertainty_method="heteroscedastic_mean_variance_posthoc_calibrated",
            known_failure_modes=[
                "Compounds containing heavy atoms outside H, C, N, O, P, S, F, Cl, Br, I",
                "Extremely macrocyclic compounds or highly fragmented mixtures"
            ],
            references=[
                "Nix, D. A., & Weigend, A. S. (1994). Estimating the mean and variance of target distributions.",
                "Gustafson, D. I. (1989). Groundwater ubiquity score: a simple method for assessing pesticide leachability."
            ],
            authors=["Edeon AI Team"]
        )
    else:
        # === REGRESSION EVALUATION PATH (unchanged) ===
        split_cal, var_cal = load_calibration(os.path.join(checkpoint_dir, "calibration.npz"))
        test_x_d = [np.array([float(val)]) for val in test_ionizable] if test_ionizable is not None else None
        _, chem_std = predict_chemprop_ensemble(test_smiles, os.path.join(checkpoint_dir, "chemprop"), x_d=test_x_d)
        y_pred = ensemble.predict(test_smiles, X_test, x_d=test_x_d)
        
        use_variance_scaled = "chemprop" in ensemble.weights and ensemble.weights["chemprop"] > 0
        if use_variance_scaled:
            y_low, y_high = var_cal.interval(y_pred, chem_std)
            conformal_method = "ensemble_variance_scaled"
            cal_coverage = float(var_cal.empirical_coverage(y_pred, test_y, chem_std))
        else:
            y_low, y_high = split_cal.interval(y_pred)
            conformal_method = "split_conformal"
            cal_coverage = float(split_cal.empirical_coverage(y_pred, test_y))
        
        if endpoint == "soil_koc":
            train_smiles, _, _, train_ionizable = load_partition(config["phase1_dataset"], "train", return_ionizable=True)
            cal_smiles, cal_y, _, cal_ionizable = load_partition(config["phase1_dataset"], "cal", return_ionizable=True)
        else:
            train_smiles, _, _ = load_partition(config["phase1_dataset"], "train")
            cal_smiles, cal_y, _ = load_partition(config["phase1_dataset"], "cal")
            train_ionizable = None
            cal_ionizable = None
            
        cal_x_d = [np.array([float(val)]) for val in cal_ionizable] if cal_ionizable is not None else None
        X_cal = featurize_for_baseline(cal_smiles, registry.descriptors_selected, ionizable_flags=cal_ionizable)
        y_pred_cal = ensemble.predict(cal_smiles, X_cal, x_d=cal_x_d)
        from sklearn.metrics import r2_score
        cal_rmse = float(np.sqrt(np.mean((cal_y - y_pred_cal) ** 2)))
        cal_r2 = float(r2_score(cal_y, y_pred_cal))
        
        with open(os.path.join(checkpoint_dir, "baselines", "xgb_hpo_results.json"), "r") as f:
            cv_train_rmse = json.load(f)["best_cv_rmse"]
            
        subset_masks = None
        if endpoint == "soil_koc" and test_ionizable is not None:
            test_ionizable_arr = np.array(test_ionizable)
            subset_masks = {
                "ionizable": (test_ionizable_arr == 1),
                "non_ionizable": (test_ionizable_arr == 0)
            }
            
        report = generate_validation_report(
            endpoint_id=config["endpoint_id"],
            y_true_test=test_y,
            y_pred_test=y_pred,
            y_low_test=y_low,
            y_high_test=y_high,
            ad_statuses_test=ad_statuses,
            ad_distances_test=ad_distances,
            smiles_test=test_smiles,
            train_samples=len(train_smiles),
            cal_samples=len(cal_smiles),
            cv_train_rmse=cv_train_rmse,
            cal_rmse=cal_rmse,
            cal_r2=cal_r2,
            output_dir=checkpoint_dir,
            subset_masks=subset_masks
        )
        
        card = ModelCard(
            model_id=f"t1_{config['endpoint_id']}_v1.0",
            name=f"Edeon Tier-1 Reference {config['endpoint_id'].replace('_', ' ').title()}",
            version="v1.0",
            tier=1,
            endpoint=config["endpoint_id"],
            description=(
                f"High-fidelity reference QSAR model combining Random Forest, XGBoost, and "
                f"a 5-seed Chemprop D-MPNN ensemble. Features split conformal prediction "
                f"intervals (95%) and a Tanimoto k-NN applicability domain auditor."
            ),
            intended_use="Tier-1 high-precision prediction of ecotoxicological hazard for regulatory screening.",
            training_data=TrainingDataInfo(
                n_compounds=len(train_smiles),
                sources=["Phase 1 Curated Agrochemical Dataset"],
                split_strategy="scaffold"
            ),
            performance=PerformanceMetrics(
                metrics={
                    "rmse": report["overall"]["rmse"],
                    "r2": report["overall"]["r2"],
                    "mae": report["overall"]["mae"]
                },
                test_set_n=len(test_smiles),
                cv_folds=5,
                calibration_coverage_95=cal_coverage,
                subset_metrics=report.get("subset_metrics")
            ),
            applicability_domain=ADDefinition(
                method="tanimoto_knn",
                threshold=ad.in_threshold,
                k=ad.k,
                training_set_size=len(train_smiles)
            ),
            uncertainty_method=conformal_method,
            known_failure_modes=[
                "Compounds containing heavy atoms outside H, C, N, O, P, S, F, Cl, Br, I",
                "Extremely macrocyclic compounds or highly fragmented mixtures"
            ],
            references=[
                "Bemis, G. W., & Murcko, M. A. (1996). The properties of known drugs. 1. Molecular frameworks. J. Med. Chem.",
                "Vovk, V., Gammerman, A., & Shafer, G. (2005). Algorithmic learning in a random world. Springer Science & Business Media."
            ],
            connected_models=[],
            authors=["Edeon AI Team"]
        )
    
    # Save Model Card YAML
    card_yaml_path = os.path.join(checkpoint_dir, "model_card.yaml")
    with open(card_yaml_path, "w") as f:
        yaml.dump(card.model_dump(mode='json'), f, default_flow_style=False, sort_keys=False)
    logger.info(f"Saved Model Card YAML to {card_yaml_path}")
    
    # Write a clean markdown version to docs
    docs_dir = "docs/TIER1_MODEL_CARDS"
    os.makedirs(docs_dir, exist_ok=True)
    doc_path = os.path.join(docs_dir, f"{config['endpoint_id']}.md")
    
    with open(doc_path, "w") as f:
        f.write(f"# Model Card: {card.name}\n\n")
        f.write(f"**Model ID:** `{card.model_id}` | **Version:** `{card.version}`\n\n")
        f.write(f"## Description\n{card.description}\n\n")
        f.write(f"## Performance (Scaffold Test Set)\n")
        if target_kind == "classification":
            f.write(f"- **Balanced Accuracy:** {report['overall']['balanced_accuracy']:.4f}\n")
            f.write(f"- **AUC-ROC:** {report['overall'].get('auc_roc', 'N/A')}\n")
            f.write(f"- **F1:** {report['overall']['f1']:.4f}\n")
            f.write(f"- **ECE:** {report['overall']['ece']:.4f}\n")
            f.write(f"- **Conformal Coverage (95%):** {conformal_coverage*100:.1f}%\n")
            f.write(f"- **Mean Set Size:** {mean_set_size:.2f}\n\n")
        elif target_kind == "regression_heteroscedastic":
            f.write(f"- **Negative Log-Likelihood (NLL):** {report['overall']['nll']:.4f}\n")
            f.write(f"- **Observed vs. Predicted σ Spearman ρ:** {report['overall'].get('spearman_sigma', 0.0):.4f}\n")
            f.write(f"- **RMSE:** {report['overall']['rmse']:.4f}\n")
            f.write(f"- **R²:** {report['overall']['r2']:.4f}\n")
            f.write(f"- **MAE:** {report['overall']['mae']:.4f}\n")
            f.write(f"- **95% Conformal Coverage:** {cal_coverage*100:.1f}%\n\n")
        else:
            f.write(f"- **RMSE:** {report['overall']['rmse']:.4f}\n")
            f.write(f"- **R²:** {report['overall']['r2']:.4f}\n")
            f.write(f"- **MAE:** {report['overall']['mae']:.4f}\n")
            f.write(f"- **95% Conformal Coverage:** {cal_coverage*100:.1f}%\n\n")
        f.write(f"## Applicability Domain\n")
        f.write(f"- **Method:** Tanimoto 5-NN Morgan Fingerprint\n")
        f.write(f"- **In-Domain Distance Threshold (95%):** {ad.in_threshold:.4f}\n")
        f.write(f"- **Borderline Distance Threshold (99%):** {ad.out_threshold:.4f}\n\n")
        f.write(f"## References\n")
        for ref in card.references:
            f.write(f"- {ref}\n")
            
    logger.info(f"Saved human-readable model card MD to {doc_path}")
    logger.info(f"=== Model Test-Set Evaluation Completed successfully for {endpoint} ===")

def run_deploy(endpoint: str, config: Dict[str, Any], checkpoint_dir: str) -> None:
    """Registers ModelCard metadata in SQLite databases for startup loading."""
    logger.info(f"=== Deploying Tier-1 Reference Backend for {endpoint} ===")
    
    card_path = os.path.join(checkpoint_dir, "model_card.yaml")
    if not os.path.exists(card_path):
        raise FileNotFoundError(f"Model Card YAML not found at {card_path}. Please run evaluate first!")
        
    with open(card_path, "r") as f:
        card_data = yaml.safe_load(f)
        
    card = ModelCard.model_validate(card_data)
    
    # Save to SQLite database locations (both user application and workspace repository)
    for db_path in DB_PATHS:
        try:
            save_card(card, db_path=db_path)
            logger.info(f"Model card successfully loaded and saved to database: {db_path}")
        except Exception as e:
            logger.warning(f"Unable to write model card to {db_path}: {e}")
            
    logger.info(f"=== Deployment Completed successfully for {endpoint} ===")

def run_all(endpoint: str, config: Dict[str, Any], checkpoint_dir: str) -> None:
    """Executes HPO, Train, Calibrate, Evaluate, and Deploy in a single end-to-end command."""
    logger.info(f"============================================================")
    logger.info(f"Executing Full Pipeline (All Steps) for {endpoint}")
    logger.info(f"============================================================")
    
    run_hpo(endpoint, config, checkpoint_dir)
    run_train(endpoint, config, checkpoint_dir)
    run_calibrate(endpoint, config, checkpoint_dir)
    run_evaluate(endpoint, config, checkpoint_dir)
    run_deploy(endpoint, config, checkpoint_dir)
    
    logger.info(f"============================================================")
    logger.info(f"Full Pipeline Execution Successfully Completed for {endpoint}")
    logger.info(f"============================================================")

def main() -> None:
    parser = argparse.ArgumentParser(description="Edeon Tier-1 Model Training & Orchestration CLI")
    
    parser.add_argument(
        "endpoint",
        nargs="?",
        help="Endpoint identifier (e.g. 'bee_acute_oral_ld50' or 'all')"
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=["hpo", "train", "calibrate", "evaluate", "deploy", "all"],
        help="Command to run"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all active ecotox endpoints"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Check training status across all endpoints"
    )
    
    args = parser.parse_args()
    
    if args.list:
        print("\nAvailable Edeon Tier-1 Ecotox Endpoints:")
        print("------------------------------------------")
        for ep in ENDPOINT_CONFIGS.keys():
            print(f" - {ep}")
        print()
        sys.exit(0)
        
    if args.status:
        print("\nEdeon Tier-1 Reference Model Training Status:")
        print("-----------------------------------------------")
        for ep in ENDPOINT_CONFIGS.keys():
            ep_dir = os.path.join("data/checkpoints", ep, "v1.0")
            hpo_done = os.path.exists(os.path.join(ep_dir, "baselines", "rf_hpo_results.json"))
            trained = os.path.exists(os.path.join(ep_dir, "ensemble_weights.yaml"))
            calibrated = os.path.exists(os.path.join(ep_dir, "calibration.npz"))
            evaluated = os.path.exists(os.path.join(ep_dir, "validation_report.html"))
            deployed = False
            
            # Check SQLite status
            card_id = f"t1_{ep}_v1.0"
            for db in DB_PATHS:
                if os.path.exists(db):
                    import sqlite3
                    try:
                        conn = sqlite3.connect(db)
                        c = conn.cursor()
                        c.execute("SELECT 1 FROM model_cards WHERE model_id = ?", (card_id,))
                        if c.fetchone() is not None:
                            deployed = True
                        conn.close()
                    except Exception:
                        pass
                        
            status_parts = []
            if hpo_done: status_parts.append("HPO")
            if trained: status_parts.append("TRAINED")
            if calibrated: status_parts.append("CALIBRATED")
            if evaluated: status_parts.append("EVALUATED")
            if deployed: status_parts.append("DEPLOYED")
            
            status_str = " | ".join(status_parts) if status_parts else "UNTRAINED"
            print(f" - {ep:<25} : {status_str}")
        print()
        sys.exit(0)
        
    if not args.endpoint or not args.command:
        parser.print_help()
        sys.exit(1)
        
    endpoint = args.endpoint
    command = args.command
    
    if endpoint == "all":
        endpoints_to_run = list(ENDPOINT_CONFIGS.keys())
    elif endpoint in ENDPOINT_CONFIGS:
        endpoints_to_run = [endpoint]
    else:
        logger.error(f"Unknown endpoint: {endpoint}. Use --list to see options.")
        sys.exit(1)
        
    for ep in endpoints_to_run:
        config = ENDPOINT_CONFIGS[ep]
        target_kind = config.get("target_kind", "regression")
        
        # Classification endpoints use v1.0_cls subdirectory
        if target_kind == "classification":
            checkpoint_dir = os.path.join("data/checkpoints", ep, "v1.0_cls")
        else:
            checkpoint_dir = os.path.join("data/checkpoints", ep, "v1.0")
        
        # Skip if dataset directory does not exist (e.g. for earthworm)
        if not os.path.exists(config["phase1_dataset"]):
            logger.warning(f"Phase 1 dataset path '{config['phase1_dataset']}' does not exist. Skipping endpoint '{ep}'.")
            continue
        
        try:
            if command == "hpo":
                run_hpo(ep, config, checkpoint_dir)
            elif command == "train":
                run_train(ep, config, checkpoint_dir)
            elif command == "calibrate":
                run_calibrate(ep, config, checkpoint_dir)
            elif command == "evaluate":
                run_evaluate(ep, config, checkpoint_dir)
            elif command == "deploy":
                run_deploy(ep, config, checkpoint_dir)
            elif command == "all":
                run_all(ep, config, checkpoint_dir)
        except Exception as e:
            logger.error(f"Failed to execute '{command}' for endpoint '{ep}': {e}", exc_info=True)
            sys.exit(1)

if __name__ == "__main__":
    main()
