[build-system]
requires = ["setuptools>=61.0.0", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
packages = ["edeon_data", "edeon_train", "edeon_engine", "edeon_models", "edeon_docking", "edeon_app_meta", "edeon_knowledge", "edeon_generation", "edeon_bioisostere"]

[project]
name = "edeon_engine"
version = "0.1.0"
description = "Edeon Engine - Cheminformatics and QSAR modeling backend"
requires-python = ">=3.10"
dependencies = [
    "rdkit>=2024.3.1",
    "xgboost>=2.0",
    "lightgbm>=4.0",
    "optuna>=3.5",
    "imbalanced-learn>=0.12",
    "shap>=0.45",
    "matplotlib>=3.8",
    "scipy>=1.11"
]

[project.optional-dependencies]
speciation = ["dimorphite-dl"]
shape      = ["espsim"]
sar        = ["mmpdb"]
retro      = ["aizynthfinder", "onnxruntime"]
cartography= ["tmap", "faerun"]
optimize   = ["botorch", "gpytorch", "torch"]

[project.scripts]
edeon-train = "edeon_train.cli:main"
