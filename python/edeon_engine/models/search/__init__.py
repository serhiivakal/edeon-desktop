"""
Edeon Engine — Search
Hyperparameter search packages supporting Grid Search and Optuna Bayesian Optimization.
"""

def primary_metric_name(model_type: str) -> str:
    """Returns the primary metric key based on model target."""
    return "r2_val" if model_type == "regression" else "accuracy_val"

from .grid import grid_search
from .bayesian import bayesian_search

