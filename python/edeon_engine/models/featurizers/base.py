"""
Edeon Engine — Featurizer Base
Defines the FeaturizerSpec dataclass and global registration utility to avoid circular imports.
"""

from dataclasses import dataclass
from typing import Callable, Literal
import numpy as np

@dataclass
class FeaturizerSpec:
    id: str                              # e.g. 'morgan'
    category: Literal['descriptors_2d','fingerprints','pharmacophore','custom']
    label: str                           # UI label
    description: str                     # tooltip
    dimensionality: Callable[[dict], int]  # given params → output width
    cost_estimate: Callable[[dict, int], float]  # params, n_compounds → seconds
    compute: Callable[[list, dict], np.ndarray]  # smiles list, params → matrix
    param_schema: dict                   # JSON-schema-ish for UI form generation
    default_params: dict

FEATURIZER_REGISTRY: dict[str, FeaturizerSpec] = {}

def register(spec: FeaturizerSpec):
    FEATURIZER_REGISTRY[spec.id] = spec
