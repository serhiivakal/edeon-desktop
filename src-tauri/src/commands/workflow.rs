/// Edeon Desktop — Workflow Commands
///
/// Tauri IPC handlers for running cheminformatics workflows.
/// Stages: Standardize → Properties → Pesticide-likeness

use crate::models::WorkflowRecord;
use crate::python::PythonEngine;
use crate::AppState;
use chrono::Utc;
use rusqlite::params;
use serde_json::json;
use tauri::{Emitter, State};
use uuid::Uuid;

/// Start a workflow on the active project's compounds.
/// Runs synchronously through all 3 stages.
#[tauri::command]
pub fn start_workflow(
    app: tauri::AppHandle,
    state: State<'_, AppState>,
    project_id: String,
    workflow_name: Option<String>,
) -> Result<WorkflowRecord, String> {
    let workflow_id = Uuid::new_v4().to_string();
    let name = workflow_name.unwrap_or_else(|| "Lead Optimization Pre-Screen".to_string());
    let now = Utc::now().to_rfc3339();

    // Create workflow record
    {
        let db = state.db.lock().map_err(|e| e.to_string())?;
        db.execute(
            "INSERT INTO workflows (id, project_id, name, status, started_at) VALUES (?1, ?2, ?3, 'running', ?4)",
            params![workflow_id, project_id, name, now],
        ).map_err(|e| e.to_string())?;
    }

    // Load all compound SMILES for this project
    let compounds: Vec<(String, String, String)> = {
        let db = state.db.lock().map_err(|e| e.to_string())?;
        let mut stmt = db.prepare(
            "SELECT id, name, smiles FROM compounds WHERE project_id = ?1 ORDER BY name"
        ).map_err(|e| e.to_string())?;
        let rows = stmt.query_map(params![project_id], |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, String>(2)?,
            ))
        }).map_err(|e| e.to_string())?;
        rows.collect::<Result<Vec<_>, _>>().map_err(|e| e.to_string())?
    };

    let total = compounds.len() as i64;

    if total == 0 {
        // Mark workflow as failed
        let db = state.db.lock().map_err(|e| e.to_string())?;
        db.execute(
            "UPDATE workflows SET status = 'failed', completed_at = ?1 WHERE id = ?2",
            params![Utc::now().to_rfc3339(), workflow_id],
        ).map_err(|e| e.to_string())?;
        return Err("No compounds in project to process".to_string());
    }

    // Emit initial status
    let _ = app.emit("workflow://progress", json!({
        "workflow_id": workflow_id,
        "status": "running",
        "current_stage": "Standardize",
        "stages_complete": 0,
        "total_stages": 3,
        "compounds_processed": 0,
        "compounds_total": total,
    }));

    // Spawn Python engine
    let mut engine = {
        let mut py = state.python.lock().map_err(|e| e.to_string())?;
        if py.is_none() {
            *py = Some(PythonEngine::spawn()?);
        }
        // We need to take it out to use it (can't hold the lock during long operations)
        py.take().ok_or("Python engine not available")?
    };

    // ─── Stage 1: Standardize ───────────────────────────────
    let smiles_list: Vec<&str> = compounds.iter().map(|(_, _, s)| s.as_str()).collect();
    let std_result = engine.send_request("standardize", json!({
        "smiles": smiles_list,
    }));

    let standardized = match std_result {
        Ok(result) => {
            let arr = result.as_array().ok_or("Expected array from standardize")?;
            // Update canonical SMILES in DB
            let db = state.db.lock().map_err(|e| e.to_string())?;
            for (i, item) in arr.iter().enumerate() {
                if let Some(canonical) = item.get("canonical").and_then(|v| v.as_str()) {
                    let compound_id = &compounds[i].0;
                    let _ = db.execute(
                        "UPDATE compounds SET smiles = ?1 WHERE id = ?2",
                        params![canonical, compound_id],
                    );
                }
            }
            arr.clone()
        }
        Err(e) => {
            // Put engine back and fail
            let mut py = state.python.lock().map_err(|e2| e2.to_string())?;
            *py = Some(engine);
            update_workflow_failed(&state, &workflow_id, &format!("Standardize failed: {}", e))?;
            return Err(format!("Standardize stage failed: {}", e));
        }
    };

    // Count valid compounds
    let valid_count = standardized.iter()
        .filter(|s| s.get("valid").and_then(|v| v.as_bool()).unwrap_or(false))
        .count();

    let _ = app.emit("workflow://progress", json!({
        "workflow_id": workflow_id,
        "status": "running",
        "current_stage": "Properties",
        "stages_complete": 1,
        "total_stages": 3,
        "compounds_processed": valid_count,
        "compounds_total": total,
        "stage_result": {
            "stage": "Standardize",
            "status": "done",
            "compound_count": total,
            "valid_count": valid_count,
        },
    }));

    // ─── Stage 2: Compute Properties ────────────────────────
    let valid_smiles: Vec<&str> = standardized.iter()
        .filter_map(|s| {
            if s.get("valid").and_then(|v| v.as_bool()).unwrap_or(false) {
                s.get("canonical").and_then(|v| v.as_str())
            } else {
                None
            }
        })
        .collect();

    let props_result = engine.send_request("compute_properties", json!({
        "smiles": valid_smiles,
    }));

    let properties = match props_result {
        Ok(result) => {
            let arr = result.as_array().ok_or("Expected array from compute_properties")?;
            // Update compound properties in DB
            let db = state.db.lock().map_err(|e| e.to_string())?;
            let mut prop_idx = 0;
            for (i, std_item) in standardized.iter().enumerate() {
                let is_valid = std_item.get("valid").and_then(|v| v.as_bool()).unwrap_or(false);
                if !is_valid {
                    continue;
                }
                if prop_idx >= arr.len() {
                    break;
                }
                let props = &arr[prop_idx];
                let compound_id = &compounds[i].0;
                let _ = db.execute(
                    "UPDATE compounds SET mol_weight = ?1, logp = ?2, tpsa = ?3, hbd = ?4, hba = ?5, rotatable_bonds = ?6 WHERE id = ?7",
                    params![
                        props.get("mol_weight").and_then(|v| v.as_f64()),
                        props.get("logp").and_then(|v| v.as_f64()),
                        props.get("tpsa").and_then(|v| v.as_f64()),
                        props.get("hbd").and_then(|v| v.as_i64()),
                        props.get("hba").and_then(|v| v.as_i64()),
                        props.get("rotatable_bonds").and_then(|v| v.as_i64()),
                        compound_id,
                    ],
                );
                prop_idx += 1;
            }
            arr.clone()
        }
        Err(e) => {
            let mut py = state.python.lock().map_err(|e2| e2.to_string())?;
            *py = Some(engine);
            update_workflow_failed(&state, &workflow_id, &format!("Properties failed: {}", e))?;
            return Err(format!("Properties stage failed: {}", e));
        }
    };

    let _ = app.emit("workflow://progress", json!({
        "workflow_id": workflow_id,
        "status": "running",
        "current_stage": "Pesticide-likeness",
        "stages_complete": 2,
        "total_stages": 3,
        "compounds_processed": valid_count,
        "compounds_total": total,
        "stage_result": {
            "stage": "Properties",
            "status": "done",
            "compound_count": valid_count,
        },
    }));

    // ─── Stage 3: Pesticide-likeness ────────────────────────
    let tice_result = engine.send_request("pesticide_likeness", json!({
        "compounds": properties,
    }));

    match tice_result {
        Ok(result) => {
            let arr = result.as_array().ok_or("Expected array from pesticide_likeness")?;
            // Store workflow results
            let db = state.db.lock().map_err(|e| e.to_string())?;
            let mut prop_idx = 0;
            for (i, std_item) in standardized.iter().enumerate() {
                let is_valid = std_item.get("valid").and_then(|v| v.as_bool()).unwrap_or(false);
                if !is_valid {
                    continue;
                }
                if prop_idx >= arr.len() {
                    break;
                }
                let tice = &arr[prop_idx];
                let compound_id = &compounds[i].0;
                let result_id = Uuid::new_v4().to_string();

                let level = tice.get("level").and_then(|v| v.as_str()).unwrap_or("Low");
                let violations = tice.get("violations").and_then(|v| v.as_array())
                    .map(|a| a.iter().filter_map(|v| v.as_str()).collect::<Vec<_>>().join("; "))
                    .unwrap_or_default();

                // Calculate a simple composite score based on properties + tice
                let props = &properties[prop_idx];
                let score = compute_score(props, level);

                let results_json = json!({
                    "pesticide_likeness": level,
                    "violations": violations,
                    "score": score,
                }).to_string();

                let _ = db.execute(
                    "INSERT OR REPLACE INTO workflow_results (id, workflow_id, compound_id, stage, results_json, score) VALUES (?1, ?2, ?3, 'pesticide_likeness', ?4, ?5)",
                    params![result_id, workflow_id, compound_id, results_json, score],
                );
                prop_idx += 1;
            }
        }
        Err(e) => {
            let mut py = state.python.lock().map_err(|e2| e2.to_string())?;
            *py = Some(engine);
            update_workflow_failed(&state, &workflow_id, &format!("Tice rules failed: {}", e))?;
            return Err(format!("Pesticide-likeness stage failed: {}", e));
        }
    }

    // Put engine back
    {
        let mut py = state.python.lock().map_err(|e| e.to_string())?;
        *py = Some(engine);
    }

    // Mark workflow complete
    let completed_at = Utc::now().to_rfc3339();
    {
        let db = state.db.lock().map_err(|e| e.to_string())?;
        db.execute(
            "UPDATE workflows SET status = 'complete', completed_at = ?1 WHERE id = ?2",
            params![completed_at, workflow_id],
        ).map_err(|e| e.to_string())?;
    }

    let _ = app.emit("workflow://progress", json!({
        "workflow_id": workflow_id,
        "status": "complete",
        "current_stage": null,
        "stages_complete": 3,
        "total_stages": 3,
        "compounds_processed": total,
        "compounds_total": total,
        "stage_result": {
            "stage": "Pesticide-likeness",
            "status": "done",
            "compound_count": valid_count,
        },
    }));

    // Build the workflow record to return
    Ok(WorkflowRecord {
        id: workflow_id,
        project_id,
        name,
        status: "complete".to_string(),
        stages_complete: 3,
        total_stages: 3,
        compounds_processed: total,
        compounds_total: total,
        current_stage: None,
        started_at: now,
        completed_at: Some(completed_at),
    })
}

/// Get the status of a workflow.
#[tauri::command]
pub fn get_workflow_status(
    state: State<'_, AppState>,
    workflow_id: String,
) -> Result<WorkflowRecord, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;

    db.query_row(
        "SELECT id, project_id, name, status, started_at, completed_at FROM workflows WHERE id = ?1",
        params![workflow_id],
        |row| {
            Ok(WorkflowRecord {
                id: row.get(0)?,
                project_id: row.get(1)?,
                name: row.get(2)?,
                status: row.get(3)?,
                stages_complete: if row.get::<_, String>(3)? == "complete" { 3 } else { 0 },
                total_stages: 3,
                compounds_processed: 0,
                compounds_total: 0,
                current_stage: None,
                started_at: row.get(4)?,
                completed_at: row.get(5)?,
            })
        },
    ).map_err(|e| e.to_string())
}

/// Get workflow results (compounds with scores).
#[tauri::command]
pub fn get_workflow_results(
    state: State<'_, AppState>,
    workflow_id: String,
) -> Result<Vec<serde_json::Value>, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;

    let mut stmt = db.prepare(
        "SELECT c.id, c.name, c.smiles, c.mol_weight, c.logp, c.tpsa, c.hbd, c.hba, c.rotatable_bonds,
                wr.results_json, wr.score
         FROM workflow_results wr
         JOIN compounds c ON wr.compound_id = c.id
         WHERE wr.workflow_id = ?1
         ORDER BY wr.score DESC"
    ).map_err(|e| e.to_string())?;

    let rows = stmt.query_map(params![workflow_id], |row| {
        let results_json: Option<String> = row.get(9)?;
        let parsed = results_json
            .as_ref()
            .and_then(|s| serde_json::from_str::<serde_json::Value>(s).ok())
            .unwrap_or(json!({}));

        Ok(json!({
            "id": row.get::<_, String>(0)?,
            "name": row.get::<_, String>(1)?,
            "smiles": row.get::<_, String>(2)?,
            "mol_weight": row.get::<_, Option<f64>>(3)?,
            "logp": row.get::<_, Option<f64>>(4)?,
            "tpsa": row.get::<_, Option<f64>>(5)?,
            "hbd": row.get::<_, Option<i32>>(6)?,
            "hba": row.get::<_, Option<i32>>(7)?,
            "rotatable_bonds": row.get::<_, Option<i32>>(8)?,
            "pesticide_likeness": parsed.get("pesticide_likeness"),
            "violations": parsed.get("violations"),
            "score": row.get::<_, Option<f64>>(10)?,
        }))
    }).map_err(|e| e.to_string())?;

    rows.collect::<Result<Vec<_>, _>>().map_err(|e| e.to_string())
}

/// List workflows for a project.
#[tauri::command]
pub fn list_workflows(
    state: State<'_, AppState>,
    project_id: String,
) -> Result<Vec<WorkflowRecord>, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;

    let mut stmt = db.prepare(
        "SELECT id, project_id, name, status, started_at, completed_at FROM workflows WHERE project_id = ?1 ORDER BY started_at DESC"
    ).map_err(|e| e.to_string())?;

    let rows = stmt.query_map(params![project_id], |row| {
        Ok(WorkflowRecord {
            id: row.get(0)?,
            project_id: row.get(1)?,
            name: row.get(2)?,
            status: row.get(3)?,
            stages_complete: if row.get::<_, String>(3)? == "complete" { 3 } else { 0 },
            total_stages: 3,
            compounds_processed: 0,
            compounds_total: 0,
            current_stage: None,
            started_at: row.get(4)?,
            completed_at: row.get(5)?,
        })
    }).map_err(|e| e.to_string())?;

    rows.collect::<Result<Vec<_>, _>>().map_err(|e| e.to_string())
}

/// Check if the Python engine is available.
#[tauri::command]
pub fn check_python_engine(state: State<'_, AppState>) -> Result<bool, String> {
    let mut py = state.python.lock().map_err(|e| e.to_string())?;

    if let Some(ref mut engine) = *py {
        match engine.ping() {
            Ok(true) => Ok(true),
            _ => {
                // Engine is dead, remove it
                *py = None;
                Ok(false)
            }
        }
    } else {
        // Try to spawn
        match PythonEngine::spawn() {
            Ok(engine) => {
                *py = Some(engine);
                Ok(true)
            }
            Err(_) => Ok(false),
        }
    }
}

/// Compute a simple composite score (0–10) based on properties and tice level.
fn compute_score(props: &serde_json::Value, tice_level: &str) -> f64 {
    let mut score: f64 = 5.0; // Base score

    // Tice bonus
    match tice_level {
        "High" => score += 3.0,
        "Med" => score += 1.5,
        _ => {} // "Low" gets no bonus
    }

    // MW penalty/bonus (ideal: 200–400)
    if let Some(mw) = props.get("mol_weight").and_then(|v| v.as_f64()) {
        if (200.0..=400.0).contains(&mw) {
            score += 1.0;
        } else if mw > 500.0 || mw < 150.0 {
            score -= 1.0;
        }
    }

    // LogP penalty (ideal: 0–4)
    if let Some(logp) = props.get("logp").and_then(|v| v.as_f64()) {
        if (0.0..=4.0).contains(&logp) {
            score += 1.0;
        } else if logp > 6.0 || logp < -2.0 {
            score -= 1.0;
        }
    }

    // Clamp to 0–10
    score.clamp(0.0, 10.0)
}

fn update_workflow_failed(
    state: &State<'_, AppState>,
    workflow_id: &str,
    _error: &str,
) -> Result<(), String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    db.execute(
        "UPDATE workflows SET status = 'failed', completed_at = ?1 WHERE id = ?2",
        params![Utc::now().to_rfc3339(), workflow_id],
    ).map_err(|e| e.to_string())?;
    Ok(())
}
