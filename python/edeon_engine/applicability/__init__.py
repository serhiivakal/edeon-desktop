"""
Applicability Domain (AD) Orchestrator

Integrates:
  1. Tanimoto-based k-NN similarity bounding (Morgan 2048-bit FPs)
  2. Leverage-based density check (standardized descriptors)
"""

from dataclasses import dataclass
import numpy as np

from .tanimoto import TanimotoADReference, build_tanimoto_reference, score_tanimoto
from .leverage import LeverageADReference, build_leverage_reference, score_leverage

@dataclass
class ApplicabilityDomain:
    tanimoto: TanimotoADReference
    leverage: LeverageADReference
    schema_version: int = 1

def build_ad_reference(train_smiles: list[str], X_train: np.ndarray, y_train: np.ndarray,
                        y_train_pred: np.ndarray) -> ApplicabilityDomain:
    """Builds combined Applicability Domain reference on training set."""
    X_train = np.asarray(X_train, dtype=float)
    y_train = np.asarray(y_train, dtype=float)
    y_train_pred = np.asarray(y_train_pred, dtype=float)
    
    tanimoto_ref = build_tanimoto_reference(train_smiles)
    leverage_ref = build_leverage_reference(X_train, y_train, y_train_pred)
    
    return ApplicabilityDomain(
        tanimoto=tanimoto_ref,
        leverage=leverage_ref
    )

def score_query(ad: ApplicabilityDomain, query_smiles: list[str], X_query: np.ndarray,
                y_query: np.ndarray | None = None, y_query_pred: np.ndarray | None = None) -> dict:
    """Evaluates applicability domain status for query compounds.
    
    Returns:
      {
        'overall_status': ['in'|'borderline'|'out'|'invalid'] * n,
        'tanimoto': {...},
        'leverage': {...} or {'available': False}
      }
    """
    X_query = np.asarray(X_query, dtype=float)
    
    tanimoto_scores = score_tanimoto(ad.tanimoto, query_smiles)
    leverage_scores = score_leverage(ad.leverage, X_query, y_query, y_query_pred)
    
    overall_status = []
    n = len(query_smiles)
    
    # Grab leverage statuses if available
    lev_statuses = leverage_scores.get("status", [None] * n) if leverage_scores.get("available") else [None] * n
    
    for t_stat, l_stat in zip(tanimoto_scores["status"], lev_statuses):
        if t_stat == "invalid":
            overall_status.append("invalid")
        elif l_stat is None:
            # Leverage is not available or skipped
            overall_status.append(t_stat)
        elif t_stat == "out" or l_stat == "out":
            overall_status.append("out")
        elif t_stat == "borderline" or l_stat == "borderline":
            overall_status.append("borderline")
        else:
            overall_status.append("in")
            
    return {
        "overall_status": overall_status,
        "tanimoto": tanimoto_scores,
        "leverage": leverage_scores
    }

# Backwards compatibility shims
def score_ad(ad_reference, X, smiles):
    """Placeholder evaluator for older scaffold code, mapping to score_query."""
    if hasattr(ad_reference, "tanimoto"):
        scores = score_query(ad_reference, smiles, X)
        return [{"in_ad": status in ("in", "borderline"), "score": 1.0 if status == "in" else 0.6 if status == "borderline" else 0.2, "reason": status} for status in scores["overall_status"]]
    # Fallback legacy scaffold return
    return [{"in_ad": True, "score": 1.0, "reason": None} for _ in X]
