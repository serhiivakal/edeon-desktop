"""
Unit & Integration Tests for Reaction-Based Combinatorial Enumeration (Feature I9)
"""

import pytest
from edeon_generation.reaction_enum import load_reaction_templates, enumerate_reaction_products
from edeon_generation.ipc_handlers import handle_reaction_list_templates, handle_reaction_enumerate


def test_load_reaction_templates():
    templates = load_reaction_templates()
    assert len(templates) >= 4
    ids = [t["id"] for t in templates]
    assert "amide_coupling" in ids
    assert "suzuki_coupling" in ids


def test_enumerate_reaction_products_amide():
    # Amide coupling test: carboxylic acid + amine
    res = enumerate_reaction_products(
        template_id="amide_coupling",
        core_smiles="CC(=O)O",
        reagents=["CCN", "NC1=CC=CC=C1"],
        max_products=50,
        apply_filters={"tice": False, "pains": False},
        retro_gate={"enabled": True, "sa_threshold": 0.4}
    )

    assert res["ok"] is True
    assert res["n_generated"] > 0
    assert res["n_passed"] > 0
    assert all("feasibility_score" in p for p in res["products"])
    assert all("tier" in p for p in res["products"])


def test_handle_reaction_list_templates():
    res = handle_reaction_list_templates({})
    assert res["ok"] is True
    assert len(res["templates"]) >= 4


def test_handle_reaction_enumerate():
    res = handle_reaction_enumerate({
        "template_id": "suzuki_coupling",
        "max_products": 20
    })
    assert res["ok"] is True
    assert "products" in res
