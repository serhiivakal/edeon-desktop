/// Edeon Desktop — Mobility Commands
///
/// Tauri IPC handlers for mechanistic systemic mobility model (Phase J8).

use crate::AppState;
use serde_json::json;
use tauri::State;

#[tauri::command]
pub fn mobility_predict(
    state: State<'_, AppState>,
    smiles: String,
    ph_apoplast: Option<f64>,
    ph_phloem: Option<f64>,
) -> Result<serde_json::Value, String> {
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request("mobility.predict", json!({
        "smiles": smiles,
        "ph_apoplast": ph_apoplast.unwrap_or(5.5),
        "ph_phloem": ph_phloem.unwrap_or(8.0),
    }))
}
