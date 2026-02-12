"""
Classification Model Diagnostics Module
"""
import numpy as np
from sklearn.metrics import roc_curve, precision_recall_curve, auc
from sklearn.calibration import calibration_curve
from edeon_engine.diagnostics.regression import _learning_curve

def _confusion(y_true, y_pred):
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    tp = int(np.sum((y_true == 1) & (y_pred == 1)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))
    tn = int(np.sum((y_true == 0) & (y_pred == 0)))
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "total": len(y_true)
    }

def _roc_with_ci(cv_fold_predictions):
    if not cv_fold_predictions:
        return {"points": [], "auc": 0.0}
    
    mean_fpr = np.linspace(0.0, 1.0, 100)
    tprs = []
    aucs = []
    
    for fold in cv_fold_predictions:
        y_true_fold = np.asarray(fold["y_true"])
        y_proba_fold = np.asarray(fold["y_proba"])
        if len(np.unique(y_true_fold)) < 2:
            continue
        fpr, tpr, _ = roc_curve(y_true_fold, y_proba_fold)
        interp_tpr = np.interp(mean_fpr, fpr, tpr)
        interp_tpr[0] = 0.0
        tprs.append(interp_tpr)
        aucs.append(auc(fpr, tpr))
        
    if not tprs:
        return {"points": [], "auc": 0.0}
        
    mean_tpr = np.mean(tprs, axis=0)
    mean_tpr[-1] = 1.0
    std_tpr = np.std(tprs, axis=0)
    
    points = []
    for i, fpr_val in enumerate(mean_fpr):
        tpr_val = mean_tpr[i]
        std_val = std_tpr[i]
        tpr_min = max(0.0, tpr_val - std_val)
        tpr_max = min(1.0, tpr_val + std_val)
        points.append({
            "fpr": float(fpr_val),
            "tpr": float(tpr_val),
            "tpr_min": float(tpr_min),
            "tpr_max": float(tpr_max)
        })
        
    mean_auc = float(np.mean(aucs)) if aucs else 0.0
    return {
        "points": points,
        "auc": mean_auc
    }

def _pr_with_ci(cv_fold_predictions):
    if not cv_fold_predictions:
        return {"points": [], "auc": 0.0}
        
    mean_recall = np.linspace(0.0, 1.0, 100)
    precisions = []
    aucs = []
    
    for fold in cv_fold_predictions:
        y_true_fold = np.asarray(fold["y_true"])
        y_proba_fold = np.asarray(fold["y_proba"])
        if len(np.unique(y_true_fold)) < 2:
            continue
        precision, recall, _ = precision_recall_curve(y_true_fold, y_proba_fold)
        
        rev_recall = recall[::-1]
        rev_precision = precision[::-1]
        
        interp_precision = np.interp(mean_recall, rev_recall, rev_precision)
        precisions.append(interp_precision)
        aucs.append(auc(rev_recall, rev_precision))
        
    if not precisions:
        return {"points": [], "auc": 0.0}
        
    mean_precision = np.mean(precisions, axis=0)
    std_precision = np.std(precisions, axis=0)
    
    points = []
    for i, rec_val in enumerate(mean_recall):
        prec_val = mean_precision[i]
        std_val = std_precision[i]
        prec_min = max(0.0, prec_val - std_val)
        prec_max = min(1.0, prec_val + std_val)
        points.append({
            "recall": float(rec_val),
            "precision": float(prec_val),
            "precision_min": float(prec_min),
            "precision_max": float(prec_max)
        })
        
    mean_auc = float(np.mean(aucs)) if aucs else 0.0
    return {
        "points": points,
        "auc": mean_auc
    }

def _calibration_curve(y_true, y_proba, n_bins=10):
    y_true = np.asarray(y_true)
    y_proba = np.asarray(y_proba)
    if len(np.unique(y_true)) < 2:
        return []
    
    try:
        prob_true, prob_pred = calibration_curve(y_true, y_proba, n_bins=n_bins, strategy="uniform")
        return [
            {
                "pred": float(p),
                "true": float(t)
            }
            for p, t in zip(prob_pred, prob_true)
        ]
    except Exception:
        return []

def _threshold_sweep(y_true, y_proba):
    y_true = np.asarray(y_true)
    y_proba = np.asarray(y_proba)
    thresholds = np.linspace(0.01, 0.99, 50)
    sweep = []
    for t in thresholds:
        y_pred_t = (y_proba >= t).astype(int)
        tp = int(np.sum((y_true == 1) & (y_pred_t == 1)))
        fp = int(np.sum((y_true == 0) & (y_pred_t == 1)))
        fn = int(np.sum((y_true == 1) & (y_pred_t == 0)))
        tn = int(np.sum((y_true == 0) & (y_pred_t == 0)))
        
        accuracy = float(tp + tn) / len(y_true) if len(y_true) > 0 else 0.0
        precision = float(tp) / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = float(tp) / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        sweep.append({
            "threshold": float(t),
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "accuracy": float(accuracy),
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn
        })
    return sweep

def _histogram(data, bins=20):
    if len(data) == 0:
        edges = np.linspace(0.0, 1.0, bins + 1)
        return [
            {
                "bin_start": float(edges[i]),
                "bin_end": float(edges[i+1]),
                "bin_center": float(0.5 * (edges[i] + edges[i+1])),
                "count": 0
            }
            for i in range(bins)
        ]
    
    counts, edges = np.histogram(data, bins=bins, range=(0.0, 1.0))
    bin_centers = 0.5 * (edges[:-1] + edges[1:])
    return [
        {
            "bin_start": float(edges[i]),
            "bin_end": float(edges[i+1]),
            "bin_center": float(bin_centers[i]),
            "count": int(counts[i])
        }
        for i in range(len(counts))
    ]

def classification_diagnostics(y_true, y_pred, y_proba,
                               cv_fold_predictions: list[dict],
                               estimator, X_train, y_train_arr,
                               cv_k, random_state) -> dict:
    y_true = np.asarray(y_true, dtype=int)
    y_pred = np.asarray(y_pred, dtype=int)
    y_proba = np.asarray(y_proba, dtype=float)
    
    cv_k = cv_k if cv_k >= 2 else 5
    
    return {
        "confusion_matrix": _confusion(y_true, y_pred),
        "roc": _roc_with_ci(cv_fold_predictions),
        "pr": _pr_with_ci(cv_fold_predictions),
        "calibration": _calibration_curve(y_true, y_proba, n_bins=10),
        "threshold_sweep": _threshold_sweep(y_true, y_proba),
        "probability_histogram": {
            "positive": _histogram(y_proba[y_true == 1], bins=20),
            "negative": _histogram(y_proba[y_true == 0], bins=20),
        },
        "learning_curve": _learning_curve(estimator, X_train, y_train_arr,
                                           cv=cv_k, random_state=random_state,
                                           scoring="roc_auc"),
        "calibration_data": {
            "y_true": y_true.tolist(),
            "y_proba": y_proba.tolist(),
        }
    }

