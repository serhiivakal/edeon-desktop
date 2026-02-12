/// Edeon Desktop — Decision Journal Writer
///
/// Implements the immutable, append-only decision journal (Phase M).
///
/// Two hard invariants:
/// - INV-1 (atomicity): A journal entry and the state change it describes
///   commit in the SAME SQLite transaction. `append()` writes inside the
///   caller's open transaction; if the caller rolls back, the journal row
///   disappears with it.
/// - INV-2 (append-only): Journal rows are immutable. Corrections are new
///   rows linked by `supersedes_id`. There is no UPDATE or DELETE path on
///   `decision_journal` other than whole-project deletion cascade.

use rusqlite::{Connection, Transaction, params};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// A single decision journal entry, mirroring the `decision_journal` schema.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JournalEntry {
    pub entry_id: String,
    pub project_id: String,
    pub actor: String,           // "system" | "user"
    pub decision_kind: String,
    pub subject_type: String,    // "compound" | "workflow" | "model" | "campaign" | "analysis" | "tp" | "config"
    pub subject_id: String,
    pub summary: String,
    pub rationale_json: Option<String>,
    pub alternatives_json: Option<String>,
    pub confidence_json: Option<String>,
    pub provenance_json: String,
    pub override_of: Option<String>,
    pub supersedes_id: Option<String>,
    pub user_note: Option<String>,
}

impl JournalEntry {
    /// Create a new system-emitted journal entry with a fresh UUID.
    pub fn new_system(
        project_id: &str,
        decision_kind: &str,
        subject_type: &str,
        subject_id: &str,
        summary: &str,
        provenance_json: &str,
    ) -> Self {
        JournalEntry {
            entry_id: Uuid::new_v4().to_string(),
            project_id: project_id.to_string(),
            actor: "system".to_string(),
            decision_kind: decision_kind.to_string(),
            subject_type: subject_type.to_string(),
            subject_id: subject_id.to_string(),
            summary: summary.to_string(),
            rationale_json: None,
            alternatives_json: None,
            confidence_json: None,
            provenance_json: provenance_json.to_string(),
            override_of: None,
            supersedes_id: None,
            user_note: None,
        }
    }

    /// Create a new user-emitted journal entry (e.g. manual override).
    pub fn new_user(
        project_id: &str,
        decision_kind: &str,
        subject_type: &str,
        subject_id: &str,
        summary: &str,
        provenance_json: &str,
    ) -> Self {
        let mut entry = Self::new_system(
            project_id, decision_kind, subject_type,
            subject_id, summary, provenance_json,
        );
        entry.actor = "user".to_string();
        entry
    }
}

/// Appends a journal row using the caller's open transaction.
/// Fails the whole transaction on error — the decision and its record
/// are all-or-nothing (INV-1).
///
/// Returns the `entry_id` of the newly inserted row.
pub fn append(tx: &Transaction, entry: &JournalEntry) -> Result<String, String> {
    tx.execute(
        "INSERT INTO decision_journal (
            entry_id, project_id, actor, decision_kind,
            subject_type, subject_id, summary,
            rationale_json, alternatives_json, confidence_json,
            provenance_json, override_of, supersedes_id, user_note
        ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14)",
        params![
            entry.entry_id,
            entry.project_id,
            entry.actor,
            entry.decision_kind,
            entry.subject_type,
            entry.subject_id,
            entry.summary,
            entry.rationale_json,
            entry.alternatives_json,
            entry.confidence_json,
            entry.provenance_json,
            entry.override_of,
            entry.supersedes_id,
            entry.user_note,
        ],
    )
    .map_err(|e| format!("Journal append failed: {}", e))?;

    Ok(entry.entry_id.clone())
}

/// Convenience for commands that don't already hold a transaction.
/// Opens a transaction, appends the entry, and commits.
pub fn append_standalone(conn: &mut Connection, entry: &JournalEntry) -> Result<String, String> {
    let tx = conn.transaction().map_err(|e| format!("Journal tx begin failed: {}", e))?;
    let id = append(&tx, entry)?;
    tx.commit().map_err(|e| format!("Journal tx commit failed: {}", e))?;
    Ok(id)
}
