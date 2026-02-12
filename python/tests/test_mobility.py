"""
Unit & Integration Tests for Systemic Mobility (Feature J8)
"""

import pytest

from edeon_engine.mobility.kleier import calculate_kleier_indices
from edeon_engine.mobility.bromilow import calculate_bromilow_cf
from edeon_engine.mobility.classify import classify_systemic_mobility
from edeon_engine.mobility.ipc_handlers import handle_mobility_predict


def test_calculate_kleier_indices():
    log_pm, xylem_idx, phloem_idx = calculate_kleier_indices(log_kow=1.5, mw=250.0, pka=4.5)
    assert -8.5 <= log_pm <= -5.0
    assert xylem_idx > 0.5
    assert phloem_idx > 0.5


def test_calculate_bromilow_cf():
    # Weak acid pKa 4.5
    cf = calculate_bromilow_cf(pka_values=[4.5], ph_apoplast=5.5, ph_phloem=8.0)
    assert cf > 10.0

    # Neutral compound (no pKa)
    cf_neutral = calculate_bromilow_cf(pka_values=None)
    assert cf_neutral == 1.0


def test_classify_systemic_mobility_24d():
    # 2,4-D SMILES: CC(O)=O or phenoxyacetic acid derivative CC1=C(Cl)C=C(Cl)C=C1OCC(=O)O
    smiles_24d = "CC1=C(Cl)C=C(Cl)C=C1OCC(=O)O"
    res = classify_systemic_mobility(smiles_24d)

    assert res["ok"] is True
    assert res["class"] in ("phloem", "ambimobile")
    assert res["phloem_concentration_factor"] > 1.0
    assert res["confidence"] in ("in_domain", "edge")


def test_handle_mobility_predict():
    res = handle_mobility_predict({
        "smiles": "CC1=C(Cl)C=C(Cl)C=C1OCC(=O)O",
        "ph_apoplast": 5.5,
        "ph_phloem": 8.0,
    })
    assert res["ok"] is True
    assert "class" in res
    assert "drivers" in res
