/// Edeon Desktop — Environmental Fate Commands
///
/// Tauri IPC handlers for estimating parent compound fate and REACH scorecard.

use crate::AppState;
use serde_json::json;
use tauri::State;

#[tauri::command]
pub fn compute_environmental_fate(
    state: State<'_, AppState>,
    smiles: Vec<String>,
) -> Result<serde_json::Value, String> {
    if smiles.is_empty() {
        return Ok(json!([]));
    }

    // Acquire Python engine (auto-respawns if dead)
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    // Make RPC request to compute environmental fate
    engine.send_request(
        "environmental_fate",
        json!({
            "smiles": smiles,
        }),
    )
}

#[tauri::command]
pub fn predict_transformation_products(
    state: State<'_, AppState>,
    smiles: String,
    routes: Vec<String>,
    max_depth: u32,
    sources: Option<Vec<String>>,
    ph: Option<f64>,
) -> Result<serde_json::Value, String> {
    if smiles.is_empty() {
        return Err("SMILES string cannot be empty".to_string());
    }

    // Acquire Python engine (auto-respawns if dead)
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    let result = engine.send_request(
        "transformation_products",
        json!({
            "smiles": smiles,
            "routes": routes,
            "max_depth": max_depth,
            "sources": sources,
            "ph": ph.unwrap_or(6.5),
        }),
    )?;

    // Check if any product has risk liabilities
    if let Some(products) = result.get("products").and_then(|v| v.as_array()) {
        let flagged_count = products.iter()
            .filter(|p| p.get("risk_flag").and_then(|v| v.as_bool()).unwrap_or(false) || p.get("risk_flag").and_then(|v| v.as_i64()).unwrap_or(0) == 1)
            .count();

        if flagged_count > 0 {
            let summary = format!("Transformation products for SMILES flagged {} liability risk product(s)", flagged_count);
            let entry = crate::journal::JournalEntry::new_system(
                "global",
                "tp_liability_flagged",
                "tp",
                &smiles,
                &summary,
                &json!({ "routes": routes, "max_depth": max_depth, "flagged_count": flagged_count }).to_string(),
            );
            if let Ok(mut db) = state.db.lock() {
                let _ = crate::journal::append_standalone(&mut db, &entry);
            }
        }
    }

    Ok(result)
}
