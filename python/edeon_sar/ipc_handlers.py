"""
Edeon SAR — JSON-RPC IPC Handlers
"""

from typing import Dict, Any
from .mmp_engine import index_matched_pairs
from .selectivity_transforms import suggest_selectivity_transforms
from .free_wilson import fit_free_wilson_model


def handle_sar_mmp_index(params: Dict[str, Any]) -> Dict[str, Any]:
    """Index matched molecular pairs across a dataset."""
    compounds = params.get("compounds", [])
    pairs = index_matched_pairs(compounds)
    return {
        "ok": True,
        "pairs": pairs,
        "n_pairs": len(pairs)
    }


def handle_sar_mmp_suggest_transforms(params: Dict[str, Any]) -> Dict[str, Any]:
    """Suggest selectivity window-widening transforms."""
    compounds = params.get("compounds", [])
    top_k = int(params.get("top_k", 20))
    transforms = suggest_selectivity_transforms(compounds, top_k=top_k)
    return {
        "ok": True,
        "transforms": transforms,
        "n_transforms": len(transforms)
    }


def handle_sar_free_wilson_fit(params: Dict[str, Any]) -> Dict[str, Any]:
    """Fit Free-Wilson additive SAR regression model."""
    compounds = params.get("compounds", [])
    endpoint = params.get("endpoint", "potency")
    return fit_free_wilson_model(compounds, endpoint=endpoint)
