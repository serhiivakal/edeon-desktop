/// Edeon Desktop — Prescriptive Design & Generation Commands
///
/// Tauri IPC handlers for suggesting molecular analogs via CReM mutations,
/// batch virtual screenings with EasyDock, closed-loop scoring pipelines,
/// and persisting generation jobs in the local SQLite database.

use crate::AppState;
use serde_json::{json, Value};
use tauri::{AppHandle, State};

/// Suggest molecular analogs for a query compound.
/// Returns ranked suggestions with predicted deltas across all endpoints.
#[tauri::command]
pub fn suggest_analogs(
    state: State<'_, AppState>,
    smiles: String,
    improve: String,
    preserve: Option<Vec<String>>,
    n: Option<u32>,
) -> Result<serde_json::Value, String> {
    if smiles.is_empty() {
        return Err("SMILES string cannot be empty".to_string());
    }

    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request(
        "suggest_analogs",
        json!({
            "smiles": smiles,
            "improve": improve,
            "preserve": preserve.unwrap_or_default(),
            "n": n.unwrap_or(20),
        }),
    )
}

/// Mutate a molecule using CReM core mutator.
#[tauri::command]
pub async fn crem_generate(
    state: State<'_, AppState>,
    smiles: String,
    radius: u32,
    min_size: u32,
    max_size: u32,
    max_mutants: u32,
) -> Result<serde_json::Value, String> {
    if smiles.is_empty() {
        return Err("SMILES string cannot be empty".to_string());
    }

    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request(
        "crem_generate",
        json!({
            "smiles": smiles,
            "radius": radius,
            "min_size": min_size,
            "max_size": max_size,
            "max_mutants": max_mutants,
        }),
    )
}

/// Run batch virtual screening using EasyDock and save to SQLite history.
#[tauri::command]
pub async fn easydock_dock(
    app: AppHandle,
    state: State<'_, AppState>,
    job_name: String,
    receptor_hash: String,
    receptor_display_name: String,
    smiles: Vec<String>,
    box_center: (f64, f64, f64),
    box_size: (f64, f64, f64),
    engine_name: String,
) -> Result<serde_json::Value, String> {
    if smiles.is_empty() {
        return Err("Ligands list cannot be empty".to_string());
    }

    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    let params = json!({
        "receptor_hash": receptor_hash,
        "smiles": smiles,
        "box_center": box_center,
        "box_size": box_size,
        "engine": engine_name,
    });

    // Run docking with progress streams
    let result = engine.send_request_with_app("easydock_dock", params, Some(&app))?;
    
    // Save to SQLite history
    let job_id = uuid::Uuid::new_v4().to_string();
    let completed_at = chrono::Utc::now().to_rfc3339();
    let total_docked = smiles.len() as i64;
    
    let parameters = json!({
        "receptor_hash": receptor_hash,
        "box_center": box_center,
        "box_size": box_size,
        "engine": engine_name,
    });

    let db = state.db.lock().map_err(|e| e.to_string())?;
    db.execute(
        "INSERT INTO generation_jobs (
            job_id, name, mode, parent_smiles, receptor_id, receptor_display_name,
            parameters_json, results_json, total_generated, total_docked, elapsed_seconds, completed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            &job_id,
            &job_name,
            "EasyDock Batch",
            None::<String>,
            &receptor_hash,
            &receptor_display_name,
            &parameters.to_string(),
            &result.to_string(),
            0,
            total_docked,
            0.0,
            &completed_at,
        ),
    ).map_err(|e| e.to_string())?;

    Ok(result)
}

/// Run closed-loop design pipeline (mutation + docking + property scoring) and save to SQLite.
#[tauri::command]
pub async fn crem_dock_run(
    app: AppHandle,
    state: State<'_, AppState>,
    job_name: String,
    parent_smiles: String,
    receptor_hash: String,
    receptor_display_name: String,
    box_center: (f64, f64, f64),
    box_size: (f64, f64, f64),
    n_iterations: u32,
    population_size: u32,
    keep_top_n: u32,
    weights: Option<serde_json::Value>,
) -> Result<serde_json::Value, String> {
    if parent_smiles.is_empty() {
        return Err("Parent SMILES cannot be empty".to_string());
    }

    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    let params = json!({
        "smiles": parent_smiles,
        "receptor_hash": receptor_hash,
        "box_center": box_center,
        "box_size": box_size,
        "n_iterations": n_iterations,
        "population_size": population_size,
        "keep_top_n": keep_top_n,
        "weights": weights.clone().unwrap_or(json!({})),
    });

    // Run pipeline with progress streams
    let result = engine.send_request_with_app("crem_dock_run", params, Some(&app))?;
    
    // Parse response metrics
    let total_generated = result.get("total_compounds_generated").and_then(|v| v.as_i64()).unwrap_or(0);
    let total_docked = result.get("total_compounds_docked").and_then(|v| v.as_i64()).unwrap_or(0);
    let elapsed = result.get("elapsed_seconds").and_then(|v| v.as_f64()).unwrap_or(0.0);

    // Save to SQLite history
    let job_id = uuid::Uuid::new_v4().to_string();
    let completed_at = chrono::Utc::now().to_rfc3339();
    
    let parameters = json!({
        "parent_smiles": parent_smiles,
        "receptor_hash": receptor_hash,
        "box_center": box_center,
        "box_size": box_size,
        "n_iterations": n_iterations,
        "population_size": population_size,
        "keep_top_n": keep_top_n,
        "weights": weights.unwrap_or(json!({})),
    });

    let mut db = state.db.lock().map_err(|e| e.to_string())?;
    let tx = db.transaction().map_err(|e| e.to_string())?;

    tx.execute(
        "INSERT INTO generation_jobs (
            job_id, name, mode, parent_smiles, receptor_id, receptor_display_name,
            parameters_json, results_json, total_generated, total_docked, elapsed_seconds, completed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            &job_id,
            &job_name,
            "CReM-dock",
            &parent_smiles,
            &receptor_hash,
            &receptor_display_name,
            &parameters.to_string(),
            &result.to_string(),
            total_generated,
            total_docked,
            elapsed,
            &completed_at,
        ),
    ).map_err(|e| e.to_string())?;

    let summary = format!("Analog generation job '{}' registered {} analogs for parent SMILES", job_name, total_generated);
    let entry = crate::journal::JournalEntry::new_system(
        "global",
        "analog_registered",
        "campaign",
        &job_id,
        &summary,
        &parameters.to_string(),
    );
    let _ = crate::journal::append(&tx, &entry);

    tx.commit().map_err(|e| e.to_string())?;

    Ok(result)
}

/// Retrieve the generation jobs history list from SQLite.
#[tauri::command]
pub fn generation_history_list(
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    let mut stmt = db.prepare(
        "SELECT job_id, name, mode, parent_smiles, receptor_id, receptor_display_name,
                total_generated, total_docked, elapsed_seconds, completed_at
         FROM generation_jobs
         ORDER BY completed_at DESC"
    ).map_err(|e| e.to_string())?;

    let rows = stmt.query_map([], |row| {
        Ok(json!({
            "job_id": row.get::<_, String>(0)?,
            "name": row.get::<_, String>(1)?,
            "mode": row.get::<_, String>(2)?,
            "parent_smiles": row.get::<_, Option<String>>(3)?,
            "receptor_id": row.get::<_, Option<String>>(4)?,
            "receptor_display_name": row.get::<_, Option<String>>(5)?,
            "total_generated": row.get::<_, i64>(6)?,
            "total_docked": row.get::<_, i64>(7)?,
            "elapsed_seconds": row.get::<_, f64>(8)?,
            "completed_at": row.get::<_, String>(9)?,
        }))
    }).map_err(|e| e.to_string())?;

    let mut list = Vec::new();
    for row in rows {
        list.push(row.map_err(|e| e.to_string())?);
    }

    Ok(Value::Array(list))
}

/// Load a specific generation job's parameters and results.
#[tauri::command]
pub fn generation_history_load(
    state: State<'_, AppState>,
    job_id: String,
) -> Result<serde_json::Value, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    let mut stmt = db.prepare(
        "SELECT job_id, name, mode, parent_smiles, receptor_id, receptor_display_name,
                parameters_json, results_json, total_generated, total_docked, elapsed_seconds, completed_at
         FROM generation_jobs
         WHERE job_id = ?"
    ).map_err(|e| e.to_string())?;

    let mut rows = stmt.query_map([job_id], |row| {
        let params_str: String = row.get(6)?;
        let results_str: String = row.get(7)?;
        
        let parameters: Value = serde_json::from_str(&params_str)
            .unwrap_or(Value::Null);
        let results: Value = serde_json::from_str(&results_str)
            .unwrap_or(Value::Null);

        Ok(json!({
            "job_id": row.get::<_, String>(0)?,
            "name": row.get::<_, String>(1)?,
            "mode": row.get::<_, String>(2)?,
            "parent_smiles": row.get::<_, Option<String>>(3)?,
            "receptor_id": row.get::<_, Option<String>>(4)?,
            "receptor_display_name": row.get::<_, Option<String>>(5)?,
            "parameters": parameters,
            "results": results,
            "total_generated": row.get::<_, i64>(8)?,
            "total_docked": row.get::<_, i64>(9)?,
            "elapsed_seconds": row.get::<_, f64>(10)?,
            "completed_at": row.get::<_, String>(11)?,
        }))
    }).map_err(|e| e.to_string())?;

    if let Some(row_res) = rows.next() {
        Ok(row_res.map_err(|e| e.to_string())?)
    } else {
        Err("Job not found".to_string())
    }
}

/// Delete a specific generation job from history.
#[tauri::command]
pub fn generation_history_delete(
    state: State<'_, AppState>,
    job_id: String,
) -> Result<bool, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    db.execute("DELETE FROM generation_jobs WHERE job_id = ?", [job_id])
        .map_err(|e| e.to_string())?;
    Ok(true)
}

/// List available RDKit reaction SMARTS templates.
#[tauri::command]
pub fn gen_reaction_list_templates(
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request("gen.reaction_list_templates", json!({}))
}

/// Run combinatorial reaction product enumeration.
#[tauri::command]
pub fn gen_reaction_enumerate(
    state: State<'_, AppState>,
    template_id: String,
    core_smiles: Option<String>,
    reagent_catalogs: Option<Vec<String>>,
    max_products: Option<usize>,
    apply_filters: Option<serde_json::Value>,
    retro_gate: Option<serde_json::Value>,
) -> Result<serde_json::Value, String> {
    let mut py = state.get_python_engine()?;
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request("gen.reaction_enumerate", json!({
        "template_id": template_id,
        "core_smiles": core_smiles,
        "reagent_catalogs": reagent_catalogs,
        "max_products": max_products.unwrap_or(500),
        "apply_filters": apply_filters.unwrap_or(json!({"tice": true, "pains": true})),
        "retro_gate": retro_gate.unwrap_or(json!({"enabled": true, "sa_threshold": 0.4})),
    }))
}
