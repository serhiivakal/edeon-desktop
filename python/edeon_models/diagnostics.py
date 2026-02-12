"""Interactive model calibration diagnostics module for Edeon."""
import os
import re
import json
import sqlite3
import numpy as np
import pandas as pd
import scipy.stats as stats
from pathlib import Path
from typing import Optional, Any, Dict

from rdkit import Chem, DataStructs

from edeon_models.endpoints import Endpoint
from edeon_models.types import (
    ADStatus,
    CalibrationDiagnostics,
    ParityPlotData,
    ParityPoint,
    CalibrationCurveData,
    CalibrationPoint,
    ResidualDistData,
    HistogramBin,
    ROCData,
    ROCPoint,
    PRData,
    PRPoint,
    ReliabilityData,
    ReliabilityBin,
    ADHistogramData,
)
from edeon_train.shared.ad import TrainedTanimotoAD
from edeon_train.shared.compound_classes import tag_compound_classes
from edeon_models.ipc.commands import REGISTRY
from edeon_models.card import DEFAULT_DB_PATH

def get_calibration_diagnostics(model_id: str, db_path: Optional[str] = None) -> dict:
    """Computes/extracts calibration diagnostics data for a registered model.
    
    Args:
        model_id: Unique model identifier.
        db_path: Path to Edeon SQLite database.
        
    Returns:
        A serialized CalibrationDiagnostics dict.
    """
    if db_path is None:
        db_path = DEFAULT_DB_PATH
        
    # 1. Resolve backend from REGISTRY
    backend = None
    for tier_dict in REGISTRY._backends.values():
        for b in tier_dict.values():
            if b.metadata().model_id == model_id:
                backend = b
                break
        if backend is not None:
            break
            
    # If not in registry, check if we can reconstruct a StudioBackend
    if backend is None and ".t4.studio-" in model_id:
        from edeon_models.backends.studio import StudioBackend
        parts = model_id.split(".t4.studio-")
        endpoint_val = parts[0]
        saved_model_id = parts[1]
        try:
            endpoint = Endpoint(endpoint_val)
            backend = StudioBackend(saved_model_id=saved_model_id, db_path=db_path, deploy_target=endpoint)
        except Exception as e:
            raise ValueError(f"Failed to load StudioBackend for {model_id}: {str(e)}")
            
    if backend is None:
        raise ValueError(f"Model '{model_id}' not found in registry or database.")

    tier = backend.tier()
    
    if tier == 1:
        # Tier-1 Reference Model
        # Retrieve checkpoint directory self._dir
        if not hasattr(backend, "_dir"):
            raise ValueError("Tier-1 backend lacks checkpoint directory configuration.")
            
        checkpoint_dir = Path(backend._dir)
        
        # Load validation JSON
        val_json_path = checkpoint_dir / "validation_report.json"
        if not val_json_path.exists():
            raise FileNotFoundError(f"Validation report JSON not found at {val_json_path}")
            
        with open(val_json_path, "r") as f:
            val_data = json.load(f)
            
        # Load validation HTML (to parse raw test sets)
        val_html_path = checkpoint_dir / "validation_report.html"
        if not val_html_path.exists():
            raise FileNotFoundError(f"Validation report HTML not found at {val_html_path}")
            
        with open(val_html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
            
        endpoint = val_data["endpoint_id"]
        split_strategy = val_data.get("split_strategy") or backend.metadata().training_data.split_strategy or "scaffold"
        task_kind = val_data.get("task_kind", "regression")
        
        # Get test set SMILES
        test_smiles = []
        # Try test.parquet first
        parquet_path = Path("data/curated") / endpoint / "v1.0" / "splits" / split_strategy / "test.parquet"
        if parquet_path.exists():
            try:
                df = pd.read_parquet(parquet_path)
                if "smiles_canonical" in df.columns:
                    test_smiles = df["smiles_canonical"].tolist()
                elif "smiles_original" in df.columns:
                    test_smiles = df["smiles_original"].tolist()
            except Exception:
                pass
                
        # If parquet loading failed or returned empty list, try regex parsing of html report
        if not test_smiles:
            hover_match = re.search(r"const\s+hover_labels\s*=\s*(\[.*?\])\s*;", html_content)
            if not hover_match:
                hover_match = re.search(r"const\s+hoverLabels\s*=\s*(\[.*?\])\s*;", html_content)
            if hover_match:
                try:
                    test_smiles = json.loads(hover_match.group(1))
                except Exception:
                    pass

        # Load AD fingerprints & compute train/test AD distances
        ad_path = checkpoint_dir / "ad_fingerprints.npz"
        if not ad_path.exists():
            raise FileNotFoundError(f"AD fingerprints NPZ not found at {ad_path}")
            
        ad = TrainedTanimotoAD.load(str(ad_path))
        
        # Intra-training distances
        train_fps = ad.train_fps
        train_distances = []
        if len(train_fps) > 1:
            effective_k = min(ad.k, len(train_fps) - 1)
            for i, fp in enumerate(train_fps):
                other_fps = [f for j, f in enumerate(train_fps) if j != i]
                sims = DataStructs.BulkTanimotoSimilarity(fp, other_fps)
                dists = 1.0 - np.array(sims)
                top_k = np.sort(dists)[:effective_k]
                train_distances.append(float(np.mean(top_k)))
                
        # Test set AD distances
        test_distances = []
        if test_smiles:
            ad_results = ad.score(test_smiles)
            test_distances = [res[1] for res in ad_results if res[1] is not None]
            
        ad_histogram = ADHistogramData(
            train_distances=train_distances,
            test_distances=test_distances,
            in_threshold=ad.in_threshold,
            out_threshold=ad.out_threshold
        )
        
        # Build diagnostics based on kind
        if task_kind == "regression":
            # Parse regression arrays from HTML
            y_true_match = re.search(r"const\s+yTrue\s*=\s*(\[.*?\])\s*;", html_content)
            y_pred_match = re.search(r"const\s+yPred\s*=\s*(\[.*?\])\s*;", html_content)
            y_low_match = re.search(r"const\s+yLow\s*=\s*(\[.*?\])\s*;", html_content)
            y_high_match = re.search(r"const\s+yHigh\s*=\s*(\[.*?\])\s*;", html_content)
            
            if not (y_true_match and y_pred_match and y_low_match and y_high_match):
                raise ValueError("Failed to parse regression predicted arrays from validation HTML.")
                
            y_true = json.loads(y_true_match.group(1))
            y_pred = json.loads(y_pred_match.group(1))
            y_low = json.loads(y_low_match.group(1))
            y_high = json.loads(y_high_match.group(1))
            
            # Obtain AD status for test smiles
            test_ad_statuses = []
            if test_smiles:
                test_ad_res = ad.score(test_smiles)
                test_ad_statuses = [res[0].value for res in test_ad_res]
            else:
                test_ad_statuses = ["in"] * len(y_true)
                
            # Parity data
            parity_points = []
            for i in range(len(y_true)):
                sm = test_smiles[i] if i < len(test_smiles) else ""
                status = test_ad_statuses[i] if i < len(test_ad_statuses) else "in"
                parity_points.append(ParityPoint(
                    observed=float(y_true[i]),
                    predicted=float(y_pred[i]),
                    smiles=sm,
                    ad_status=status,
                    ci_lower=float(y_low[i]),
                    ci_upper=float(y_high[i])
                ))
            parity_data = ParityPlotData(points=parity_points)
            
            # Calibration Curve (conformal)
            y_true_arr = np.array(y_true)
            y_pred_arr = np.array(y_pred)
            y_low_arr = np.array(y_low)
            y_high_arr = np.array(y_high)
            half_widths = (y_high_arr - y_low_arr) / 2.0
            half_widths = np.maximum(half_widths, 1e-9)
            normalized_residuals = np.abs(y_true_arr - y_pred_arr) / half_widths
            
            cal_points = []
            for expected in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0]:
                if expected == 0.0:
                    actual = 0.0
                elif expected == 1.0:
                    actual = 1.0
                else:
                    z_c = stats.norm.ppf((1.0 + expected) / 2.0)
                    factor = z_c / 1.9599639845400542
                    actual = float((normalized_residuals <= factor).mean())
                cal_points.append(CalibrationPoint(expected=expected, actual=actual))
            calibration_curve = CalibrationCurveData(points=cal_points)
            
            # Residual distribution
            residuals = y_true_arr - y_pred_arr
            counts, edges = np.histogram(residuals, bins=20)
            bin_centers = 0.5 * (edges[:-1] + edges[1:])
            bins = [
                HistogramBin(
                    bin_start=float(edges[i]),
                    bin_end=float(edges[i+1]),
                    bin_center=float(bin_centers[i]),
                    count=int(counts[i])
                )
                for i in range(len(counts))
            ]
            residual_distribution = ResidualDistData(
                bins=bins,
                mean=float(np.mean(residuals)),
                std=float(np.std(residuals))
            )
            
            # Per chemical class metrics
            per_chemical_class = val_data.get("classes", {})
            
            return CalibrationDiagnostics(
                endpoint=endpoint,
                model_id=model_id,
                test_set_size=len(y_true),
                task_kind="regression",
                parity_data=parity_data,
                calibration_curve=calibration_curve,
                residual_distribution=residual_distribution,
                ad_distance_histogram=ad_histogram,
                per_chemical_class_metrics=per_chemical_class
            ).model_dump(mode='json')
            
        else:
            # Classification
            # Parse classification probabilities & labels from HTML
            proba_match = re.search(r"const\s+proba\s*=\s*(\[.*?\])\s*;", html_content)
            labels_match = re.search(r"const\s+labels\s*=\s*(\[.*?\])\s*;", html_content)
            
            if not (proba_match and labels_match):
                raise ValueError("Failed to parse classification predicted probabilities from validation HTML.")
                
            proba = json.loads(proba_match.group(1))
            labels = json.loads(labels_match.group(1))
            
            # ROC curve
            roc_points = [
                ROCPoint(fpr=float(f), tpr=float(t))
                for f, t in zip(val_data["roc"]["fpr"], val_data["roc"]["tpr"])
            ]
            roc_curve = ROCData(points=roc_points, auc=val_data["roc"]["auc"])
            
            # PR curve
            from sklearn.metrics import precision_recall_curve, auc
            precision, recall, _ = precision_recall_curve(labels, proba)
            pr_points = [
                PRPoint(precision=float(p), recall=float(r))
                for p, r in zip(precision, recall)
            ]
            pr_auc = float(auc(recall, precision))
            pr_curve = PRData(points=pr_points, auc=pr_auc)
            
            # Reliability diagram
            reliability_bins = [
                ReliabilityBin(
                    bin_start=float(b["bin_start"]),
                    bin_end=float(b["bin_end"]),
                    count=int(b["count"]),
                    avg_predicted=float(b["avg_predicted"]),
                    avg_actual=float(b["avg_actual"])
                )
                for b in val_data["calibration_bins"]
            ]
            reliability_diagram = ReliabilityData(bins=reliability_bins)
            
            # Confusion matrix
            confusion_matrix = val_data["overall"]["confusion_matrix"]
            
            # Per chemical class metrics (classification)
            preds_binary = (np.array(proba) >= 0.5).astype(int)
            labels_arr = np.array(labels)
            
            class_to_indices = {}
            for i, s in enumerate(test_smiles):
                classes = tag_compound_classes(s)
                for cls in classes:
                    if cls not in class_to_indices:
                        class_to_indices[cls] = []
                    class_to_indices[cls].append(i)
                    
            from sklearn.metrics import f1_score, balanced_accuracy_score
            per_chemical_class = {}
            for cls_name, idxs in class_to_indices.items():
                idxs = np.array(idxs)
                c_labels = labels_arr[idxs]
                c_preds = preds_binary[idxs]
                c_smiles = [test_smiles[idx] for idx in idxs]
                
                if len(np.unique(c_labels)) >= 2:
                    ba = float(balanced_accuracy_score(c_labels, c_preds))
                else:
                    ba = float((c_labels == c_preds).mean())
                    
                f1 = float(f1_score(c_labels, c_preds, zero_division=0.0))
                
                # AD coverage
                ad_res = ad.score(c_smiles)
                in_domain = sum(1 for res in ad_res if res[0] in (ADStatus.IN, ADStatus.BORDERLINE))
                ad_cov = float(in_domain / len(idxs)) if len(idxs) > 0 else 0.0
                
                per_chemical_class[cls_name] = {
                    "count": len(idxs),
                    "balanced_accuracy": ba,
                    "f1": f1,
                    "ad_coverage": ad_cov
                }
                
            return CalibrationDiagnostics(
                endpoint=endpoint,
                model_id=model_id,
                test_set_size=len(labels),
                task_kind="classification",
                roc_curve=roc_curve,
                pr_curve=pr_curve,
                reliability_diagram=reliability_diagram,
                confusion_matrix=confusion_matrix,
                ad_distance_histogram=ad_histogram,
                per_chemical_class_metrics=per_chemical_class
            ).model_dump(mode='json')

    elif tier == 4:
        # Tier-4 Studio Backend
        # Query saved_models table
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT type, diagnostics, ad_reference FROM saved_models WHERE id = ?",
            (backend._saved_model_id,)
        )
        row = cur.fetchone()
        conn.close()
        
        if not row:
            raise ValueError(f"Custom model '{model_id}' details not found in saved_models table.")
            
        model_type, diags_json, ad_ref_blob = row
        diags = json.loads(diags_json) if diags_json else {}
        
        # Load AD reference to compute training distances
        train_distances = []
        in_threshold = 0.5
        out_threshold = 0.8
        
        if ad_ref_blob:
            try:
                import pickle
                ad_ref = pickle.loads(ad_ref_blob)
                if hasattr(ad_ref, "tanimoto"):
                    t_ref = ad_ref.tanimoto
                    # t_ref is TanimotoKNN_AD
                    train_fps = t_ref._train_fps
                    in_threshold = t_ref.in_threshold
                    out_threshold = t_ref.out_threshold
                    k = t_ref.k
                    if len(train_fps) > 1:
                        effective_k = min(k, len(train_fps) - 1)
                        for i, fp in enumerate(train_fps):
                            other_fps = [f for j, f in enumerate(train_fps) if j != i]
                            sims = DataStructs.BulkTanimotoSimilarity(fp, other_fps)
                            dists = 1.0 - np.array(sims)
                            top_k = np.sort(dists)[:effective_k]
                            train_distances.append(float(np.mean(top_k)))
            except Exception:
                pass
                
        ad_histogram = ADHistogramData(
            train_distances=train_distances,
            test_distances=[],
            in_threshold=in_threshold,
            out_threshold=out_threshold
        )
        
        if model_type == "regression":
            # Map regression diagnostics
            parity_points = []
            parity_raw = diags.get("parity", {}).get("points", [])
            for pt in parity_raw:
                parity_points.append(ParityPoint(
                    observed=float(pt.get("y_true", 0.0)),
                    predicted=float(pt.get("y_pred", 0.0)),
                    smiles="",
                    ad_status=pt.get("ad", "in")
                ))
            parity_data = ParityPlotData(points=parity_points)
            
            # Calibration Curve (conformal)
            cal_points = []
            residuals_fitted = diags.get("residuals_vs_fitted", [])
            if residuals_fitted:
                y_true_list = []
                y_pred_list = []
                for pt in residuals_fitted:
                    yp = pt.get("y_pred", 0.0)
                    res = pt.get("residual", 0.0)
                    y_true_list.append(yp + res)
                    y_pred_list.append(yp)
                y_true_arr = np.array(y_true_list)
                y_pred_arr = np.array(y_pred_list)
                
                residuals_abs = np.abs(y_true_arr - y_pred_arr)
                q_95 = float(np.percentile(residuals_abs, 95)) if len(residuals_abs) > 0 else 0.5
                q_95 = max(q_95, 1e-9)
                
                for expected in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0]:
                    if expected == 0.0:
                        actual = 0.0
                    elif expected == 1.0:
                        actual = 1.0
                    else:
                        z_c = stats.norm.ppf((1.0 + expected) / 2.0)
                        factor = z_c / 1.9599639845400542
                        scaled_margin = q_95 * factor
                        actual = float((residuals_abs <= scaled_margin).mean())
                    cal_points.append(CalibrationPoint(expected=expected, actual=actual))
            calibration_curve = CalibrationCurveData(points=cal_points)
            
            # Residual histogram
            hist_raw = diags.get("residual_histogram", [])
            bins = [
                HistogramBin(
                    bin_start=float(b["bin_start"]),
                    bin_end=float(b["bin_end"]),
                    bin_center=float(b["bin_center"]),
                    count=int(b["count"])
                )
                for b in hist_raw
            ]
            
            residuals_abs = [abs(pt.get("residual", 0.0)) for pt in residuals_fitted]
            residual_distribution = ResidualDistData(
                bins=bins,
                mean=float(np.mean(residuals_abs)) if residuals_abs else 0.0,
                std=float(np.std(residuals_abs)) if residuals_abs else 0.0
            )
            
            return CalibrationDiagnostics(
                endpoint=backend.endpoint().value,
                model_id=model_id,
                test_set_size=len(parity_points),
                task_kind="regression",
                parity_data=parity_data,
                calibration_curve=calibration_curve,
                residual_distribution=residual_distribution,
                ad_distance_histogram=ad_histogram,
                per_chemical_class_metrics={}
            ).model_dump(mode='json')
            
        else:
            # Map classification diagnostics
            cal_raw = diags.get("calibration", [])
            reliability_bins = []
            if cal_raw:
                for i, pt in enumerate(cal_raw):
                    reliability_bins.append(ReliabilityBin(
                        bin_start=float(i) / len(cal_raw),
                        bin_end=float(i + 1) / len(cal_raw),
                        count=1,
                        avg_predicted=float(pt.get("pred", 0.0)),
                        avg_actual=float(pt.get("true", 0.0))
                    ))
            reliability_diagram = ReliabilityData(bins=reliability_bins)
            
            # ROC / PR
            roc_raw = diags.get("roc", {}).get("points", [])
            roc_points = [
                ROCPoint(fpr=float(pt.get("fpr", 0.0)), tpr=float(pt.get("tpr", 0.0)))
                for pt in roc_raw
            ]
            roc_curve = ROCData(points=roc_points, auc=diags.get("roc", {}).get("auc", 0.0))
            
            pr_raw = diags.get("pr", {}).get("points", [])
            pr_points = [
                PRPoint(precision=float(pt.get("precision", 0.0)), recall=float(pt.get("recall", 0.0)))
                for pt in pr_raw
            ]
            pr_curve = PRData(points=pr_points, auc=diags.get("pr", {}).get("auc", 0.0))
            
            # Confusion matrix
            cm_dict = diags.get("confusion_matrix", {})
            confusion_matrix = [
                [cm_dict.get("tn", 0), cm_dict.get("fp", 0)],
                [cm_dict.get("fn", 0), cm_dict.get("tp", 0)]
            ]
            
            return CalibrationDiagnostics(
                endpoint=backend.endpoint().value,
                model_id=model_id,
                test_set_size=cm_dict.get("total", 0),
                task_kind="classification",
                roc_curve=roc_curve,
                pr_curve=pr_curve,
                reliability_diagram=reliability_diagram,
                confusion_matrix=confusion_matrix,
                ad_distance_histogram=ad_histogram,
                per_chemical_class_metrics={}
            ).model_dump(mode='json')
            
    else:
        raise ValueError("Diagnostics are not supported for legacy baseline (Tier-2) models.")
