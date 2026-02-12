"""Evaluation metrics and report generation for Edeon Phase 2.

Calculates model performance metrics (regression, conformal prediction intervals,
applicability domains, agrochemical classes) and generates JSON and interactive HTML reports.
"""

import os
import json
import logging
import datetime
import numpy as np
from typing import List, Dict, Tuple, Optional, Any
from scipy.stats import pearsonr, spearmanr
from sklearn.metrics import root_mean_squared_error, mean_absolute_error, r2_score
from jinja2 import Environment, FileSystemLoader
from edeon_models.types import ADStatus
from edeon_train.shared.compound_classes import tag_compound_classes

logger = logging.getLogger("edeon_train.evaluate")

def compute_regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, Any]:
    """Computes standard regression metrics (RMSE, MAE, R2, Pearson, Spearman)."""
    mask = ~np.isnan(y_true) & ~np.isnan(y_pred)
    yt = y_true[mask]
    yp = y_pred[mask]
    
    if len(yt) == 0:
        return {
            "rmse": np.nan, "mae": np.nan, "r2": np.nan,
            "pearson": np.nan, "spearman": np.nan, "count": 0
        }
        
    rmse = root_mean_squared_error(yt, yp)
    mae = mean_absolute_error(yt, yp)
    r2 = r2_score(yt, yp)
    
    try:
        r, _ = pearsonr(yt, yp)
    except Exception:
        r = np.nan
        
    try:
        rho, _ = spearmanr(yt, yp)
    except Exception:
        rho = np.nan
        
    return {
        "rmse": float(rmse),
        "mae": float(mae),
        "r2": float(r2),
        "pearson": float(r) if not np.isnan(r) else None,
        "spearman": float(rho) if not np.isnan(rho) else None,
        "count": int(len(yt))
    }

def compute_ad_and_conformal_stats(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_low: np.ndarray,
    y_high: np.ndarray,
    ad_statuses: List[ADStatus],
    ad_distances: List[Optional[float]]
) -> Dict[str, Any]:
    """Computes conformal coverage, widths, and breakdowns across applicability domain zones."""
    mask = ~np.isnan(y_true) & ~np.isnan(y_pred) & ~np.isnan(y_low) & ~np.isnan(y_high)
    yt = y_true[mask]
    yp = y_pred[mask]
    lo = y_low[mask]
    hi = y_high[mask]
    
    statuses = [ad_statuses[i] for i, m in enumerate(mask) if m]
    
    # Overall conformal stats
    in_interval = (yt >= lo) & (yt <= hi)
    overall_coverage = float(in_interval.mean()) if len(in_interval) > 0 else np.nan
    mean_width = float(np.mean(hi - lo)) if len(in_interval) > 0 else np.nan
    
    # Conformal and prediction metrics by AD region
    regions = {}
    for status in [ADStatus.IN, ADStatus.BORDERLINE, ADStatus.OUT]:
        status_mask = np.array([s == status for s in statuses])
        count = int(status_mask.sum())
        
        if count > 0:
            reg_yt = yt[status_mask]
            reg_yp = yp[status_mask]
            reg_lo = lo[status_mask]
            reg_hi = hi[status_mask]
            
            reg_in = (reg_yt >= reg_lo) & (reg_yt <= reg_hi)
            reg_cov = float(reg_in.mean())
            reg_rmse = float(root_mean_squared_error(reg_yt, reg_yp))
            reg_width = float(np.mean(reg_hi - reg_lo))
            
            regions[status.value] = {
                "count": count,
                "rmse": reg_rmse,
                "coverage": reg_cov,
                "mean_width": reg_width
            }
        else:
            regions[status.value] = {
                "count": 0,
                "rmse": np.nan,
                "coverage": np.nan,
                "mean_width": np.nan
            }
            
    return {
        "overall_coverage": overall_coverage,
        "mean_width": mean_width,
        "regions": regions
    }

def compute_class_breakdowns(
    smiles: List[str],
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_low: np.ndarray,
    y_high: np.ndarray,
    ad_statuses: List[ADStatus]
) -> Dict[str, Any]:
    """Computes metrics and AD coverages broken down by chemical functional class."""
    class_to_indices = {}
    
    for i, s in enumerate(smiles):
        if np.isnan(y_true[i]) or np.isnan(y_pred[i]):
            continue
        classes = tag_compound_classes(s)
        for cls in classes:
            if cls not in class_to_indices:
                class_to_indices[cls] = []
            class_to_indices[cls].append(i)
            
    class_breakdowns = {}
    for cls_name, indices in class_to_indices.items():
        idx_arr = np.array(indices)
        yt = y_true[idx_arr]
        yp = y_pred[idx_arr]
        lo = y_low[idx_arr]
        hi = y_high[idx_arr]
        cls_statuses = [ad_statuses[idx] for idx in indices]
        
        rmse = root_mean_squared_error(yt, yp)
        in_interval = (yt >= lo) & (yt <= hi)
        coverage = float(in_interval.mean())
        
        # Fraction of compounds in class that are in-domain (IN or BORDERLINE)
        in_domain_count = sum(1 for s in cls_statuses if s in (ADStatus.IN, ADStatus.BORDERLINE))
        ad_coverage = float(in_domain_count / len(cls_statuses))
        
        class_breakdowns[cls_name] = {
            "count": len(indices),
            "rmse": float(rmse),
            "coverage": coverage,
            "ad_coverage": ad_coverage
        }
        
    return class_breakdowns

def generate_validation_report(
    endpoint_id: str,
    y_true_test: np.ndarray,
    y_pred_test: np.ndarray,
    y_low_test: np.ndarray,
    y_high_test: np.ndarray,
    ad_statuses_test: List[ADStatus],
    ad_distances_test: List[Optional[float]],
    smiles_test: List[str],
    train_samples: int,
    cal_samples: int,
    cv_train_rmse: float,
    cal_rmse: float,
    cal_r2: float,
    output_dir: str,
    subset_masks: Optional[Dict[str, np.ndarray]] = None,
    inchikeys_test: Optional[List[str]] = None,
    sigma2_pred_test: Optional[np.ndarray] = None,
    cv_train_nll: Optional[float] = None,
    cal_nll: Optional[float] = None
) -> Dict[str, Any]:
    """Generates and writes validation_report.json and validation_report.html dashboards."""
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Compute regression metrics
    overall_metrics = compute_regression_metrics(y_true_test, y_pred_test)
    
    # Heteroscedastic metrics
    overall_nll = None
    spearman_sigma = None
    
    if sigma2_pred_test is not None:
        mask = ~np.isnan(y_true_test) & ~np.isnan(y_pred_test) & ~np.isnan(sigma2_pred_test)
        yt = y_true_test[mask]
        mu = y_pred_test[mask]
        var = sigma2_pred_test[mask]
        if len(yt) > 0:
            overall_nll = float(0.5 * (np.log(var) + (yt - mu)**2 / var).mean())
            
        if inchikeys_test is not None:
            observed_stds = []
            predicted_means_of_sigma = []
            unique_inchikeys = list(set(inchikeys_test))
            for ikey in unique_inchikeys:
                idx = [i for i, k in enumerate(inchikeys_test) if k == ikey]
                if len(idx) >= 3:
                    y_true_comp = y_true_test[idx]
                    y_true_comp = y_true_comp[~np.isnan(y_true_comp)]
                    if len(y_true_comp) >= 3:
                        obs_std = np.std(y_true_comp, ddof=1)
                        pred_sigmas = np.sqrt(sigma2_pred_test[idx])
                        pred_sigmas = pred_sigmas[~np.isnan(pred_sigmas)]
                        if len(pred_sigmas) > 0:
                            mean_pred_sigma = np.mean(pred_sigmas)
                            observed_stds.append(obs_std)
                            predicted_means_of_sigma.append(mean_pred_sigma)
                            
            if len(observed_stds) >= 3:
                spearman_corr, _ = spearmanr(observed_stds, predicted_means_of_sigma)
                if not np.isnan(spearman_corr):
                    spearman_sigma = float(spearman_corr)
                    
    if overall_nll is not None:
        overall_metrics["nll"] = overall_nll
    if spearman_sigma is not None:
        overall_metrics["spearman_sigma"] = spearman_sigma
        
    # 2. Compute AD and conformal stats
    conformal_stats = compute_ad_and_conformal_stats(
        y_true_test, y_pred_test, y_low_test, y_high_test, ad_statuses_test, ad_distances_test
    )
    
    # 3. Compute class breakdowns
    class_stats = compute_class_breakdowns(
        smiles_test, y_true_test, y_pred_test, y_low_test, y_high_test, ad_statuses_test
    )
    
    # 4. Compute subset metrics if subset_masks provided
    subset_metrics = {}
    if subset_masks is not None:
        for subset_name, mask in subset_masks.items():
            if np.any(mask):
                yt_sub = y_true_test[mask]
                yp_sub = y_pred_test[mask]
                lo_sub = y_low_test[mask]
                hi_sub = y_high_test[mask]
                ad_statuses_sub = [ad_statuses_test[i] for i, m in enumerate(mask) if m]
                ad_distances_sub = [ad_distances_test[i] for i, m in enumerate(mask) if m]
                
                sub_reg = compute_regression_metrics(yt_sub, yp_sub)
                sub_conf = compute_ad_and_conformal_stats(
                    yt_sub, yp_sub, lo_sub, hi_sub, ad_statuses_sub, ad_distances_sub
                )
                
                subset_metrics[subset_name] = {
                    "rmse": sub_reg["rmse"],
                    "r2": sub_reg["r2"],
                    "mae": sub_reg["mae"],
                    "coverage": sub_conf["overall_coverage"],
                    "mean_width": sub_conf["mean_width"],
                    "count": int(mask.sum())
                }
    
    report_data = {
        "endpoint_id": endpoint_id,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "train_samples": train_samples,
        "cal_samples": cal_samples,
        "test_samples": len(smiles_test),
        "cv_train_rmse": cv_train_rmse,
        "cv_train_nll": cv_train_nll,
        "cal_rmse": cal_rmse,
        "cal_nll": cal_nll,
        "cal_r2": cal_r2,
        "overall": overall_metrics,
        "conformal": conformal_stats,
        "classes": class_stats,
        "subset_metrics": subset_metrics if subset_metrics else None
    }
    
    # Save structured JSON
    json_path = os.path.join(output_dir, "validation_report.json")
    with open(json_path, "w") as f:
        json.dump(report_data, f, indent=2)
    logger.info(f"Saved structured validation report JSON to {json_path}")
    
    # compile HTML report using Jinja2
    template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("validation_report.html.j2")
    
    # Filter out parse failures for JavaScript parity plotting
    valid_plot_indices = [
        i for i in range(len(smiles_test)) 
        if not np.isnan(y_true_test[i]) and not np.isnan(y_pred_test[i])
    ]
    
    y_true_plot = [float(y_true_test[i]) for i in valid_plot_indices]
    y_pred_plot = [float(y_pred_test[i]) for i in valid_plot_indices]
    y_low_plot = [float(y_low_test[i]) for i in valid_plot_indices]
    y_high_plot = [float(y_high_test[i]) for i in valid_plot_indices]
    hover_labels = [smiles_test[i] for i in valid_plot_indices]
    
    html_content = template.render(
        endpoint_id=endpoint_id,
        timestamp=report_data["timestamp"],
        train_samples=train_samples,
        cal_samples=cal_samples,
        test_samples=report_data["test_samples"],
        cv_train_rmse=cv_train_rmse,
        cal_rmse=cal_rmse,
        cal_r2=cal_r2,
        overall=overall_metrics,
        conformal=conformal_stats,
        classes=class_stats,
        subset_metrics=subset_metrics if subset_metrics else None,
        y_true_raw=json.dumps(y_true_plot),
        y_pred_raw=json.dumps(y_pred_plot),
        y_low_raw=json.dumps(y_low_plot),
        y_high_raw=json.dumps(y_high_plot),
        hover_labels=json.dumps(hover_labels)
    )
    
    html_path = os.path.join(output_dir, "validation_report.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    logger.info(f"Saved interactive validation report HTML dashboard to {html_path}")
    
    return report_data

def compute_classification_metrics(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    threshold: float = 0.5
) -> Dict[str, Any]:
    """Computes classification metrics for binary tasks.
    
    Args:
        y_true: True binary labels (0/1), shape (n,).
        y_proba: Predicted probabilities for class 1 (toxic), shape (n,).
        threshold: Decision boundary for converting probabilities to labels.
        
    Returns:
        Dict with balanced_accuracy, auc_roc, f1, precision, recall,
        confusion_matrix, ece.
    """
    from sklearn.metrics import (
        balanced_accuracy_score, roc_auc_score, f1_score,
        precision_score, recall_score, confusion_matrix
    )
    
    mask = ~np.isnan(y_true) & ~np.isnan(y_proba)
    yt = y_true[mask].astype(int)
    yp = y_proba[mask]
    
    if len(yt) == 0:
        return {
            "balanced_accuracy": np.nan, "auc_roc": np.nan,
            "f1": np.nan, "precision": np.nan, "recall": np.nan,
            "confusion_matrix": [[0, 0], [0, 0]],
            "ece": np.nan, "count": 0
        }
    
    y_pred_binary = (yp >= threshold).astype(int)
    
    ba = balanced_accuracy_score(yt, y_pred_binary)
    f1 = f1_score(yt, y_pred_binary, zero_division=0)
    prec = precision_score(yt, y_pred_binary, zero_division=0)
    rec = recall_score(yt, y_pred_binary, zero_division=0)
    cm = confusion_matrix(yt, y_pred_binary, labels=[0, 1])
    
    try:
        auc = roc_auc_score(yt, yp)
    except ValueError:
        auc = np.nan
    
    # Expected Calibration Error (10-bin)
    ece = _compute_ece(yt, yp, n_bins=10)
    
    return {
        "balanced_accuracy": float(ba),
        "auc_roc": float(auc) if not np.isnan(auc) else None,
        "f1": float(f1),
        "precision": float(prec),
        "recall": float(rec),
        "confusion_matrix": cm.tolist(),
        "ece": float(ece),
        "count": int(len(yt))
    }

def _compute_ece(y_true: np.ndarray, y_proba: np.ndarray, n_bins: int = 10) -> float:
    """Computes the Expected Calibration Error (ECE)."""
    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    total = len(y_true)
    
    for i in range(n_bins):
        mask = (y_proba > bins[i]) & (y_proba <= bins[i + 1])
        if i == 0:
            mask = (y_proba >= bins[i]) & (y_proba <= bins[i + 1])
        count = mask.sum()
        if count == 0:
            continue
        avg_confidence = y_proba[mask].mean()
        avg_accuracy = y_true[mask].mean()
        ece += (count / total) * abs(avg_accuracy - avg_confidence)
    
    return float(ece)

def compute_classification_ad_stats(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    ad_statuses: List[ADStatus],
    threshold: float = 0.5
) -> Dict[str, Any]:
    """Computes classification metrics broken down by AD region."""
    from sklearn.metrics import balanced_accuracy_score
    
    mask = ~np.isnan(y_true) & ~np.isnan(y_proba)
    yt = y_true[mask].astype(int)
    yp = y_proba[mask]
    statuses = [ad_statuses[i] for i, m in enumerate(mask) if m]
    
    regions = {}
    for status in [ADStatus.IN, ADStatus.BORDERLINE, ADStatus.OUT]:
        status_mask = np.array([s == status for s in statuses])
        count = int(status_mask.sum())
        
        if count > 0:
            reg_yt = yt[status_mask]
            reg_yp = yp[status_mask]
            reg_pred = (reg_yp >= threshold).astype(int)
            
            ba = float(balanced_accuracy_score(reg_yt, reg_pred))
            accuracy = float((reg_yt == reg_pred).mean())
            
            regions[status.value] = {
                "count": count,
                "balanced_accuracy": ba,
                "accuracy": accuracy,
            }
        else:
            regions[status.value] = {
                "count": 0,
                "balanced_accuracy": np.nan,
                "accuracy": np.nan,
            }
    
    return {"regions": regions}

def generate_classification_validation_report(
    endpoint_id: str,
    y_true_test: np.ndarray,
    y_proba_test: np.ndarray,
    ad_statuses_test: List[ADStatus],
    ad_distances_test: List[Optional[float]],
    smiles_test: List[str],
    train_samples: int,
    cal_samples: int,
    cv_train_ba: float,
    cal_ba: float,
    conformal_coverage: float,
    mean_set_size: float,
    output_dir: str
) -> Dict[str, Any]:
    """Generates classification validation report (JSON + HTML).
    
    Args:
        endpoint_id: Name of the endpoint.
        y_true_test: True binary labels on test set.
        y_proba_test: Predicted probabilities on test set.
        ad_statuses_test: AD status for each test compound.
        ad_distances_test: AD distance for each test compound.
        smiles_test: SMILES strings for each test compound.
        train_samples: Number of training compounds.
        cal_samples: Number of calibration compounds.
        cv_train_ba: CV balanced accuracy during training.
        cal_ba: Balanced accuracy on calibration set.
        conformal_coverage: Conformal coverage on test set.
        mean_set_size: Mean prediction set size (1.0=crisp, 2.0=uncertain).
        output_dir: Directory for report output.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Compute classification metrics
    overall_metrics = compute_classification_metrics(y_true_test, y_proba_test)
    
    # 2. Compute AD breakdowns
    ad_stats = compute_classification_ad_stats(y_true_test, y_proba_test, ad_statuses_test)
    
    # 3. Compute calibration bins for reliability diagram
    calibration_bins = _compute_calibration_bins(y_true_test, y_proba_test, n_bins=10)
    
    # 4. Compute ROC curve data
    roc_data = _compute_roc_data(y_true_test, y_proba_test)
    
    report_data = {
        "endpoint_id": endpoint_id,
        "task_kind": "classification",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "train_samples": train_samples,
        "cal_samples": cal_samples,
        "test_samples": len(smiles_test),
        "cv_train_balanced_accuracy": cv_train_ba,
        "cal_balanced_accuracy": cal_ba,
        "conformal_coverage": conformal_coverage,
        "mean_set_size": mean_set_size,
        "overall": overall_metrics,
        "ad": ad_stats,
        "calibration_bins": calibration_bins,
        "roc": roc_data
    }
    
    # Save structured JSON
    json_path = os.path.join(output_dir, "validation_report.json")
    with open(json_path, "w") as f:
        json.dump(report_data, f, indent=2)
    logger.info(f"Saved classification validation report JSON to {json_path}")
    
    # Render HTML report
    template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
    env = Environment(loader=FileSystemLoader(template_dir))
    
    try:
        template = env.get_template("classification_report.html.j2")
    except Exception:
        logger.warning("Classification report template not found, skipping HTML generation")
        return report_data
    
    # Prepare data for JS charts
    valid_indices = [
        i for i in range(len(smiles_test))
        if not np.isnan(y_true_test[i]) and not np.isnan(y_proba_test[i])
    ]
    
    proba_plot = [float(y_proba_test[i]) for i in valid_indices]
    labels_plot = [int(y_true_test[i]) for i in valid_indices]
    hover_labels = [smiles_test[i] for i in valid_indices]
    
    html_content = template.render(
        endpoint_id=endpoint_id,
        timestamp=report_data["timestamp"],
        train_samples=train_samples,
        cal_samples=cal_samples,
        test_samples=report_data["test_samples"],
        cv_train_ba=cv_train_ba,
        cal_ba=cal_ba,
        overall=overall_metrics,
        ad=ad_stats,
        conformal_coverage=conformal_coverage,
        mean_set_size=mean_set_size,
        calibration_bins=json.dumps(calibration_bins),
        roc_data=json.dumps(roc_data),
        proba_raw=json.dumps(proba_plot),
        labels_raw=json.dumps(labels_plot),
        hover_labels=json.dumps(hover_labels),
        confusion_matrix=json.dumps(overall_metrics["confusion_matrix"])
    )
    
    html_path = os.path.join(output_dir, "validation_report.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    logger.info(f"Saved classification validation report HTML to {html_path}")
    
    return report_data

def _compute_calibration_bins(
    y_true: np.ndarray, y_proba: np.ndarray, n_bins: int = 10
) -> list:
    """Computes calibration reliability diagram data."""
    mask = ~np.isnan(y_true) & ~np.isnan(y_proba)
    yt = y_true[mask].astype(int)
    yp = y_proba[mask]
    
    bins = np.linspace(0, 1, n_bins + 1)
    result = []
    
    for i in range(n_bins):
        if i == 0:
            bin_mask = (yp >= bins[i]) & (yp <= bins[i + 1])
        else:
            bin_mask = (yp > bins[i]) & (yp <= bins[i + 1])
        count = int(bin_mask.sum())
        
        if count > 0:
            avg_predicted = float(yp[bin_mask].mean())
            avg_actual = float(yt[bin_mask].mean())
        else:
            avg_predicted = float((bins[i] + bins[i + 1]) / 2)
            avg_actual = 0.0
            
        result.append({
            "bin_start": float(bins[i]),
            "bin_end": float(bins[i + 1]),
            "count": count,
            "avg_predicted": avg_predicted,
            "avg_actual": avg_actual
        })
    
    return result

def _compute_roc_data(y_true: np.ndarray, y_proba: np.ndarray) -> dict:
    """Computes ROC curve points for Chart.js plotting."""
    from sklearn.metrics import roc_curve, roc_auc_score
    
    mask = ~np.isnan(y_true) & ~np.isnan(y_proba)
    yt = y_true[mask].astype(int)
    yp = y_proba[mask]
    
    if len(yt) == 0 or len(np.unique(yt)) < 2:
        return {"fpr": [], "tpr": [], "thresholds": [], "auc": None}
    
    fpr, tpr, thresholds = roc_curve(yt, yp)
    auc = roc_auc_score(yt, yp)
    
    return {
        "fpr": [float(x) for x in fpr],
        "tpr": [float(x) for x in tpr],
        "thresholds": [float(x) for x in thresholds],
        "auc": float(auc)
    }
