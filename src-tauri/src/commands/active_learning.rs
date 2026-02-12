/// Edeon Desktop — Bayesian-Optimization Active Learning Commands
///
/// Tauri IPC handlers for Gaussian Process surrogate modeling and acquisition batch optimization.

use crate::AppState;
use serde_json::json;
use tauri::State;

/// Suggest next optimal candidate batch for synthesis/screening.
#[tauri::command]
pub fn al_suggest_next_batch(
    state: State<'_, AppState>,
    labeled_pool: Vec<serde_json::Value>,
    candidate_pool: Vec<serde_json::Value>,
    acquisition: Option<String>,
    batch_size: Option<usize>,
    endpoint: Option<String>,
) -> Result<serde_json::Value, String> {
    if labeled_pool.is_empty() {
        return Err("Labeled training pool cannot be empty".to_string());
    }
    if candidate_pool.is_empty() {
        return Err("Candidate pool cannot be empty".to_string());
    }

    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request(
        "al.suggest_next_batch",
        json!({
            "labeled_pool": labeled_pool,
            "candidate_pool": candidate_pool,
            "acquisition": acquisition.unwrap_or_else(|| "ei".to_string()),
            "batch_size": batch_size.unwrap_or(10),
            "endpoint": endpoint.unwrap_or_else(|| "potency".to_string()),
        }),
    )
}
