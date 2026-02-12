"""
Edeon SAR — Free-Wilson Additive SAR Regression Solver
Decomposes series compounds into core and substituent matrix, fitting c_j contribution weights.
"""

from typing import List, Dict, Any
import numpy as np
from sklearn.linear_model import Ridge
from .mmp_engine import fragment_molecule


def fit_free_wilson_model(compounds: List[Dict[str, Any]], endpoint: str = "potency") -> Dict[str, Any]:
    """Fit a Free-Wilson additive regression model across a chemical series.

    Model: y_i = mu + sum_j c_j * x_{ij}

    Args:
        compounds: List of {"smiles": str, "potency": float, ...}
        endpoint: Endpoint name key to fit against

    Returns:
        Dict containing core, substituent_coefficients, mu (mean intercept), R2, and predicted_values.
    """
    valid = [c for c in compounds if endpoint in c and c[endpoint] is not None]
    if len(valid) < 3:
        return {"ok": False, "error": "Insufficient compounds for Free-Wilson regression (minimum 3 required)"}

    # Extract all fragments
    decomp = []
    r_substituents = set()
    core_counts: Dict[str, int] = {}

    for c in valid:
        frags = fragment_molecule(c["smiles"])
        if frags:
            best_core, best_r = frags[0]
            r_substituents.add(best_r)
            core_counts[best_core] = core_counts.get(best_core, 0) + 1
            decomp.append({"smiles": c["smiles"], "y": float(c[endpoint]), "core": best_core, "r": best_r})

    if not decomp or not r_substituents:
        return {"ok": False, "error": "Could not identify a common structural core for Free-Wilson analysis"}

    dominant_core = max(core_counts.items(), key=lambda x: x[1])[0]
    r_list = sorted(list(r_substituents))
    r_idx = {r: i for i, r in enumerate(r_list)}

    # Build design matrix X and response vector y
    X = np.zeros((len(decomp), len(r_list)))
    y = np.array([d["y"] for d in decomp])

    for row_idx, d in enumerate(decomp):
        r_str = d["r"]
        if r_str in r_idx:
            X[row_idx, r_idx[r_str]] = 1.0

    # Fit Ridge regression with minor regularization
    model = Ridge(alpha=1e-3, fit_intercept=True)
    model.fit(X, y)

    y_pred = model.predict(X)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    ss_res = np.sum((y - y_pred) ** 2)
    r2 = float(1.0 - (ss_res / max(ss_tot, 1e-9)))

    coefficients = []
    for r_str, coef in zip(r_list, model.coef_):
        coefficients.append({
            "substituent": r_str,
            "coefficient": round(float(coef), 4)
        })

    # Sort coefficients descending
    coefficients.sort(key=lambda x: x["coefficient"], reverse=True)

    predictions = []
    for idx, d in enumerate(decomp):
        predictions.append({
            "smiles": d["smiles"],
            "observed": round(float(y[idx]), 4),
            "predicted": round(float(y_pred[idx]), 4),
            "residual": round(float(y[idx] - y_pred[idx]), 4)
        })

    return {
        "ok": True,
        "endpoint": endpoint,
        "dominant_core": dominant_core,
        "intercept_mu": round(float(model.intercept_), 4),
        "r2_score": round(max(0.0, min(1.0, r2)), 4),
        "substituent_coefficients": coefficients,
        "predictions": predictions,
        "n_samples": len(decomp)
    }
