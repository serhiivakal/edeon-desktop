"""
Edeon Engine — Model Interpretability Submodule
"""

from .shap_explainer import explain_model, standardised_coefficients, explain_single
from .atom_maps import compute_morgan_with_bitinfo, project_bits_to_atoms, render_contribution_png

__all__ = [
    "explain_model",
    "standardised_coefficients",
    "explain_single",
    "compute_morgan_with_bitinfo",
    "project_bits_to_atoms",
    "render_contribution_png"
]
