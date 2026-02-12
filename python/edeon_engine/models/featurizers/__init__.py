"""
Edeon Engine — Featurizers Registry
Combines and orchestrates advanced chemistry-aware featurization pipelines.
"""

import numpy as np
from .base import FEATURIZER_REGISTRY, FeaturizerSpec, register

# Import all submodules to trigger automatic registration at import time
from . import descriptors_2d
from . import fingerprints
from . import pharmacophore
from . import custom

# Re-exports for backwards compatibility
from .descriptors_2d import extract_descriptors
from .fingerprints import compute_morgan_fingerprints

def _legacy_features_to_selections(legacy_features):
    selections = []
    for f in legacy_features:
        if f.startswith("morgan_"):
            parts = f.split("_")
            radius = int(parts[1]) if len(parts) > 1 else 2
            n_bits = int(parts[2]) if len(parts) > 2 else 2048
            selections.append({"id": "morgan", "params": {"radius": radius, "n_bits": n_bits}})
        elif f in ("descriptors_basic", "descriptors_2d"):
            from .descriptors_2d import LIPINSKI
            selections.append({"id": "descriptors_2d", "params": {"selected": list(LIPINSKI)}})
    if not selections:
        from .descriptors_2d import LIPINSKI
        selections.append({"id": "descriptors_2d", "params": {"selected": list(LIPINSKI)}})
    return selections

def run_featurizers(smiles: list[str], selections: list[dict] = None) -> tuple[np.ndarray, list[str]]:
    """
    selections = [
        {"id": "morgan", "params": {"radius": 2, "n_bits": 2048}},
        {"id": "descriptors_2d", "params": {"selected": ["MolWt","MolLogP", ...]}},
        ...
    ]
    Returns (X, feature_names) — concatenated horizontally in the order given.
    """
    if not smiles:
        return np.zeros((0, 0)), []
        
    if not selections:
        from .descriptors_2d import LIPINSKI
        selections = [{"id": "descriptors_2d", "params": {"selected": list(LIPINSKI)}}]
        
    matrices = []
    feature_names = []
    
    for sel in selections:
        sel_id = sel.get("id")
        params = sel.get("params", {})
        
        spec = FEATURIZER_REGISTRY.get(sel_id)
        if spec is None:
            continue
            
        matrix = spec.compute(smiles, params)
        matrices.append(matrix)
        
        # Build feature names
        dim = matrix.shape[1]
        if sel_id == "descriptors_2d":
            selected_names = params.get("selected", [])
            feature_names.extend(selected_names)
        elif sel_id == "custom":
            feature_names.extend([f"custom:{i}" for i in range(dim)])
        else:
            if sel_id == "morgan" or sel_id == "fcfp":
                radius = params.get("radius", 2)
                feature_names.extend([f"{sel_id}_{radius}:{i}" for i in range(dim)])
            else:
                feature_names.extend([f"{sel_id}:{i}" for i in range(dim)])
            
    if not matrices:
        return np.zeros((len(smiles), 0)), []
        
    X = np.hstack(matrices)
    return X, feature_names
