/// Edeon Desktop — Retrosynthesis & Synthesizability Commands
///
/// Tauri IPC handlers for retrosynthetic route search and BR-SAScore synthesizability gating (Phase G1).

use crate::AppState;
use serde_json::json;
use tauri::State;

#[tauri::command]
pub fn retro_sascore(
    state: State<'_, AppState>,
    smiles: Vec<String>,
) -> Result<serde_json::Value, String> {
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request("retro.sascore", json!({
        "smiles": smiles,
    }))
}

#[tauri::command]
pub fn retro_route_search(
    state: State<'_, AppState>,
    smiles: String,
    time_limit_s: Option<u64>,
    max_routes: Option<usize>,
    stock_id: Option<String>,
) -> Result<serde_json::Value, String> {
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request("retro.route_search", json!({
        "smiles": smiles,
        "time_limit_s": time_limit_s.unwrap_or(30),
        "max_routes": max_routes.unwrap_or(5),
        "stock_id": stock_id.unwrap_or_else(|| "agrochem_default".to_string()),
    }))
}

#[tauri::command]
pub fn retro_gate_batch(
    state: State<'_, AppState>,
    smiles: Vec<String>,
    sa_threshold: Option<f64>,
    route_search_top_k: Option<usize>,
    stock_id: Option<String>,
) -> Result<serde_json::Value, String> {
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request("retro.gate_batch", json!({
        "smiles": smiles,
        "sa_threshold": sa_threshold.unwrap_or(0.4),
        "route_search_top_k": route_search_top_k.unwrap_or(5),
        "stock_id": stock_id.unwrap_or_else(|| "agrochem_default".to_string()),
    }))
}

#[tauri::command]
pub fn retro_import_stock(
    state: State<'_, AppState>,
    path: String,
    name: String,
) -> Result<serde_json::Value, String> {
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request("retro.import_stock", json!({
        "path": path,
        "name": name,
    }))
}
