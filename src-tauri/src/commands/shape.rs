/// Edeon Desktop — 3D Shape & Electrostatic Similarity Screening Commands
///
/// Tauri IPC handlers for Open3DAlign conformer alignment and espsim electrostatic similarity scoring.

use crate::AppState;
use serde_json::json;
use tauri::State;

/// Screen candidates against reference ligand SMILES using 3D shape + electrostatic similarity.
#[tauri::command]
pub fn shape_screen_3d(
    state: State<'_, AppState>,
    reference_smiles: String,
    candidates: Vec<serde_json::Value>,
    top_k: Option<usize>,
) -> Result<serde_json::Value, String> {
    if reference_smiles.is_empty() {
        return Err("Reference SMILES cannot be empty".to_string());
    }
    if candidates.is_empty() {
        return Ok(json!({"ok": true, "reference_smiles": reference_smiles, "results": [], "n_screened": 0, "n_returned": 0}));
    }

    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request(
        "shape.screen_3d",
        json!({
            "reference_smiles": reference_smiles,
            "candidates": candidates,
            "top_k": top_k.unwrap_or(50),
        }),
    )
}
