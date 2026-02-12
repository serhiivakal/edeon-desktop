"""
Edeon Engine — Legacy QSAR ML Model Training Redirector

This module is retained for backwards compatibility.
It re-exports train_model_batch from the new modular .models package.
"""

from .models import train_model_batch

__all__ = ["train_model_batch"]
