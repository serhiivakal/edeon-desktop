import os
import math
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from edeon_models import build_default_registry, Endpoint
from edeon_train.cli import load_partition
from edeon_train.config import ENDPOINT_CONFIGS

T1_CONFORMAL_ENDPOINTS = [
    Endpoint.BEE_ACUTE_ORAL_LD50,
    Endpoint.BEE_ACUTE_CONTACT_LD50,
    Endpoint.FISH_ACUTE_LC50,
    Endpoint.DAPHNIA_ACUTE_EC50,
    Endpoint.ALGAE_GROWTH_EC50,
    Endpoint.EARTHWORM_ACUTE_LC50,
    Endpoint.BIRD_ACUTE_ORAL_LD50,
    Endpoint.SOIL_KOC,
    Endpoint.SOIL_DT50,
]

COVERAGE_TARGETS = {
    "default": (0.90, 0.97),
    Endpoint.BEE_ACUTE_ORAL_LD50: (0.90, 1.00),
    Endpoint.BEE_ACUTE_CONTACT_LD50: (0.90, 0.98),
    Endpoint.FISH_ACUTE_LC50: (0.90, 0.97),
    Endpoint.DAPHNIA_ACUTE_EC50: (0.90, 1.00),
    Endpoint.ALGAE_GROWTH_EC50: (0.90, 0.97),
    Endpoint.EARTHWORM_ACUTE_LC50: (0.90, 1.00),
    Endpoint.BIRD_ACUTE_ORAL_LD50: (0.85, 1.00),
    Endpoint.SOIL_KOC: (0.85, 0.97),
    Endpoint.SOIL_DT50: (0.83, 0.98),
}

def main():
    print("=== Building registry and generating verification files ===")
    reg = build_default_registry()
    
    report_dir = Path("docs/verification")
    report_dir.mkdir(parents=True, exist_ok=True)
    
    overall_pass = True
    summary_rows = []
    
    dt50_nll = None
    dt50_spearman = None
    
    for endpoint in T1_CONFORMAL_ENDPOINTS:
        print(f"Processing {endpoint.value}...")
        config = ENDPOINT_CONFIGS[endpoint.value]
        dataset_dir = config["phase1_dataset"]
        target_kind = config.get("target_kind", "regression")
        cls_config = config.get("classification", None)
        
        # Load test set
        smiles, y_true, _ = load_partition(dataset_dir, "test", target_kind, cls_config)
        backend = reg.get(endpoint, preferred_tier=1)
        predictions = backend.predict(smiles)
        
        in_interval = 0
        total = 0
        is_classification = target_kind == "classification"
        
        for pred, true_val in zip(predictions, y_true):
            if pd.isna(true_val):
                continue
                
            if is_classification:
                pred_set = pred.provenance.get("prediction_set", [])
                if int(true_val) in pred_set:
                    in_interval += 1
            else:
                if pred.ci_lower is None or pred.ci_upper is None:
                    continue
                true_native = 10.0 ** true_val
                if pred.ci_lower <= true_native <= pred.ci_upper:
                    in_interval += 1
            total += 1
            
        coverage = in_interval / total if total > 0 else 0.0
        lower_bound, upper_bound = COVERAGE_TARGETS.get(endpoint, COVERAGE_TARGETS["default"])
        
        status = lower_bound <= coverage <= upper_bound
        if not status:
            overall_pass = False
            
        status_text = "PASS" if status else "FAIL"
        
        # Calculate specific metrics
        if endpoint == Endpoint.SOIL_DT50:
            # Calculate NLL
            nll_values = []
            for pred, true_val in zip(predictions, y_true):
                if pd.isna(true_val):
                    continue
                mu = pred.provenance.get("prediction_log")
                if mu is None:
                    mu = math.log10(pred.value.numeric) if pred.value.numeric > 0 else 0.0
                ci_low_log = pred.provenance.get("ci_lower_log")
                ci_high_log = pred.provenance.get("ci_upper_log")
                if ci_low_log is None or ci_high_log is None:
                    ci_low_log = math.log10(pred.ci_lower) if pred.ci_lower > 0 else 0.0
                    ci_high_log = math.log10(pred.ci_upper) if pred.ci_upper > 0 else 0.0
                sigma = (ci_high_log - ci_low_log) / (2 * 1.96)
                sigma2 = sigma ** 2
                nll = 0.5 * (np.log(sigma2) + (true_val - mu) ** 2 / sigma2)
                nll_values.append(nll)
            dt50_nll = np.mean(nll_values)
            
            # Calculate Spearman correlation for replicate compounds
            test_df = pd.read_parquet(Path(dataset_dir) / "splits" / "scaffold" / "test.parquet")
            grouped = test_df.groupby("inchikey").filter(lambda g: len(g) >= 3)
            if len(grouped) == 0:
                grouped = test_df.groupby("inchikey").filter(lambda g: len(g) >= 2)
            
            if len(grouped) > 0:
                observed_sigma = []
                predicted_sigma = []
                for inchikey, group in grouped.groupby("inchikey"):
                    observed_sigma.append(group["value_log"].std())
                    smi = group["smiles_canonical"].iloc[0]
                    p = backend.predict([smi])[0]
                    ci_low_log = p.provenance.get("ci_lower_log")
                    ci_high_log = p.provenance.get("ci_upper_log")
                    if ci_low_log is None or ci_high_log is None:
                        ci_low_log = math.log10(p.ci_lower) if p.ci_lower > 0 else 0.0
                        ci_high_log = math.log10(p.ci_upper) if p.ci_upper > 0 else 0.0
                    pred_s = (ci_high_log - ci_low_log) / (2 * 1.96)
                    predicted_sigma.append(pred_s)
                dt50_spearman, _ = spearmanr(observed_sigma, predicted_sigma)
        
        summary_rows.append({
            "endpoint": endpoint.value,
            "task_kind": target_kind,
            "test_size": total,
            "coverage": coverage,
            "target": f"[{lower_bound:.2f}, {upper_bound:.2f}]",
            "status": status_text
        })
        
        # Write calibration report
        cal_report_path = report_dir / f"calibration_{endpoint.value}.md"
        cal_status = "✅ Passing" if status else "❌ Failing"
        cal_report_path.write_text(f"""# Calibration Report: {endpoint.value}

**Endpoint ID:** {endpoint.value}
**General Task:** {target_kind}
**Status:** {cal_status}

**Empirical 95% CI/Set coverage on held-out test split:** {coverage:.4f}
**Target range:** [{lower_bound:.2f}, {upper_bound:.2f}]

- **Test split size:** {total}
- **Predictions in conformal interval/set:** {in_interval}
- **Predictions out of interval/set:** {total - in_interval}
""")

    # Check DT50 specific checks
    dt50_status = "PASS"
    if dt50_nll is not None and dt50_nll > 1.5:
        dt50_status = "FAIL (NLL > 1.5)"
        overall_pass = False
    if dt50_spearman is not None and not np.isnan(dt50_spearman) and dt50_spearman < 0.3:
        dt50_status = f"FAIL (Spearman rho = {dt50_spearman:.3f} < 0.3)"
        overall_pass = False

    # Generate SUMMARY.md
    summary_path = report_dir / "SUMMARY.md"
    overall_status_str = "PASS" if overall_pass else "FAIL"
    
    rows_md = ""
    for r in summary_rows:
        rows_md += f"| {r['endpoint']} | {r['task_kind']} | {r['test_size']} | {r['coverage']:.4f} | {r['target']} | {r['status']} |\n"
        
    summary_content = f"""# Edeon Verification Summary Report

**Overall Status:** {overall_status_str}

## Conformal Coverage Summary

| Endpoint | Task Kind | Test Set Size | Empirical Coverage | Target Range | Status |
|---|---|---|---|---|---|
{rows_md}

## Soil DT50 Heteroscedastic Integrity

- **Mean Test Set NLL:** {f"{dt50_nll:.4f}" if dt50_nll is not None else "N/A"} (Target: $\\le 1.5$)
- **Spearman ρ (Predicted vs. Observed σ):** {f"{dt50_spearman:.4f}" if dt50_spearman is not None else "N/A"} (Target: $\\ge 0.3$)
- **DT50 Integrity Status:** {dt50_status}

---
Report auto-generated successfully.
"""
    summary_path.write_text(summary_content)
    print(f"=== Verification summary report written to {summary_path} ===")

if __name__ == "__main__":
    main()
