/// Edeon Desktop — Speciation Commands
///
/// Tauri IPC handlers for pH-dependent chemical speciation calculations (Phase G5).

use crate::AppState;
use serde_json::json;
use tauri::State;

#[tauri::command]
pub fn speciation_enumerate(
    state: State<'_, AppState>,
    smiles: String,
    ph_min: Option<f64>,
    ph_max: Option<f64>,
    ph_target: Option<f64>,
    max_variants: Option<usize>,
) -> Result<serde_json::Value, String> {
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    let db_path = {
        let db = state.db.lock().map_err(|e| format!("DB lock error: {}", e))?;
        db.path().unwrap_or("").to_string()
    };

    engine.send_request("speciation.enumerate", json!({
        "smiles": smiles,
        "ph_min": ph_min.unwrap_or(4.0),
        "ph_max": ph_max.unwrap_or(8.0),
        "ph_target": ph_target.unwrap_or(6.5),
        "max_variants": max_variants.unwrap_or(8),
        "db_path": db_path,
    }))
}

#[tauri::command]
pub fn speciation_dominant_at_ph(
    state: State<'_, AppState>,
    smiles: String,
    ph: f64,
) -> Result<serde_json::Value, String> {
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request("speciation.dominant_at_ph", json!({
        "smiles": smiles,
        "ph": ph,
    }))
}

#[tauri::command]
pub fn speciation_profile_curve(
    state: State<'_, AppState>,
    smiles: String,
    ph_min: Option<f64>,
    ph_max: Option<f64>,
    steps: Option<usize>,
) -> Result<serde_json::Value, String> {
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request("speciation.profile_curve", json!({
        "smiles": smiles,
        "ph_min": ph_min.unwrap_or(4.0),
        "ph_max": ph_max.unwrap_or(9.0),
        "steps": steps.unwrap_or(26),
    }))
}
