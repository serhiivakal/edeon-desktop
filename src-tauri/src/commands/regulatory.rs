/// Edeon Desktop — Registration Risk Scorecard Commands
///
/// Tauri IPC handlers for assessing registration risk (structural alerts,
/// PBT/vPvB, groundwater concern, CLP aquatic hazard, acute mammalian tox).

use crate::AppState;
use serde_json::json;
use tauri::State;

/// Assess registration risk for a single compound.
/// Returns a full scorecard with per-criterion verdicts and overall risk.
#[tauri::command]
pub fn assess_registration_risk(
    state: State<'_, AppState>,
    smiles: String,
    use_predicted_fate: Option<bool>,
    fate_data: Option<serde_json::Value>,
) -> Result<serde_json::Value, String> {
    if smiles.is_empty() {
        return Err("SMILES string cannot be empty".to_string());
    }

    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    let mut params = json!({
        "smiles": smiles,
        "use_predicted_fate": use_predicted_fate.unwrap_or(true),
    });

    if let Some(fate) = fate_data {
        params["fate_data"] = fate;
    }

    engine.send_request("registration_risk", params)
}

/// Assess registration risk for a batch of compounds.
/// Returns an array of scorecards.
#[tauri::command]
pub fn assess_registration_risk_batch(
    state: State<'_, AppState>,
    smiles_list: Vec<String>,
    use_predicted_fate: Option<bool>,
) -> Result<serde_json::Value, String> {
    if smiles_list.is_empty() {
        return Ok(json!([]));
    }

    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request(
        "registration_risk",
        json!({
            "smiles_list": smiles_list,
            "use_predicted_fate": use_predicted_fate.unwrap_or(true),
        }),
    )
}
