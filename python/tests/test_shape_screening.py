"""
Unit & Integration Tests for 3D Shape & Electrostatic Similarity Screening (Feature I4)
"""

import pytest
from edeon_shape.align import prepare_3d_conformer, calculate_shape_overlap
from edeon_shape.electrostatics import calculate_electrostatic_similarity
from edeon_shape.combo_score import screen_3d_similarity
from edeon_shape.ipc_handlers import handle_shape_screen_3d


def test_prepare_3d_conformer():
    mol = prepare_3d_conformer("CC(=O)O")
    assert mol is not None
    assert mol.GetNumConformers() >= 1


def test_calculate_shape_and_electrostatics():
    ref_mol = prepare_3d_conformer("CC(=O)NC1=CC=CC=C1")
    probe_mol = prepare_3d_conformer("CC(=O)NC1=CC=C(F)C=C1")

    assert ref_mol is not None
    assert probe_mol is not None

    shape_score, aligned = calculate_shape_overlap(probe_mol, ref_mol)
    assert 0.0 <= shape_score <= 1.0

    esp_score = calculate_electrostatic_similarity(aligned or probe_mol, ref_mol)
    assert 0.0 <= esp_score <= 1.0


def test_screen_3d_similarity():
    candidates = [
        {"id": "1", "smiles": "CC(=O)NC1=CC=C(F)C=C1"},
        {"id": "2", "smiles": "CC(=O)NC1=CC=C(Cl)C=C1"},
        {"id": "3", "smiles": "CCCCCC"},
    ]

    res = screen_3d_similarity("CC(=O)NC1=CC=CC=C1", candidates, top_k=5)
    assert len(res) >= 1
    assert "combo_score" in res[0]
    assert "shape_score" in res[0]
    assert "esp_score" in res[0]


def test_handle_shape_screen_3d():
    res = handle_shape_screen_3d({
        "reference_smiles": "CC(=O)O",
        "candidates": [{"smiles": "CCO"}, {"smiles": "CC(=O)O"}],
        "top_k": 2
    })

    assert res["ok"] is True
    assert len(res["results"]) >= 1
