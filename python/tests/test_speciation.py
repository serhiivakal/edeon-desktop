"""
Unit & Integration Tests for pH-Dependent Speciation (Feature G5)
"""

import os
import sqlite3
import tempfile
import pytest

from edeon_engine.speciation.enumerate import enumerate_protonation_states
from edeon_engine.speciation.pka import estimate_pka
from edeon_engine.speciation.microspecies import calculate_fractional_populations
from edeon_engine.speciation.ipc_handlers import (
    handle_speciation_enumerate,
    handle_speciation_dominant_at_ph,
    handle_speciation_profile_curve,
)


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE speciation_cache (
            input_inchikey TEXT NOT NULL,
            ph_target      REAL NOT NULL,
            payload_json   TEXT NOT NULL,
            created_at     TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (input_inchikey, ph_target)
        );
        """
    )
    conn.commit()
    conn.close()

    yield path

    if os.path.exists(path):
        os.remove(path)


def test_enumerate_protonation_states():
    # Carboxylic acid (acetic acid)
    variants, method = enumerate_protonation_states("CC(=O)O", ph_min=4.0, ph_max=8.0)
    assert len(variants) >= 1
    assert any(v["charge"] in (0, -1) for v in variants)


def test_estimate_pka():
    pkas = estimate_pka("CC(=O)O")
    assert pkas is not None
    assert 4.5 in pkas


def test_calculate_fractional_populations():
    variants = [{"smiles": "CC(=O)O", "charge": 0}, {"smiles": "CC(=O)[O-]", "charge": -1}]
    pkas = [4.5]

    # At low pH (2.0), neutral species dominant
    pop_low = calculate_fractional_populations(variants, ph_target=2.0, pka_values=pkas)
    neut_low = next(p for p in pop_low if p["charge"] == 0)
    assert neut_low["fraction_at_target"] > 0.9
    assert neut_low["dominant"] is True

    # At high pH (8.0), deprotonated species dominant
    pop_high = calculate_fractional_populations(variants, ph_target=8.0, pka_values=pkas)
    dep_high = next(p for p in pop_high if p["charge"] == -1)
    assert dep_high["fraction_at_target"] > 0.9
    assert dep_high["dominant"] is True


def test_handle_speciation_enumerate(temp_db):
    res = handle_speciation_enumerate({
        "smiles": "CC(=O)O",
        "ph_min": 4.0,
        "ph_max": 8.0,
        "ph_target": 6.5,
        "db_path": temp_db,
    })

    assert res["ok"] is True
    assert "input_inchikey" in res
    assert len(res["microspecies"]) >= 1

    # Verify cached
    res_cached = handle_speciation_enumerate({
        "smiles": "CC(=O)O",
        "ph_target": 6.5,
        "db_path": temp_db,
    })
    assert res_cached["input_inchikey"] == res["input_inchikey"]


def test_handle_speciation_dominant_at_ph():
    dom = handle_speciation_dominant_at_ph({"smiles": "CC(=O)O", "ph": 7.0})
    assert dom["ok"] is True
    assert "smiles" in dom
    assert "charge" in dom
    assert "fraction" in dom


def test_handle_speciation_profile_curve():
    curve = handle_speciation_profile_curve({"smiles": "CC(=O)O", "ph_min": 4.0, "ph_max": 9.0, "steps": 6})
    assert curve["ok"] is True
    assert len(curve["series"]) == 6
    assert curve["series"][0]["ph"] == 4.0
    assert curve["series"][-1]["ph"] == 9.0
