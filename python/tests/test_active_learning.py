"""
Unit & Integration Tests for Bayesian Optimization Active Learning (Feature K10)
"""

import pytest
from edeon_active_learning.surrogate_gp import fit_gp_surrogate
from edeon_active_learning.acquisition import compute_expected_improvement, compute_ucb
from edeon_active_learning.loop import suggest_active_learning_batch
from edeon_active_learning.ipc_handlers import handle_al_suggest_next_batch


def test_fit_gp_surrogate():
    train_smiles = ["CC(=O)O", "CCO", "CCCO", "CCCCO"]
    train_y = [5.0, 6.0, 7.0, 7.5]
    candidate_smiles = ["CC(=O)NC1=CC=CC=C1", "CCCCCO"]

    means, stds, r2 = fit_gp_surrogate(train_smiles, train_y, candidate_smiles)
    assert len(means) == 2
    assert len(stds) == 2
    assert r2 >= 0.0


def test_suggest_active_learning_batch():
    labeled = [
        {"smiles": "CC(=O)NC1=CC=CC=C1", "potency": 7.5},
        {"smiles": "CC(=O)NC1=CC=C(F)C=C1", "potency": 8.2},
        {"smiles": "CC(=O)NC1=CC=C(Cl)C=C1", "potency": 8.0},
    ]
    candidates = [
        {"smiles": "CC(=O)NC1=CC=C(Br)C=C1"},
        {"smiles": "CC(=O)NC1=CC=C(I)C=C1"},
        {"smiles": "CCCCCC"},
    ]

    res = suggest_active_learning_batch(labeled, candidates, acquisition="ei", batch_size=2)
    assert res["ok"] is True
    assert len(res["suggested_batch"]) == 2
    assert res["acquisition_method"] == "EI"
    assert "r2_score" in res["model_metrics"]


def test_handle_al_suggest_next_batch():
    labeled = [{"smiles": "CC(=O)O", "potency": 5.0}, {"smiles": "CCO", "potency": 6.0}]
    candidates = [{"smiles": "CCCO"}, {"smiles": "CCCCO"}]

    res = handle_al_suggest_next_batch({
        "labeled_pool": labeled,
        "candidate_pool": candidates,
        "acquisition": "ucb",
        "batch_size": 1
    })

    assert res["ok"] is True
    assert len(res["suggested_batch"]) == 1
    assert res["acquisition_method"] == "UCB"
