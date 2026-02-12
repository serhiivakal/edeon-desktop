/// Edeon Desktop — Chemical-Space Cartography Commands
///
/// Tauri IPC handlers for computing TMAP Minimum Spanning Tree 2D coordinates.

use crate::AppState;
use serde_json::json;
use tauri::State;

/// Compute TMAP MST layout coordinates for a dataset of compounds.
#[tauri::command]
pub fn cartography_compute_tmap(
    state: State<'_, AppState>,
    compounds: Vec<serde_json::Value>,
) -> Result<serde_json::Value, String> {
    if compounds.is_empty() {
        return Ok(json!({"ok": true, "nodes": [], "edges": [], "n_compounds": 0}));
    }

    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request("cartography.compute_tmap", json!({ "compounds": compounds }))
}
