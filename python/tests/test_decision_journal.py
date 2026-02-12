"""
Tests for Edeon Decision Journal analytics (Phase M).

Tests build_lineage and compute_override_analytics against a temporary
SQLite database populated with sample decision_journal schema rows.
"""

import os
import sqlite3
import tempfile
import pytest

from edeon_engine.journal_analytics import build_lineage, compute_override_analytics
from edeon_engine.journal_payload import (
    build_rationale,
    build_alternatives,
    build_confidence,
    build_provenance,
)


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database initialized with decision_journal schema."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE projects (
            id TEXT PRIMARY KEY
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE decision_journal (
            entry_id      TEXT PRIMARY KEY,
            project_id    TEXT NOT NULL,
            created_at    TEXT NOT NULL,
            actor         TEXT NOT NULL CHECK (actor IN ('system','user')),
            decision_kind TEXT NOT NULL,
            subject_type  TEXT NOT NULL,
            subject_id    TEXT NOT NULL,
            summary       TEXT NOT NULL,
            rationale_json     TEXT,
            alternatives_json  TEXT,
            confidence_json    TEXT,
            provenance_json    TEXT NOT NULL,
            override_of   TEXT REFERENCES decision_journal(entry_id),
            supersedes_id TEXT REFERENCES decision_journal(entry_id),
            user_note     TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );
        """
    )
    conn.execute("INSERT INTO projects VALUES ('proj_1');")
    conn.commit()
    conn.close()

    yield path

    if os.path.exists(path):
        os.remove(path)


def test_build_lineage(temp_db):
    """Test lineage chain creation for a compound across multiple events."""
    conn = sqlite3.connect(temp_db)
    conn.execute(
        """
        INSERT INTO decision_journal (entry_id, project_id, created_at, actor, decision_kind, subject_type, subject_id, summary, rationale_json, alternatives_json, confidence_json, provenance_json, override_of, supersedes_id, user_note)
        VALUES 
        ('entry_1', 'proj_1', '2026-07-01T10:00:00Z', 'system', 'analog_registered', 'compound', 'cmpd_100', 'Registered analog', NULL, NULL, NULL, '{}', NULL, NULL, NULL),
        ('entry_2', 'proj_1', '2026-07-01T11:00:00Z', 'system', 'workflow_verdict', 'compound', 'cmpd_100', 'Passed workflow gates', NULL, NULL, NULL, '{}', NULL, NULL, NULL),
        ('entry_3', 'proj_1', '2026-07-01T12:00:00Z', 'user', 'manual_override', 'compound', 'cmpd_100', 'User override recommendation', NULL, NULL, NULL, '{}', 'entry_2', NULL, 'Note');
        """
    )
    conn.commit()
    conn.close()

    res = build_lineage(temp_db, "proj_1", "cmpd_100")
    assert res["compound_id"] == "cmpd_100"
    assert res["project_id"] == "proj_1"
    assert res["n_entries"] == 3
    assert [e["entry_id"] for e in res["entries"]] == ["entry_1", "entry_2", "entry_3"]


def test_compute_override_analytics(temp_db):
    """Test override analytics calculations (by_kind, rates, totals)."""
    conn = sqlite3.connect(temp_db)
    conn.execute(
        """
        INSERT INTO decision_journal (entry_id, project_id, created_at, actor, decision_kind, subject_type, subject_id, summary, rationale_json, alternatives_json, confidence_json, provenance_json, override_of, supersedes_id, user_note)
        VALUES 
        ('rec_1', 'proj_1', '2026-07-01T10:00:00Z', 'system', 'model_selected', 'model', 'm1', 'System selected model M1', NULL, NULL, NULL, '{}', NULL, NULL, NULL),
        ('rec_2', 'proj_1', '2026-07-01T10:05:00Z', 'system', 'model_selected', 'model', 'm2', 'System selected model M2', NULL, NULL, NULL, '{}', NULL, NULL, NULL),
        ('rec_3', 'proj_1', '2026-07-01T10:10:00Z', 'system', 'transform_applied', 'compound', 'c1', 'Applied bioisostere', NULL, NULL, NULL, '{}', NULL, NULL, NULL),
        ('ov_1',  'proj_1', '2026-07-01T10:15:00Z', 'user',   'manual_override', 'model', 'm1', 'User overrode model M1', NULL, NULL, NULL, '{}', 'rec_1', NULL, NULL);
        """
    )
    conn.commit()
    conn.close()

    res = compute_override_analytics(temp_db, "proj_1")
    assert res["total_decisions"] == 4
    assert res["total_overrides"] == 1
    assert res["overall_override_rate"] == 0.25

    by_kind = res["by_kind"]
    assert "model_selected" in by_kind
    assert by_kind["model_selected"]["total"] == 2
    assert by_kind["model_selected"]["overridden"] == 1
    assert by_kind["model_selected"]["rate"] == 0.5


def test_journal_payload_builders():
    """Test standard builders in edeon_engine.journal_payload."""
    rat = build_rationale(
        drivers=[{"factor": "MW", "value": 350.0, "contribution": 0.8}],
        scores={"mpo": 8.5},
        thresholds={"logp": 3.0},
    )
    assert "drivers" in rat
    assert rat["scores"]["mpo"] == 8.5

    alts = build_alternatives([{"id": "c2", "label": "Compound 2", "score": 7.2, "why_not": "Lower selectivity"}])
    assert len(alts) == 1
    assert alts[0]["why_not"] == "Lower selectivity"

    conf = build_confidence(uq={"logp": {"interval": [2.1, 2.5]}}, ad_status="in", reliability="ok")
    assert conf["ad_status"] == "in"

    prov = build_provenance(params_hash="abc123hash", model_versions={"logp": "v1.0"}, code_version="0.1.0")
    assert prov["code_version"] == "0.1.0"
