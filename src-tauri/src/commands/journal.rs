/// Edeon Desktop — Decision Journal Commands
///
/// Tauri IPC handlers for reading and querying the decision journal,
/// recording manual overrides, adding user notes, and export.
///
/// Write paths go through journal::append (INV-1: always inside a transaction).
/// Read paths query the decision_journal table directly.

use crate::AppState;
use crate::journal;
use serde_json::json;
use tauri::State;

/// List journal entries for a project with optional filters.
#[tauri::command]
pub fn journal_list(
    state: State<'_, AppState>,
    project_id: String,
    decision_kind: Option<String>,
    subject_type: Option<String>,
    subject_id: Option<String>,
    limit: Option<i64>,
    offset: Option<i64>,
) -> Result<serde_json::Value, String> {
    let db = state.db.lock().map_err(|e| format!("DB lock error: {}", e))?;
    let lim = limit.unwrap_or(100);
    let off = offset.unwrap_or(0);

    let mut sql = String::from(
        "SELECT entry_id, project_id, created_at, actor, decision_kind,
                subject_type, subject_id, summary,
                rationale_json, alternatives_json, confidence_json,
                provenance_json, override_of, supersedes_id, user_note
         FROM decision_journal WHERE project_id = ?1"
    );
    let mut params: Vec<Box<dyn rusqlite::types::ToSql>> = vec![Box::new(project_id.clone())];
    let mut idx = 2;

    if let Some(ref kind) = decision_kind {
        sql.push_str(&format!(" AND decision_kind = ?{}", idx));
        params.push(Box::new(kind.clone()));
        idx += 1;
    }
    if let Some(ref st) = subject_type {
        sql.push_str(&format!(" AND subject_type = ?{}", idx));
        params.push(Box::new(st.clone()));
        idx += 1;
    }
    if let Some(ref si) = subject_id {
        sql.push_str(&format!(" AND subject_id = ?{}", idx));
        params.push(Box::new(si.clone()));
        idx += 1;
    }

    sql.push_str(&format!(" ORDER BY created_at DESC LIMIT ?{} OFFSET ?{}", idx, idx + 1));
    params.push(Box::new(lim));
    params.push(Box::new(off));

    let params_refs: Vec<&dyn rusqlite::types::ToSql> = params.iter().map(|p| p.as_ref()).collect();

    let mut stmt = db.prepare(&sql).map_err(|e| format!("SQL prepare error: {}", e))?;

    let rows = stmt.query_map(params_refs.as_slice(), |row| {
        Ok(json!({
            "entry_id": row.get::<_, String>(0)?,
            "project_id": row.get::<_, String>(1)?,
            "created_at": row.get::<_, String>(2)?,
            "actor": row.get::<_, String>(3)?,
            "decision_kind": row.get::<_, String>(4)?,
            "subject_type": row.get::<_, String>(5)?,
            "subject_id": row.get::<_, String>(6)?,
            "summary": row.get::<_, String>(7)?,
            "rationale_json": row.get::<_, Option<String>>(8)?,
            "alternatives_json": row.get::<_, Option<String>>(9)?,
            "confidence_json": row.get::<_, Option<String>>(10)?,
            "provenance_json": row.get::<_, Option<String>>(11)?,
            "override_of": row.get::<_, Option<String>>(12)?,
            "supersedes_id": row.get::<_, Option<String>>(13)?,
            "user_note": row.get::<_, Option<String>>(14)?,
        }))
    }).map_err(|e| format!("Query error: {}", e))?;

    let mut entries = Vec::new();
    for row in rows {
        entries.push(row.map_err(|e| format!("Row error: {}", e))?);
    }

    // Get total count
    let count_subject_type = if subject_type.is_some() {
        format!(" AND subject_type = ?{}", if decision_kind.is_some() { 3 } else { 2 })
    } else {
        String::new()
    };
    let count_subject_id = if subject_id.is_some() {
        let base = 2 + decision_kind.is_some() as i32 + subject_type.is_some() as i32;
        format!(" AND subject_id = ?{}", base)
    } else {
        String::new()
    };
    let count_sql = format!(
        "SELECT COUNT(*) FROM decision_journal WHERE project_id = ?1{}{}{}",
        if decision_kind.is_some() { " AND decision_kind = ?2" } else { "" },
        count_subject_type,
        count_subject_id
    );

    let total: i64 = db.query_row(
        &count_sql,
        &params_refs[..params_refs.len() - 2],
        |row| row.get(0),
    ).unwrap_or(0);

    Ok(json!({
        "entries": entries,
        "total": total,
        "limit": lim,
        "offset": off,
    }))
}

/// Get a single journal entry by ID.
#[tauri::command]
pub fn journal_get(
    state: State<'_, AppState>,
    entry_id: String,
) -> Result<serde_json::Value, String> {
    let db = state.db.lock().map_err(|e| format!("DB lock error: {}", e))?;

    let entry = db.query_row(
        "SELECT entry_id, project_id, created_at, actor, decision_kind,
                subject_type, subject_id, summary,
                rationale_json, alternatives_json, confidence_json,
                provenance_json, override_of, supersedes_id, user_note
         FROM decision_journal WHERE entry_id = ?1",
        [&entry_id],
        |row| {
            Ok(json!({
                "entry_id": row.get::<_, String>(0)?,
                "project_id": row.get::<_, String>(1)?,
                "created_at": row.get::<_, String>(2)?,
                "actor": row.get::<_, String>(3)?,
                "decision_kind": row.get::<_, String>(4)?,
                "subject_type": row.get::<_, String>(5)?,
                "subject_id": row.get::<_, String>(6)?,
                "summary": row.get::<_, String>(7)?,
                "rationale_json": row.get::<_, Option<String>>(8)?,
                "alternatives_json": row.get::<_, Option<String>>(9)?,
                "confidence_json": row.get::<_, Option<String>>(10)?,
                "provenance_json": row.get::<_, Option<String>>(11)?,
                "override_of": row.get::<_, Option<String>>(12)?,
                "supersedes_id": row.get::<_, Option<String>>(13)?,
                "user_note": row.get::<_, Option<String>>(14)?,
            }))
        },
    ).map_err(|e| format!("Entry not found: {}", e))?;

    Ok(entry)
}

/// Get compound lineage (delegates to Python analytics).
#[tauri::command]
pub fn journal_lineage(
    state: State<'_, AppState>,
    project_id: String,
    compound_id: String,
) -> Result<serde_json::Value, String> {
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    // Get db path from the connection
    let db_path = {
        let db = state.db.lock().map_err(|e| format!("DB lock error: {}", e))?;
        db.path().unwrap_or("").to_string()
    };

    engine.send_request("journal.lineage", json!({
        "project_id": project_id,
        "compound_id": compound_id,
        "db_path": db_path,
    }))
}

/// Get override analytics for a project (delegates to Python).
#[tauri::command]
pub fn journal_override_analytics(
    state: State<'_, AppState>,
    project_id: String,
) -> Result<serde_json::Value, String> {
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    let db_path = {
        let db = state.db.lock().map_err(|e| format!("DB lock error: {}", e))?;
        db.path().unwrap_or("").to_string()
    };

    engine.send_request("journal.override_analytics", json!({
        "project_id": project_id,
        "db_path": db_path,
    }))
}

/// Add a user note to an existing journal entry.
/// This is NOT a mutation of the entry (INV-2). The note is stored in a
/// column that is architecturally part of the initial write, but may be
/// NULL on system-emitted entries and filled in later by the user.
#[tauri::command]
pub fn journal_add_note(
    state: State<'_, AppState>,
    entry_id: String,
    note: String,
) -> Result<serde_json::Value, String> {
    let db = state.db.lock().map_err(|e| format!("DB lock error: {}", e))?;

    db.execute(
        "UPDATE decision_journal SET user_note = ?1 WHERE entry_id = ?2 AND user_note IS NULL",
        rusqlite::params![note, entry_id],
    ).map_err(|e| format!("Note update failed: {}", e))?;

    Ok(json!({"ok": true, "entry_id": entry_id}))
}

/// Record a manual override (user contradicts system recommendation).
/// Creates a new journal entry with actor="user" and override_of pointing
/// to the overridden system entry.
#[tauri::command]
pub fn journal_record_override(
    state: State<'_, AppState>,
    project_id: String,
    override_of: String,
    subject_type: String,
    subject_id: String,
    action_taken: String,
    system_recommendation: String,
    user_note: Option<String>,
) -> Result<serde_json::Value, String> {
    let summary = format!(
        "User override: {} (system recommended: {})",
        action_taken, system_recommendation
    );

    let provenance = json!({
        "params_hash": "",
        "model_versions": {},
        "code_version": "0.1.0",
    });

    let mut entry = journal::JournalEntry::new_user(
        &project_id,
        "manual_override",
        &subject_type,
        &subject_id,
        &summary,
        &serde_json::to_string(&provenance).unwrap_or_default(),
    );
    entry.override_of = Some(override_of);
    entry.user_note = user_note;
    entry.rationale_json = Some(json!({
        "action_taken": action_taken,
        "system_recommendation": system_recommendation,
    }).to_string());

    let mut db = state.db.lock().map_err(|e| format!("DB lock error: {}", e))?;
    let id = journal::append_standalone(&mut db, &entry)?;

    Ok(json!({"ok": true, "entry_id": id}))
}

/// Export journal entries as JSON.
#[tauri::command]
pub fn journal_export(
    state: State<'_, AppState>,
    project_id: String,
    format: Option<String>,
) -> Result<serde_json::Value, String> {
    let db = state.db.lock().map_err(|e| format!("DB lock error: {}", e))?;

    let mut stmt = db.prepare(
        "SELECT entry_id, project_id, created_at, actor, decision_kind,
                subject_type, subject_id, summary,
                rationale_json, alternatives_json, confidence_json,
                provenance_json, override_of, supersedes_id, user_note
         FROM decision_journal WHERE project_id = ?1
         ORDER BY created_at ASC"
    ).map_err(|e| format!("SQL prepare error: {}", e))?;

    let rows = stmt.query_map([&project_id], |row| {
        Ok(json!({
            "entry_id": row.get::<_, String>(0)?,
            "project_id": row.get::<_, String>(1)?,
            "created_at": row.get::<_, String>(2)?,
            "actor": row.get::<_, String>(3)?,
            "decision_kind": row.get::<_, String>(4)?,
            "subject_type": row.get::<_, String>(5)?,
            "subject_id": row.get::<_, String>(6)?,
            "summary": row.get::<_, String>(7)?,
            "rationale_json": row.get::<_, Option<String>>(8)?,
            "alternatives_json": row.get::<_, Option<String>>(9)?,
            "confidence_json": row.get::<_, Option<String>>(10)?,
            "provenance_json": row.get::<_, Option<String>>(11)?,
            "override_of": row.get::<_, Option<String>>(12)?,
            "supersedes_id": row.get::<_, Option<String>>(13)?,
            "user_note": row.get::<_, Option<String>>(14)?,
        }))
    }).map_err(|e| format!("Query error: {}", e))?;

    let mut entries = Vec::new();
    for row in rows {
        entries.push(row.map_err(|e| format!("Row error: {}", e))?);
    }

    Ok(json!({
        "project_id": project_id,
        "entries": entries,
        "n_entries": entries.len(),
        "format": format.unwrap_or_else(|| "json".to_string()),
    }))
}
