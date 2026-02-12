"""
Edeon Engine — Mobility JSON-RPC Handler
"""

from typing import Dict, Any
from .classify import classify_systemic_mobility


def handle_mobility_predict(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for mobility.predict.

    params: { "smiles": str, "ph_apoplast": float, "ph_phloem": float }
    """
    smiles = params.get("smiles", "")
    ph_apoplast = float(params.get("ph_apoplast", 5.5))
    ph_phloem = float(params.get("ph_phloem", 8.0))

    return classify_systemic_mobility(smiles, ph_apoplast, ph_phloem)
