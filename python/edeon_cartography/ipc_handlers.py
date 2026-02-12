"""
Edeon Cartography — JSON-RPC IPC Handlers
"""

from typing import Dict, Any
from .tmap_layout import compute_tmap_layout


def handle_cartography_compute_tmap(params: Dict[str, Any]) -> Dict[str, Any]:
    """Compute TMAP Minimum Spanning Tree 2D layout for a batch of compounds."""
    compounds = params.get("compounds", [])
    return compute_tmap_layout(compounds)
