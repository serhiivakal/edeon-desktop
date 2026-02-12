/// Edeon Desktop — Matched Molecular Pair & Free-Wilson SAR Commands
///
/// Tauri IPC handlers for library fragmentation indexing, selectivity transform ranking,
/// and Free-Wilson additive regression solving.

use crate::AppState;
use serde_json::json;
use tauri::State;

/// Index matched molecular pairs across a compound dataset.
#[tauri::command]
pub fn sar_mmp_index(
    state: State<'_, AppState>,
    compounds: Vec<serde_json::Value>,
) -> Result<serde_json::Value, String> {
    if compounds.is_empty() {
        return Ok(json!({"ok": true, "pairs": [], "n_pairs": 0}));
    }

    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request("sar.mmp_index", json!({ "compounds": compounds }))
}

/// Suggest selectivity window-widening transforms.
#[tauri::command]
pub fn sar_mmp_suggest_transforms(
    state: State<'_, AppState>,
    compounds: Vec<serde_json::Value>,
    top_k: Option<usize>,
) -> Result<serde_json::Value, String> {
    if compounds.is_empty() {
        return Ok(json!({"ok": true, "transforms": [], "n_transforms": 0}));
    }

    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request(
        "sar.mmp_suggest_transforms",
        json!({
            "compounds": compounds,
            "top_k": top_k.unwrap_or(20),
        }),
    )
}

/// Fit Free-Wilson additive SAR regression model.
#[tauri::command]
pub fn sar_free_wilson_fit(
    state: State<'_, AppState>,
    compounds: Vec<serde_json::Value>,
    endpoint: String,
) -> Result<serde_json::Value, String> {
    if compounds.is_empty() {
        return Err("Compounds list cannot be empty".to_string());
    }

    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request(
        "sar.free_wilson_fit",
        json!({
            "compounds": compounds,
            "endpoint": endpoint,
        }),
    )
}
