/// Edeon Desktop — Docking Commands
///
/// Tauri IPC handlers for molecular docking calculations and history.

use crate::AppState;
use tauri::{State, AppHandle};
use std::path::PathBuf;

/// Helper to resolve cache paths relative to project root or CWD
fn resolve_cache_path(result_path: &str) -> PathBuf {
    let direct = PathBuf::from(result_path);
    if direct.exists() {
        return direct;
    }
    let dev = PathBuf::from("../").join(result_path);
    if dev.exists() {
        return dev;
    }
    direct
}

/// Helper to run a standard Python engine JSON-RPC command
fn run_python_command(state: &State<'_, AppState>, method: &str, params: serde_json::Value) -> Result<serde_json::Value, String> {
    let mut engine = {
        let mut py = state.python.lock().map_err(|e| e.to_string())?;
        if py.is_none() {
            *py = Some(crate::python::PythonEngine::spawn()?);
        }
        py.take().ok_or("Python engine not available")?
    };

    let result = engine.send_request(method, params);

    if let Ok(mut py) = state.python.lock() {
        *py = Some(engine);
    }
    result
}

/// Helper to run a Python command with AppHandle to support progress stream forwarding
fn run_python_command_with_app(
    state: &State<'_, AppState>,
    method: &str,
    params: serde_json::Value,
    app: &tauri::AppHandle,
) -> Result<serde_json::Value, String> {
    let mut engine = {
        let mut py = state.python.lock().map_err(|e| e.to_string())?;
        if py.is_none() {
            *py = Some(crate::python::PythonEngine::spawn()?);
        }
        py.take().ok_or("Python engine not available")?
    };

    let result = engine.send_request_with_app(method, params, Some(app));

    if let Ok(mut py) = state.python.lock() {
        *py = Some(engine);
    }
    result
}

#[tauri::command]
pub fn receptor_load_from_source(
    state: State<'_, AppState>,
    source_type: String,
    identifier: String,
) -> Result<serde_json::Value, String> {
    run_python_command(&state, "receptor_load_from_source", serde_json::json!({
        "source_type": source_type,
        "identifier": identifier
    }))
}

#[tauri::command]
pub fn receptor_get_het_list(
    state: State<'_, AppState>,
    receptor_hash: String,
) -> Result<serde_json::Value, String> {
    run_python_command(&state, "receptor_get_het_list", serde_json::json!({
        "receptor_hash": receptor_hash
    }))
}

#[tauri::command]
pub fn receptor_reprepare(
    state: State<'_, AppState>,
    receptor_hash: String,
    params: serde_json::Value,
) -> Result<serde_json::Value, String> {
    run_python_command(&state, "receptor_reprepare", serde_json::json!({
        "receptor_hash": receptor_hash,
        "params": params
    }))
}

#[tauri::command]
pub fn ligand_prepare(
    state: State<'_, AppState>,
    smiles: String,
    params: serde_json::Value,
) -> Result<serde_json::Value, String> {
    run_python_command(&state, "ligand_prepare", serde_json::json!({
        "smiles": smiles,
        "params": params
    }))
}

#[tauri::command]
pub fn pocket_detect(
    state: State<'_, AppState>,
    receptor_hash: String,
) -> Result<serde_json::Value, String> {
    run_python_command(&state, "pocket_detect", serde_json::json!({
        "receptor_hash": receptor_hash
    }))
}

#[tauri::command]
pub fn docking_run(
    state: State<'_, AppState>,
    app: AppHandle,
    spec: serde_json::Value,
    ligand_smiles: String,
    receptor_display_name: Option<String>,
    ligand_display_name: Option<String>,
) -> Result<serde_json::Value, String> {
    let mut result = run_python_command_with_app(&state, "docking_run", serde_json::json!({
        "spec": spec
    }), &app)?;

    let job_id = result.get("job_id").and_then(|v| v.as_str()).ok_or("Missing job_id in docking result")?;
    let completed_at = result.get("completed_at").and_then(|v| v.as_str()).ok_or("Missing completed_at in docking result")?;
    let elapsed_seconds = result.get("elapsed_seconds").and_then(|v| v.as_f64()).unwrap_or(0.0);
    
    let spec_obj = result.get("spec").ok_or("Missing spec in docking result")?;
    let receptor_hash = spec_obj.get("receptor_hash").and_then(|v| v.as_str()).ok_or("Missing receptor_hash in spec")?;
    
    let box_center = spec_obj.get("box_center").and_then(|v| v.as_array()).ok_or("Missing box_center in spec")?;
    let box_size = spec_obj.get("box_size").and_then(|v| v.as_array()).ok_or("Missing box_size in spec")?;
    
    let box_center_x = box_center.get(0).and_then(|v| v.as_f64()).unwrap_or(0.0);
    let box_center_y = box_center.get(1).and_then(|v| v.as_f64()).unwrap_or(0.0);
    let box_center_z = box_center.get(2).and_then(|v| v.as_f64()).unwrap_or(0.0);
    
    let box_size_x = box_size.get(0).and_then(|v| v.as_f64()).unwrap_or(0.0);
    let box_size_y = box_size.get(1).and_then(|v| v.as_f64()).unwrap_or(0.0);
    let box_size_z = box_size.get(2).and_then(|v| v.as_f64()).unwrap_or(0.0);
    
    let poses = result.get("poses").and_then(|v| v.as_array()).ok_or("Missing poses in result")?;
    let num_poses = poses.len() as i32;
    let top_score = if num_poses > 0 {
        poses.get(0).and_then(|p| p.get("score_kcal_per_mol")).and_then(|v| v.as_f64()).unwrap_or(0.0)
    } else {
        0.0
    };
    
    let result_path = format!("data/docking/cache/jobs/{}/result.json", job_id);
    
    // Insert job into database
    let db = state.db.lock().map_err(|e| e.to_string())?;
    db.execute(
        "INSERT OR REPLACE INTO docking_jobs (
            job_id, receptor_id, receptor_display_name, ligand_smiles, ligand_display_name,
            box_center_x, box_center_y, box_center_z,
            box_size_x, box_size_y, box_size_z,
            top_score, num_poses, elapsed_seconds, completed_at, starred,
            job_spec_json, result_path
         ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15, 0, ?16, ?17)",
        rusqlite::params![
            job_id,
            receptor_hash,
            receptor_display_name,
            ligand_smiles,
            ligand_display_name,
            box_center_x,
            box_center_y,
            box_center_z,
            box_size_x,
            box_size_y,
            box_size_z,
            top_score,
            num_poses,
            elapsed_seconds,
            completed_at,
            serde_json::to_string(&spec).unwrap_or_default(),
            result_path
        ],
    ).map_err(|e| e.to_string())?;
    
    if let serde_json::Value::Object(ref mut map) = result {
        if !map.contains_key("receptor_display_name") {
            map.insert("receptor_display_name".to_string(), serde_json::to_value(&receptor_display_name).unwrap_or(serde_json::Value::Null));
        }
        if !map.contains_key("ligand_display_name") {
            map.insert("ligand_display_name".to_string(), serde_json::to_value(&ligand_display_name).unwrap_or(serde_json::Value::Null));
        }
    }
    
    Ok(result)
}

#[tauri::command]
pub fn docking_cancel(
    job_id: String,
) -> Result<bool, String> {
    let job_dir = PathBuf::from("data/docking/cache/jobs").join(&job_id);
    let mut resolved_dir = job_dir.clone();
    if !resolved_dir.exists() {
        let alt_dir = PathBuf::from("../data/docking/cache/jobs").join(&job_id);
        if alt_dir.parent().map(|p| p.exists()).unwrap_or(false) {
            resolved_dir = alt_dir;
        }
    }
    
    std::fs::create_dir_all(&resolved_dir).map_err(|e| e.to_string())?;
    let flag_file = resolved_dir.join("cancel.flag");
    std::fs::write(&flag_file, "cancel").map_err(|e| e.to_string())?;
    Ok(true)
}

#[tauri::command]
pub fn analysis_interactions(
    state: State<'_, AppState>,
    receptor_pdb_path: String,
    pose_sdf_block: String,
    pose_index: i32,
) -> Result<serde_json::Value, String> {
    run_python_command(&state, "analysis_interactions", serde_json::json!({
        "receptor_pdb_path": receptor_pdb_path,
        "pose_sdf_block": pose_sdf_block,
        "pose_index": pose_index
    }))
}

#[tauri::command]
pub fn generate_2d_interaction_map(
    state: State<'_, AppState>,
    receptor_pdb_path: String,
    pose_sdf_block: String,
    pose_index: i32,
) -> Result<serde_json::Value, String> {
    run_python_command(&state, "generate_2d_interaction_map", serde_json::json!({
        "receptor_pdb_path": receptor_pdb_path,
        "pose_sdf_block": pose_sdf_block,
        "pose_index": pose_index
    }))
}

#[tauri::command]
pub fn analysis_distance(
    state: State<'_, AppState>,
    pose_sdf_block: String,
    receptor_pdb_path: String,
    atom1_selector: String,
    atom2_selector: String,
) -> Result<f64, String> {
    let val = run_python_command(&state, "analysis_distance", serde_json::json!({
        "pose_sdf_block": pose_sdf_block,
        "receptor_pdb_path": receptor_pdb_path,
        "atom1_selector": atom1_selector,
        "atom2_selector": atom2_selector
    }))?;
    val.as_f64().ok_or_else(|| "Distance is not a number".to_string())
}

#[tauri::command]
pub fn history_list(
    state: State<'_, AppState>,
    receptor_id: Option<String>,
    starred_only: Option<bool>,
    search_query: Option<String>,
) -> Result<serde_json::Value, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    
    let mut query = "SELECT job_id, receptor_id, receptor_display_name, ligand_smiles, ligand_display_name, 
                            box_center_x, box_center_y, box_center_z,
                            box_size_x, box_size_y, box_size_z,
                            top_score, num_poses, elapsed_seconds, completed_at, starred,
                            job_spec_json, result_path
                     FROM docking_jobs WHERE 1=1".to_string();
                     
    let mut params: Vec<Box<dyn rusqlite::ToSql>> = Vec::new();
    
    if let Some(ref r_id) = receptor_id {
        query.push_str(" AND receptor_id = ?");
        params.push(Box::new(r_id.clone()));
    }
    
    if let Some(true) = starred_only {
        query.push_str(" AND starred = 1");
    }
    
    if let Some(ref q) = search_query {
        if !q.is_empty() {
            query.push_str(" AND (ligand_smiles LIKE ? OR ligand_display_name LIKE ?)");
            let like_q = format!("%{}%", q);
            params.push(Box::new(like_q.clone()));
            params.push(Box::new(like_q));
        }
    }
    
    query.push_str(" ORDER BY completed_at DESC");
    
    let mut stmt = db.prepare(&query).map_err(|e| e.to_string())?;
    
    let params_refs: Vec<&dyn rusqlite::ToSql> = params.iter().map(|p| p.as_ref()).collect();
    
    let entries = stmt.query_map(&params_refs[..], |row| {
        Ok(serde_json::json!({
            "job_id": row.get::<_, String>(0)?,
            "receptor_id": row.get::<_, String>(1)?,
            "receptor_display_name": row.get::<_, Option<String>>(2)?,
            "ligand_smiles": row.get::<_, String>(3)?,
            "ligand_display_name": row.get::<_, Option<String>>(4)?,
            "box_center": (
                row.get::<_, f64>(5)?,
                row.get::<_, f64>(6)?,
                row.get::<_, f64>(7)?
            ),
            "box_size": (
                row.get::<_, f64>(8)?,
                row.get::<_, f64>(9)?,
                row.get::<_, f64>(10)?
            ),
            "top_score": row.get::<_, f64>(11)?,
            "num_poses": row.get::<_, i32>(12)?,
            "elapsed_seconds": row.get::<_, f64>(13)?,
            "completed_at": row.get::<_, String>(14)?,
            "starred": row.get::<_, i32>(15)? == 1,
            "job_spec_json": row.get::<_, String>(16)?,
            "result_path": row.get::<_, String>(17)?
        }))
    }).map_err(|e| e.to_string())?;
    
    let result_list: Vec<serde_json::Value> = entries
        .collect::<Result<Vec<_>, _>>()
        .map_err(|e| e.to_string())?;
        
    Ok(serde_json::Value::Array(result_list))
}

#[tauri::command]
pub fn history_load(
    state: State<'_, AppState>,
    job_id: String,
) -> Result<serde_json::Value, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    
    let (result_path, receptor_display_name, ligand_display_name): (String, Option<String>, Option<String>) = db.query_row(
        "SELECT result_path, receptor_display_name, ligand_display_name FROM docking_jobs WHERE job_id = ?1",
        rusqlite::params![job_id],
        |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
    ).map_err(|e| format!("Job history entry not found: {}", e))?;
    
    let file_path = resolve_cache_path(&result_path);
    if !file_path.exists() {
        return Err(format!("Job result file not found at: {:?}", file_path));
    }
    
    let content = std::fs::read_to_string(&file_path)
        .map_err(|e| format!("Failed to read job result file: {}", e))?;
        
    let mut result_json: serde_json::Value = serde_json::from_str(&content)
        .map_err(|e| format!("Failed to parse job result JSON: {}", e))?;
        
    if let serde_json::Value::Object(ref mut map) = result_json {
        if !map.contains_key("receptor_display_name") {
            map.insert("receptor_display_name".to_string(), serde_json::to_value(receptor_display_name).unwrap_or(serde_json::Value::Null));
        }
        if !map.contains_key("ligand_display_name") {
            map.insert("ligand_display_name".to_string(), serde_json::to_value(ligand_display_name).unwrap_or(serde_json::Value::Null));
        }
    }
        
    Ok(result_json)
}

#[tauri::command]
pub fn history_star(
    state: State<'_, AppState>,
    job_id: String,
    starred: bool,
) -> Result<bool, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    let starred_val = if starred { 1 } else { 0 };
    
    let rows = db.execute(
        "UPDATE docking_jobs SET starred = ?1 WHERE job_id = ?2",
        rusqlite::params![starred_val, job_id],
    ).map_err(|e| e.to_string())?;
    
    Ok(rows > 0)
}

#[tauri::command]
pub fn history_delete(
    state: State<'_, AppState>,
    job_id: String,
) -> Result<bool, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    
    let job_dir = PathBuf::from("data/docking/cache/jobs").join(&job_id);
    let dev_job_dir = PathBuf::from("../data/docking/cache/jobs").join(&job_id);
    
    if job_dir.exists() {
        let _ = std::fs::remove_dir_all(&job_dir);
    }
    if dev_job_dir.exists() {
        let _ = std::fs::remove_dir_all(&dev_job_dir);
    }
    
    let rows = db.execute(
        "DELETE FROM docking_jobs WHERE job_id = ?1",
        rusqlite::params![job_id],
    ).map_err(|e| e.to_string())?;
    
    Ok(rows > 0)
}

#[tauri::command]
pub fn read_text_file(path: String) -> Result<String, String> {
    let resolved_path = resolve_cache_path(&path);
    if !resolved_path.exists() {
        return Err(format!("File not found: {}", path));
    }
    std::fs::read_to_string(&resolved_path).map_err(|e| format!("Failed to read file: {}", e))
}

#[tauri::command]
pub fn cluster_poses(
    state: State<'_, AppState>,
    poses: Vec<serde_json::Value>,
    rmsd_cutoff: Option<f64>,
) -> Result<serde_json::Value, String> {
    run_python_command(&state, "cluster_poses", serde_json::json!({
        "poses": poses,
        "rmsd_cutoff": rmsd_cutoff.unwrap_or(2.0)
    }))
}

