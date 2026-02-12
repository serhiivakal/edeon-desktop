"""
Edeon Engine — Journal Analytics

Python-side analytics computed from the decision_journal SQLite table:
  - build_lineage: assembles the decision chain for a single compound
  - compute_override_analytics: override rate by kind, resolved outcome deltas

These query the journal table read-only; all writes go through Rust (INV-1).
"""

import sqlite3
from typing import Optional


def _connect(db_path: str) -> sqlite3.Connection:
    """Open a read-only connection to the Edeon database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def build_lineage(db_path: str, project_id: str, compound_id: str) -> dict:
    """Build the decision chain for a compound.

    Returns all journal entries where subject_id matches the compound,
    plus any override chains (via override_of / supersedes_id).
    Ordered by created_at ascending.
    """
    conn = _connect(db_path)
    try:
        # Get all entries for this compound
        rows = conn.execute(
            """SELECT entry_id, project_id, created_at, actor, decision_kind,
                      subject_type, subject_id, summary,
                      rationale_json, alternatives_json, confidence_json,
                      provenance_json, override_of, supersedes_id, user_note
               FROM decision_journal
               WHERE project_id = ? AND subject_id = ?
               ORDER BY created_at ASC""",
            (project_id, compound_id),
        ).fetchall()

        entries = [dict(r) for r in rows]

        # Also fetch any entries that override entries in our chain
        entry_ids = {e["entry_id"] for e in entries}
        if entry_ids:
            placeholders = ",".join("?" * len(entry_ids))
            override_rows = conn.execute(
                f"""SELECT entry_id, project_id, created_at, actor, decision_kind,
                          subject_type, subject_id, summary,
                          rationale_json, alternatives_json, confidence_json,
                          provenance_json, override_of, supersedes_id, user_note
                   FROM decision_journal
                   WHERE project_id = ? AND override_of IN ({placeholders})
                   ORDER BY created_at ASC""",
                [project_id] + list(entry_ids),
            ).fetchall()

            for r in override_rows:
                d = dict(r)
                if d["entry_id"] not in entry_ids:
                    entries.append(d)
                    entry_ids.add(d["entry_id"])

        # Sort by timestamp
        entries.sort(key=lambda x: x.get("created_at", ""))

        return {
            "compound_id": compound_id,
            "project_id": project_id,
            "entries": entries,
            "n_entries": len(entries),
        }
    finally:
        conn.close()


def compute_override_analytics(db_path: str, project_id: str) -> dict:
    """Compute override statistics for a project.

    Returns:
        {
            "by_kind": {kind: {"total": int, "overridden": int, "rate": float}},
            "total_decisions": int,
            "total_overrides": int,
            "overall_override_rate": float,
        }
    """
    conn = _connect(db_path)
    try:
        # Count total decisions by kind
        kind_rows = conn.execute(
            """SELECT decision_kind, COUNT(*) as cnt
               FROM decision_journal
               WHERE project_id = ?
               GROUP BY decision_kind""",
            (project_id,),
        ).fetchall()

        # Count overrides by kind of the overridden entry
        override_rows = conn.execute(
            """SELECT original.decision_kind, COUNT(*) as cnt
               FROM decision_journal override_entry
               JOIN decision_journal original
                 ON override_entry.override_of = original.entry_id
               WHERE override_entry.project_id = ?
               GROUP BY original.decision_kind""",
            (project_id,),
        ).fetchall()

        by_kind = {}
        total_decisions = 0
        for r in kind_rows:
            kind = r["decision_kind"]
            cnt = r["cnt"]
            total_decisions += cnt
            by_kind[kind] = {"total": cnt, "overridden": 0, "rate": 0.0}

        total_overrides = 0
        for r in override_rows:
            kind = r["decision_kind"]
            cnt = r["cnt"]
            total_overrides += cnt
            if kind in by_kind:
                by_kind[kind]["overridden"] = cnt
                by_kind[kind]["rate"] = round(cnt / by_kind[kind]["total"], 4) if by_kind[kind]["total"] > 0 else 0.0

        overall_rate = round(total_overrides / total_decisions, 4) if total_decisions > 0 else 0.0

        return {
            "by_kind": by_kind,
            "total_decisions": total_decisions,
            "total_overrides": total_overrides,
            "overall_override_rate": overall_rate,
        }
    finally:
        conn.close()
