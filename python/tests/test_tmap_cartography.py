"""
Unit & Integration Tests for Chemical-Space Cartography (Feature J7)
"""

import pytest
from edeon_cartography.tmap_layout import compute_tmap_layout
from edeon_cartography.ipc_handlers import handle_cartography_compute_tmap


def test_compute_tmap_layout():
    compounds = [
        {"id": "1", "smiles": "CC(=O)NC1=CC=CC=C1", "name": "Acetanilide"},
        {"id": "2", "smiles": "CC(=O)NC1=CC=C(F)C=C1", "name": "4-Fluoroacetanilide"},
        {"id": "3", "smiles": "CC(=O)NC1=CC=C(Cl)C=C1", "name": "4-Chloroacetanilide"},
        {"id": "4", "smiles": "CC(=O)NC1=CC=C(Br)C=C1", "name": "4-Bromoacetanilide"},
    ]

    res = compute_tmap_layout(compounds)
    assert res["ok"] is True
    assert "nodes" in res
    assert "edges" in res
    assert len(res["nodes"]) == 4

    for node in res["nodes"]:
        assert "x" in node
        assert "y" in node
        assert "smiles" in node


def test_handle_cartography_compute_tmap():
    compounds = [
        {"id": "1", "smiles": "CC(=O)O"},
        {"id": "2", "smiles": "CCO"}
    ]

    res = handle_cartography_compute_tmap({"compounds": compounds})
    assert res["ok"] is True
    assert len(res["nodes"]) == 2
