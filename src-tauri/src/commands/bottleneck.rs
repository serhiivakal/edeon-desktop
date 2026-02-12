/// Edeon Desktop — Bottleneck Analyzer Commands
///
/// Tauri IPC handlers for the L1 Bottleneck Analyzer.
/// Delegates computation to Python, persists results in SQLite,
/// and emits journal entries (via journal::append inside a transaction).

use crate::AppState;
use crate::journal;
use serde_json::json;
use tauri::State;

/// Full portfolio bottleneck analysis.
/// Persists the result in `bottleneck_analyses` and emits a `bottleneck_identified`
/// journal entry atomically (INV-1).
#[tauri::command]
pub fn bottleneck_analyze(
    state: State<'_, AppState>,
    project_id: String,
    compounds: serde_json::Value,
    profile: Option<String>,
    user_weights: Option<serde_json::Value>,
) -> Result<serde_json::Value, String> {
    let profile_id = profile.unwrap_or_else(|| "agrochem_default".to_string());

    // 1. Run the analysis in Python
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    let mut params = json!({
        "compounds": compounds,
        "profile": profile_id,
        "project_id": project_id,
    });
    if let Some(w) = user_weights {
        params["user_weights"] = w;
    }

    let result = engine.send_request("bottleneck.analyze", params)?;

    // 2. Persist analysis + journal entry atomically
    let analysis_id = result["analysis_id"].as_str().unwrap_or("").to_string();
    let top_endpoint = result["top_endpoint"].as_str().map(|s| s.to_string());
    let top_kind = result["top_kind"].as_str().map(|s| s.to_string());
    let ambiguous = result["bottleneck_ambiguous"].as_bool().unwrap_or(false);
    let n_compounds = result["n_compounds"].as_i64().unwrap_or(0) as i32;
    let params_hash = result["params_hash"].as_str().unwrap_or("").to_string();
    let payload_json = serde_json::to_string(&result).unwrap_or_default();

    {
        let mut db = state.db.lock().map_err(|e| format!("DB lock error: {}", e))?;
        let tx = db.transaction().map_err(|e| format!("TX begin error: {}", e))?;

        // Insert analysis record
        tx.execute(
            "INSERT INTO bottleneck_analyses (analysis_id, project_id, profile, n_compounds, top_endpoint, top_kind, ambiguous, payload_json, params_hash)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)",
            rusqlite::params![
                analysis_id,
                project_id,
                profile_id,
                n_compounds,
                top_endpoint,
                top_kind,
                ambiguous as i32,
                payload_json,
                params_hash,
            ],
        ).map_err(|e| format!("Insert bottleneck_analyses failed: {}", e))?;

        // Emit journal entry from the payload Python built
        if let Some(jp) = result.get("journal_payload") {
            let summary = jp["summary"].as_str().unwrap_or("Bottleneck analysis completed");
            let provenance = serde_json::to_string(&jp["provenance"]).unwrap_or_else(|_| "{}".to_string());

            let mut entry = journal::JournalEntry::new_system(
                &project_id,
                "bottleneck_identified",
                "analysis",
                &analysis_id,
                summary,
                &provenance,
            );

            if let Some(r) = jp.get("rationale") {
                entry.rationale_json = Some(serde_json::to_string(r).unwrap_or_default());
            }
            if let Some(a) = jp.get("alternatives") {
                entry.alternatives_json = Some(serde_json::to_string(a).unwrap_or_default());
            }
            if let Some(c) = jp.get("confidence") {
                entry.confidence_json = Some(serde_json::to_string(c).unwrap_or_default());
            }

            journal::append(&tx, &entry)?;
        }

        tx.commit().map_err(|e| format!("TX commit error: {}", e))?;
    }

    Ok(result)
}

/// Per-compound weakest-link analysis.
#[tauri::command]
pub fn bottleneck_compound(
    state: State<'_, AppState>,
    compound: serde_json::Value,
    profile: Option<String>,
) -> Result<serde_json::Value, String> {
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request("bottleneck.compound", json!({
        "compound": compound,
        "profile": profile.unwrap_or_else(|| "agrochem_default".to_string()),
    }))
}

/// Gate-attrition analysis from workflow run data.
#[tauri::command]
pub fn bottleneck_attrition(
    state: State<'_, AppState>,
    gate_results: serde_json::Value,
) -> Result<serde_json::Value, String> {
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request("bottleneck.attrition", json!({
        "gate_results": gate_results,
    }))
}

/// Suggest K10 objective weights from leverage profile.
#[tauri::command]
pub fn bottleneck_suggest_weights(
    state: State<'_, AppState>,
    leverage_results: serde_json::Value,
) -> Result<serde_json::Value, String> {
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request("bottleneck.suggest_weights", json!({
        "leverage_results": leverage_results,
    }))
}

/// List available desirability profiles.
#[tauri::command]
pub fn bottleneck_list_profiles(
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request("bottleneck.list_profiles", json!({}))
}
