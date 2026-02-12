"""
Unit & Integration Tests for Environmental Metabolism Expansion (Feature I6)
"""

import pytest
from edeon_engine.transformation.environmental_rules import get_environmental_rules
from edeon_engine.transformation.environmental import rescore_metabolite_nodes
from edeon_engine.transformation.pathway import predict_transformation_pathway


def test_get_environmental_rules():
    rules = get_environmental_rules(["soil_microbial", "photolysis", "hydrolysis"])
    assert len(rules) >= 5
    classes = set(r["class"] for r in rules)
    assert "soil_microbial" in classes
    assert "hydrolysis" in classes


def test_predict_transformation_pathway_environmental():
    # Test amide ester derivative with soil microbial + hydrolysis
    res = predict_transformation_pathway(
        smiles="CC(=O)OC1=CC=CC=C1C(=O)O",
        routes=["metabolic", "abiotic"],
        max_depth=2,
        sources=["soil_microbial", "hydrolysis"],
        ph=6.5
    )

    assert "nodes" in res
    assert "edges" in res
    assert len(res["nodes"]) >= 1

    # Check node metadata schema
    for node in res["nodes"]:
        assert "source" in node
        assert "liability_flag" in node
        assert "fate" in node
        assert "tox" in node


def test_rescore_metabolite_nodes():
    nodes = [
        {"smiles": "CC(=O)O"},
        {"smiles": "OC1=CC=CC=C1"}
    ]
    rescored = rescore_metabolite_nodes(nodes, parent_smiles="CC(=O)OC1=CC=CC=C1")
    assert len(rescored) == 2
    assert "liability_flag" in rescored[0]
    assert "rescored" in rescored[0]
