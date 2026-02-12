"""
Leverage-based Applicability Domain

Designed for continuous descriptor-based featurizers.
Includes a sparsity gate to skip calculation for sparse matrices (e.g. fingerprints).
"""

from dataclasses import dataclass
import numpy as np

@dataclass
class LeverageADReference:
    available: bool
    XtX_inv: np.ndarray | None    # (p+1, p+1)
    feature_mean: np.ndarray | None
    feature_std: np.ndarray | None
    h_star: float | None          # 3*(p+1)/n critical leverage
    train_residual_std: float | None  # for standardised residuals on new data
    n_train: int

def build_leverage_reference(X_train: np.ndarray, y_train: np.ndarray,
                             y_train_pred: np.ndarray) -> LeverageADReference:
    X_train = np.asarray(X_train, dtype=float)
    y_train = np.asarray(y_train, dtype=float)
    y_train_pred = np.asarray(y_train_pred, dtype=float)
    
    n = X_train.shape[0]
    if n == 0:
        return LeverageADReference(False, None, None, None, None, None, 0)
        
    sparsity = 1.0 - np.count_nonzero(X_train) / X_train.size if X_train.size > 0 else 1.0
    if sparsity > 0.70:
        return LeverageADReference(False, None, None, None, None, None, n)
        
    mu = X_train.mean(0)
    sd = X_train.std(0) + 1e-12
    Xs = (X_train - mu) / sd
    
    Xb = np.hstack([np.ones((Xs.shape[0], 1)), Xs])           # bias column
    XtX_inv = np.linalg.pinv(Xb.T @ Xb)
    p = Xs.shape[1]
    
    h_star = 3.0 * (p + 1) / n
    resid = y_train - y_train_pred
    
    if n <= 1:
        s = float(np.std(resid))
    else:
        s = float(np.std(resid, ddof=1))
    if s == 0:
        s = 1e-12
        
    return LeverageADReference(True, XtX_inv, mu, sd, h_star, s, n)

def score_leverage(ref: LeverageADReference, X_query: np.ndarray,
                   y_query: np.ndarray | None = None,
                   y_query_pred: np.ndarray | None = None) -> dict:
    if not ref.available:
        return {"available": False}
        
    X_query = np.asarray(X_query, dtype=float)
    if X_query.ndim == 1:
        X_query = X_query.reshape(1, -1)
        
    Xs = (X_query - ref.feature_mean) / ref.feature_std
    Xb = np.hstack([np.ones((Xs.shape[0], 1)), Xs])
    leverage = np.einsum("ij,jk,ik->i", Xb, ref.XtX_inv, Xb)
    
    out = {"available": True, "leverage": leverage.tolist(), "h_star": ref.h_star}
    
    if y_query is not None and y_query_pred is not None:
        y_query = np.asarray(y_query, dtype=float)
        y_query_pred = np.asarray(y_query_pred, dtype=float)
        resid = y_query - y_query_pred
        std_resid = resid / ref.train_residual_std
        out["std_residual"] = std_resid.tolist()
        out["status"] = [
            "out" if (abs(r) > 3 or h > ref.h_star) else
            "borderline" if (abs(r) > 2.5 or h > 0.8 * ref.h_star) else
            "in"
            for r, h in zip(std_resid, leverage)
        ]
    else:
        out["status"] = [
            "out" if h > ref.h_star else
            "borderline" if h > 0.8 * ref.h_star else
            "in"
            for h in leverage
        ]
    return out
