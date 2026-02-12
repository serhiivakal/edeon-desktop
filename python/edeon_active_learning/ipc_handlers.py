"""
Edeon Active Learning — JSON-RPC IPC Handlers
"""

from typing import Dict, Any
from .loop import suggest_active_learning_batch


def handle_al_suggest_next_batch(params: Dict[str, Any]) -> Dict[str, Any]:
    """Suggest the next optimal compound batch for synthesis using Bayesian Optimization."""
    labeled_pool = params.get("labeled_pool", [])
    candidate_pool = params.get("candidate_pool", [])
    acquisition = params.get("acquisition", "ei")
    batch_size = int(params.get("batch_size", 10))
    endpoint = params.get("endpoint", "potency")

    return suggest_active_learning_batch(
        labeled_pool,
        candidate_pool,
        acquisition=acquisition,
        batch_size=batch_size,
        endpoint=endpoint
    )
