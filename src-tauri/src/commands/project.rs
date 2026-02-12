/// Edeon Desktop — Project Commands
///
/// Tauri IPC handlers for project CRUD operations.

use crate::models::Project;
use crate::AppState;
use tauri::State;
use uuid::Uuid;
use chrono::Utc;

#[tauri::command]
pub fn create_project(state: State<'_, AppState>, name: String) -> Result<Project, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    let id = Uuid::new_v4().to_string();
    let now = Utc::now().to_rfc3339();

    db.execute(
        "INSERT INTO projects (id, name, created_at, updated_at, compound_count) VALUES (?1, ?2, ?3, ?4, 0)",
        rusqlite::params![id, name, now, now],
    )
    .map_err(|e| e.to_string())?;

    Ok(Project {
        id,
        name,
        created_at: now.clone(),
        updated_at: now,
        compound_count: 0,
    })
}

#[tauri::command]
pub fn list_projects(state: State<'_, AppState>) -> Result<Vec<Project>, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;

    let mut stmt = db
        .prepare("SELECT id, name, created_at, updated_at, compound_count FROM projects ORDER BY updated_at DESC")
        .map_err(|e| e.to_string())?;

    let projects = stmt
        .query_map([], |row| {
            Ok(Project {
                id: row.get(0)?,
                name: row.get(1)?,
                created_at: row.get(2)?,
                updated_at: row.get(3)?,
                compound_count: row.get(4)?,
            })
        })
        .map_err(|e| e.to_string())?
        .collect::<Result<Vec<_>, _>>()
        .map_err(|e| e.to_string())?;

    Ok(projects)
}

#[tauri::command]
pub fn rename_project(
    state: State<'_, AppState>,
    id: String,
    new_name: String,
) -> Result<Project, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    let now = Utc::now().to_rfc3339();

    let rows = db
        .execute(
            "UPDATE projects SET name = ?1, updated_at = ?2 WHERE id = ?3",
            rusqlite::params![new_name, now, id],
        )
        .map_err(|e| e.to_string())?;

    if rows == 0 {
        return Err("Project not found".to_string());
    }

    // Fetch the updated project
    let project = db
        .query_row(
            "SELECT id, name, created_at, updated_at, compound_count FROM projects WHERE id = ?1",
            rusqlite::params![id],
            |row| {
                Ok(Project {
                    id: row.get(0)?,
                    name: row.get(1)?,
                    created_at: row.get(2)?,
                    updated_at: row.get(3)?,
                    compound_count: row.get(4)?,
                })
            },
        )
        .map_err(|e| e.to_string())?;

    Ok(project)
}

#[tauri::command]
pub fn delete_project(state: State<'_, AppState>, id: String) -> Result<(), String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;

    // Foreign key cascade handles compounds, workflows, results
    let rows = db
        .execute("DELETE FROM projects WHERE id = ?1", rusqlite::params![id])
        .map_err(|e| e.to_string())?;

    if rows == 0 {
        return Err("Project not found".to_string());
    }

    Ok(())
}

#[tauri::command]
pub fn get_active_project_id(state: State<'_, AppState>) -> Result<Option<String>, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;

    let result = db.query_row(
        "SELECT value FROM settings WHERE key = 'active_project_id'",
        [],
        |row| row.get::<_, String>(0),
    );

    match result {
        Ok(id) => Ok(Some(id)),
        Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
        Err(e) => Err(e.to_string()),
    }
}

#[tauri::command]
pub fn set_active_project(state: State<'_, AppState>, id: String) -> Result<(), String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;

    db.execute(
        "INSERT INTO settings (key, value) VALUES ('active_project_id', ?1)
         ON CONFLICT(key) DO UPDATE SET value = ?1",
        rusqlite::params![id],
    )
    .map_err(|e| e.to_string())?;

    Ok(())
}
