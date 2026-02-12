"""
Edeon Engine — Models Package

Modular QSAR machine learning framework.
Exposes train_model_batch for backward compatibility.
"""

from .trainers import train_model_batch
from .featurizers import FEATURIZER_REGISTRY, run_featurizers
from .estimators import build_estimator

__all__ = ["train_model_batch", "FEATURIZER_REGISTRY", "run_featurizers", "build_estimator"]
