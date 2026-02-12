/// Edeon Desktop — App Meta and System Status Commands
///
/// Handles first-launch tracking, system resources stats, deployed models metadata, and citations generation.

use crate::AppState;
use serde_json::json;
use tauri::State;

/// Dynamically queries SQLite for the absolute path to the main database file.
fn get_db_path(state: &State<'_, AppState>) -> Result<String, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    let path: String = db.query_row(
        "SELECT file FROM pragma_database_list WHERE name='main'",
        [],
        |row| row.get(0),
    )
    .map_err(|e| e.to_string())?;
    Ok(path)
}

#[tauri::command]
pub fn app_meta_get_first_launch_state(
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    let db_path = get_db_path(&state)?;
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request(
        "app_meta_get_first_launch_state",
        json!({ "db_path": db_path }),
    )
}

#[tauri::command]
pub fn app_meta_mark_first_launch_complete(
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    let db_path = get_db_path(&state)?;
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request(
        "app_meta_mark_first_launch_complete",
        json!({ "db_path": db_path }),
    )
}

#[tauri::command]
pub fn app_meta_get_system_info(
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    let db_path = get_db_path(&state)?;
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request(
        "app_meta_get_system_info",
        json!({ "db_path": db_path }),
    )
}

#[tauri::command]
pub fn app_meta_get_status(
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    let db_path = get_db_path(&state)?;
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    // Request status from Python sidecar
    let mut status = engine.send_request(
        "app_meta_get_status",
        json!({ "db_path": db_path }),
    )?;

    // Populate Rust-level background tasks count
    if let Some(obj) = status.as_object_mut() {
        // Simple mock of background tasks count (can be populated if Edeon registers background task queues)
        obj.insert("background_tasks_count".to_string(), json!(0));
        obj.insert("background_tasks".to_string(), json!([]));
    }

    Ok(status)
}

#[tauri::command]
pub fn retrosynthesis_predict(
    state: State<'_, AppState>,
    smiles: String,
) -> Result<serde_json::Value, String> {
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request(
        "retrosynthesis_predict",
        json!({ "smiles": smiles }),
    )
}

#[tauri::command]
pub fn citation_generate(
    state: State<'_, AppState>,
    citation_target: String,
    target_metadata: serde_json::Value,
    output_format: String,
) -> Result<serde_json::Value, String> {
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request(
        "citation_generate",
        json!({
            "citation_target": citation_target,
            "target_metadata": target_metadata,
            "output_format": output_format,
        }),
    )
}

#[tauri::command]
pub fn app_meta_get_verification_report(
    state: State<'_, AppState>,
    endpoint: Option<String>,
) -> Result<serde_json::Value, String> {
    let db_path = get_db_path(&state)?;
    let db_path_buf = std::path::PathBuf::from(&db_path);
    let project_root = db_path_buf
        .parent()
        .and_then(|p| p.parent())
        .ok_or_else(|| "Failed to resolve project root directory from database path".to_string())?;

    let file_name = match endpoint {
        Some(ref ep) => format!("calibration_{}.md", ep),
        None => "SUMMARY.md".to_string(),
    };

    let report_path = project_root.join("docs").join("verification").join(&file_name);
    
    if !report_path.exists() {
        return Err(format!("Verification report file not found at: {:?}", report_path));
    }

    let content = std::fs::read_to_string(&report_path)
        .map_err(|e| format!("Failed to read report file: {}", e))?;

    let mut image_uri = None;
    if endpoint.is_none() || endpoint.as_deref() == Some("soil_dt50") {
        let image_path = project_root.join("docs").join("verification").join("dt50_sigma_correlation.png");
        if image_path.exists() {
            if let Ok(bytes) = std::fs::read(&image_path) {
                use base64::prelude::*;
                let b64 = BASE64_STANDARD.encode(bytes);
                image_uri = Some(format!("data:image/png;base64,{}", b64));
            }
        }
    }

    Ok(json!({
        "content": content,
        "image_uri": image_uri,
    }))
}
