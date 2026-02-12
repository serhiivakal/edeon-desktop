"""
Unit & Integration Tests for Matched Molecular Pairs & Free-Wilson SAR (Feature H2)
"""

import pytest
from edeon_sar.mmp_engine import fragment_molecule, index_matched_pairs
from edeon_sar.selectivity_transforms import suggest_selectivity_transforms
from edeon_sar.free_wilson import fit_free_wilson_model
from edeon_sar.ipc_handlers import handle_sar_mmp_index, handle_sar_mmp_suggest_transforms, handle_sar_free_wilson_fit


def test_fragment_molecule():
    frags = fragment_molecule("CC(=O)O")
    assert len(frags) >= 1
    assert any(f[0] and f[1] for f in frags)


def test_index_matched_pairs_and_selectivity():
    compounds = [
        {"id": "1", "smiles": "CC(=O)NC1=CC=CC=C1", "potency": 7.5, "off_target": 4.0},
        {"id": "2", "smiles": "CC(=O)NC1=CC=C(F)C=C1", "potency": 8.2, "off_target": 3.5},
        {"id": "3", "smiles": "CC(=O)NC1=CC=C(Cl)C=C1", "potency": 8.0, "off_target": 3.8},
        {"id": "4", "smiles": "CC(=O)NC1=CC=C(Br)C=C1", "potency": 8.4, "off_target": 3.2},
    ]

    pairs = index_matched_pairs(compounds)
    assert len(pairs) >= 1
    assert "transform" in pairs[0]

    transforms = suggest_selectivity_transforms(compounds, top_k=5)
    assert len(transforms) >= 1
    assert "mean_delta_selectivity" in transforms[0]


def test_fit_free_wilson_model():
    compounds = [
        {"id": "1", "smiles": "CC(=O)NC1=CC=CC=C1", "potency": 7.5},
        {"id": "2", "smiles": "CC(=O)NC1=CC=C(F)C=C1", "potency": 8.2},
        {"id": "3", "smiles": "CC(=O)NC1=CC=C(Cl)C=C1", "potency": 8.0},
        {"id": "4", "smiles": "CC(=O)NC1=CC=C(Br)C=C1", "potency": 8.4},
    ]

    model = fit_free_wilson_model(compounds, endpoint="potency")
    assert model["ok"] is True
    assert "substituent_coefficients" in model
    assert len(model["substituent_coefficients"]) >= 1
    assert "r2_score" in model


def test_ipc_handlers():
    compounds = [
        {"id": "1", "smiles": "CC(=O)NC1=CC=CC=C1", "potency": 7.5, "off_target": 4.0},
        {"id": "2", "smiles": "CC(=O)NC1=CC=C(F)C=C1", "potency": 8.2, "off_target": 3.5},
        {"id": "3", "smiles": "CC(=O)NC1=CC=C(Cl)C=C1", "potency": 8.0, "off_target": 3.8},
    ]

    res_idx = handle_sar_mmp_index({"compounds": compounds})
    assert res_idx["ok"] is True

    res_tr = handle_sar_mmp_suggest_transforms({"compounds": compounds})
    assert res_tr["ok"] is True

    res_fw = handle_sar_free_wilson_fit({"compounds": compounds, "endpoint": "potency"})
    assert res_fw["ok"] is True
