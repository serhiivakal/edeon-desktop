"""
Unit & Integration Tests for Retrosynthesis & Synthesizability Gating (Feature G1)
"""

import pytest

from edeon_retro.sascore import calculate_sascore, calculate_sascore_batch
from edeon_retro.feasibility import compute_feasibility
from edeon_retro.ipc_handlers import (
    handle_retro_sascore,
    handle_retro_route_search,
    handle_retro_gate_batch,
)


def test_calculate_sascore():
    # Simple aspirin molecule (easy to make, high SA score)
    score_aspirin = calculate_sascore("CC(=O)OC1=CC=CC=C1C(=O)O")
    assert 0.6 <= score_aspirin <= 1.0

    # Complex macrolide / polycycle (difficult to make, low SA score)
    score_complex = calculate_sascore("C1CC2CC3CC(C1)C23")
    assert score_complex < score_aspirin


def test_compute_feasibility():
    score, tier = compute_feasibility(sa_score=0.8, solved=True, leaves_in_stock_frac=1.0, n_steps=1)
    assert score >= 0.70
    assert tier == "green"

    score_low, tier_low = compute_feasibility(sa_score=0.2, solved=False, leaves_in_stock_frac=0.0, n_steps=5)
    assert score_low < 0.45
    assert tier_low == "red"


def test_handle_retro_sascore():
    res = handle_retro_sascore({"smiles": ["CC(=O)O", "CCN"]})
    assert res["ok"] is True
    assert len(res["scores"]) == 2
    assert all("sa_score" in s for s in res["scores"])


def test_handle_retro_route_search():
    res = handle_retro_route_search({"smiles": "CC(=O)OC1=CC=CC=C1C(=O)O"})
    assert res["ok"] is True
    assert "feasibility_score" in res
    assert "tier" in res
    assert "route_tree" in res
    assert "building_blocks" in res


def test_handle_retro_gate_batch():
    res = handle_retro_gate_batch({
        "smiles": ["CC(=O)O", "CCN", "C1CC2CC3CC(C1)C23"],
        "sa_threshold": 0.4,
        "route_search_top_k": 2
    })
    assert res["ok"] is True
    assert len(res["results"]) == 3
    assert all("tier" in r for r in res["results"])
