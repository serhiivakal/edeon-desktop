/// Edeon Desktop — Models Commands
///
/// Tauri IPC handlers for custom QSAR machine learning models.

use crate::models::SavedModel;
use crate::python::PythonEngine;
use crate::AppState;
use chrono::Utc;
use rusqlite::params;
use serde_json::json;
use tauri::State;
use tauri::Manager;
use uuid::Uuid;
use std::sync::OnceLock;
use std::sync::Mutex;

#[derive(Clone)]
pub struct ActiveSHAPCache {
    pub shap_values: Vec<u8>,
    pub x_train_bg: Vec<u8>,
    pub estimator: Vec<u8>,
    pub algorithm: String,
    pub model_type: String,
    pub featurizer_selections: serde_json::Value,
    pub feature_names: Vec<String>,
    pub plot_data: serde_json::Value,
}

static LATEST_SHAP: OnceLock<Mutex<Option<ActiveSHAPCache>>> = OnceLock::new();

fn get_latest_shap() -> &'static Mutex<Option<ActiveSHAPCache>> {
    LATEST_SHAP.get_or_init(|| Mutex::new(None))
}


#[tauri::command]
pub fn list_saved_models(state: State<'_, AppState>) -> Result<Vec<SavedModel>, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;

    let mut stmt = db
        .prepare("SELECT id, name, type, algorithm, features, metrics, importances, provenance, curation_report, cv_results, y_scramble, COALESCE(search_results, '{}'), created_at, ad_reference, shap_values, COALESCE(diagnostics, '{}'), COALESCE(cliffs, '{}'), COALESCE(schema_version, 3), deploy_target, deployed_at, COALESCE(deployment_status, 'undeployed') FROM saved_models ORDER BY created_at DESC")
        .map_err(|e| e.to_string())?;

    let models = stmt
        .query_map([], |row| {
            Ok(SavedModel {
                id: row.get(0)?,
                name: row.get(1)?,
                r#type: row.get(2)?,
                algorithm: row.get(3)?,
                features: row.get(4)?,
                metrics: row.get(5)?,
                importances: row.get(6)?,
                provenance: row.get(7)?,
                curation_report: row.get(8)?,
                cv_results: row.get(9)?,
                y_scramble: row.get(10)?,
                search_results: row.get(11)?,
                created_at: row.get(12)?,
                ad_reference: row.get(13)?,
                shap_values: row.get(14)?,
                diagnostics: row.get(15)?,
                cliffs: row.get(16)?,
                schema_version: row.get(17)?,
                deploy_target: row.get(18)?,
                deployed_at: row.get(19)?,
                deployment_status: row.get(20)?,
            })
        })
        .map_err(|e| e.to_string())?
        .collect::<Result<Vec<_>, _>>()
        .map_err(|e| e.to_string())?;

    Ok(models)
}

#[tauri::command]
pub fn save_model(
    app: tauri::AppHandle,
    state: State<'_, AppState>,
    name: String,
    model_type: String,
    algorithm: String,
    features: Vec<String>,
    metrics: serde_json::Value,
    importances: serde_json::Value,
    provenance: serde_json::Value,        // NEW
    curation_report: serde_json::Value,   // NEW
    cv_results: serde_json::Value,        // NEW
    y_scramble: serde_json::Value,        // NEW
    search_results: serde_json::Value,    // NEW
    ad_reference: Option<Vec<u8>>,        // ADDED
    shap_values: Option<Vec<u8>>,         // ADDED
    diagnostics: Option<serde_json::Value>, // ADDED
    cliffs: Option<serde_json::Value>,      // ADDED
    estimator: Option<Vec<u8>>,           // ADDED
    x_train_bg: Option<Vec<u8>>,          // ADDED
) -> Result<SavedModel, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    let id = Uuid::new_v4().to_string();
    let now = Utc::now().to_rfc3339();

    let features_str = json!(features).to_string();
    let metrics_str = metrics.to_string();
    let importances_str = importances.to_string();
    let provenance_str = provenance.to_string();
    let curation_report_str = curation_report.to_string();
    let cv_results_str = cv_results.to_string();
    let y_scramble_str = y_scramble.to_string();
    let search_results_str = search_results.to_string();
    let diag_str = diagnostics.unwrap_or(json!({})).to_string();
    let cliffs_str = cliffs.unwrap_or(json!({})).to_string();

    db.execute(
        "INSERT INTO saved_models (id, name, type, algorithm, features, metrics, importances, provenance, curation_report, cv_results, y_scramble, search_results, created_at, ad_reference, shap_values, diagnostics, cliffs, schema_version)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15, ?16, ?17, 4)",
        params![id, name, model_type, algorithm, features_str, metrics_str, importances_str, provenance_str, curation_report_str, cv_results_str, y_scramble_str, search_results_str, now, ad_reference, shap_values, diag_str, cliffs_str],
    )
    .map_err(|e| e.to_string())?;

    // Save estimator binary and background training data to user's AppData directory
    let default_data_dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
    let models_dir = default_data_dir.join("models");
    std::fs::create_dir_all(&models_dir).map_err(|e| e.to_string())?;

    if let Some(est_bytes) = estimator {
        let est_path = models_dir.join(format!("{}.pkl", id));
        let _ = std::fs::write(&est_path, est_bytes);
    }

    if let Some(bg_bytes) = x_train_bg {
        let bg_path = models_dir.join(format!("{}_bg.pkl", id));
        let _ = std::fs::write(&bg_path, bg_bytes);
    }

    Ok(SavedModel {
        id,
        name,
        r#type: model_type,
        algorithm,
        features: features_str,
        metrics: metrics_str,
        importances: importances_str,
        provenance: provenance_str,
        curation_report: curation_report_str,
        cv_results: cv_results_str,
        y_scramble: y_scramble_str,
        search_results: search_results_str,
        created_at: now,
        ad_reference,
        shap_values,
        diagnostics: diag_str,
        cliffs: cliffs_str,
        schema_version: 4,
        deploy_target: None,
        deployed_at: None,
        deployment_status: "undeployed".to_string(),
    })
}

#[tauri::command]
pub fn delete_model(state: State<'_, AppState>, id: String) -> Result<(), String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;

    let rows = db
        .execute("DELETE FROM saved_models WHERE id = ?1", params![id])
        .map_err(|e| e.to_string())?;

    if rows == 0 {
        return Err("Model not found".to_string());
    }

    Ok(())
}

#[tauri::command]
pub fn train_custom_model(
    app: tauri::AppHandle,
    state: State<'_, AppState>,
    dataset_name: String,
    smiles: Vec<String>,
    activities: Vec<f64>,
    config: serde_json::Value,
) -> Result<serde_json::Value, String> {
    // Acquire Python engine
    let mut engine = {
        let mut py = state.python.lock().map_err(|e| e.to_string())?;
        if py.is_none() {
            *py = Some(PythonEngine::spawn()?);
        }
        py.take().ok_or("Python engine not available")?
    };

    // Make RPC request to train model
    let result = engine.send_request_with_app(
        "train_model",
        json!({
            "dataset_name": dataset_name,
            "smiles": smiles,
            "activities": activities,
            "config": config,
        }),
        Some(&app),
    );

    // Release Python engine back to the pool
    {
        let mut py = state.python.lock().map_err(|e| e.to_string())?;
        *py = Some(engine);
    }

    if let Ok(ref val) = result {
        let shap_bytes: Vec<u8> = val.get("shap_values")
            .and_then(|v| v.as_array())
            .map(|arr| arr.iter().filter_map(|x| x.as_u64().map(|b| b as u8)).collect())
            .unwrap_or_default();
            
        let x_train_bg: Vec<u8> = val.get("x_train_bg")
            .and_then(|v| v.as_array())
            .map(|arr| arr.iter().filter_map(|x| x.as_u64().map(|b| b as u8)).collect())
            .unwrap_or_default();
            
        let estimator: Vec<u8> = val.get("estimator")
            .and_then(|v| v.as_array())
            .map(|arr| arr.iter().filter_map(|x| x.as_u64().map(|b| b as u8)).collect())
            .unwrap_or_default();

        let feature_names: Vec<String> = val.get("feature_names")
            .and_then(|v| v.as_array())
            .map(|arr| arr.iter().filter_map(|x| x.as_str().map(|s| s.to_string())).collect())
            .unwrap_or_default();

        let algorithm = config.get("algorithm").and_then(|v| v.as_str()).unwrap_or("Random Forest").to_string();
        let model_type = config.get("model_type").and_then(|v| v.as_str()).unwrap_or("regression").to_string();
        let featurizer_selections = config.get("featurizer_selections").cloned().unwrap_or(serde_json::Value::Null);
        let plot_data = val.get("plot_data").cloned().unwrap_or(serde_json::Value::Null);

        let cache = ActiveSHAPCache {
            shap_values: shap_bytes,
            x_train_bg,
            estimator,
            algorithm,
            model_type,
            featurizer_selections,
            feature_names,
            plot_data,
        };

        if let Ok(mut latest) = get_latest_shap().lock() {
            *latest = Some(cache);
        }
    }

    result
}

#[tauri::command]
pub fn run_arena(
    app: tauri::AppHandle,
    state: State<'_, AppState>,
    smiles: Vec<String>,
    activities: Vec<f64>,
    config: serde_json::Value,
) -> Result<serde_json::Value, String> {
    // Acquire Python engine
    let mut engine = {
        let mut py = state.python.lock().map_err(|e| e.to_string())?;
        if py.is_none() {
            *py = Some(PythonEngine::spawn()?);
        }
        py.take().ok_or("Python engine not available")?
    };

    // Make RPC request to run arena
    let result = engine.send_request_with_app(
        "run_arena",
        json!({
            "smiles": smiles,
            "activities": activities,
            "config": config,
        }),
        Some(&app),
    );

    // Release Python engine back to the pool
    {
        let mut py = state.python.lock().map_err(|e| e.to_string())?;
        *py = Some(engine);
    }

    result
}

#[tauri::command]
pub fn curate_dataset(
    state: State<'_, AppState>,
    smiles: Vec<String>,
    activities: Vec<f64>,
    model_type: String,
) -> Result<serde_json::Value, String> {
    // Acquire Python engine
    let mut engine = {
        let mut py = state.python.lock().map_err(|e| e.to_string())?;
        if py.is_none() {
            *py = Some(PythonEngine::spawn()?);
        }
        py.take().ok_or("Python engine not available")?
    };

    // Make RPC request to curate dataset
    let result = engine.send_request(
        "curate_dataset",
        json!({
            "smiles": smiles,
            "activities": activities,
            "model_type": model_type,
        }),
    );

    // Release Python engine back to the pool
    {
        let mut py = state.python.lock().map_err(|e| e.to_string())?;
        *py = Some(engine);
    }

    result
}

#[tauri::command]
pub fn estimate_featurization(
    state: State<'_, AppState>,
    selections: Vec<serde_json::Value>,
    n_compounds: usize,
) -> Result<serde_json::Value, String> {
    // Acquire Python engine
    let mut engine = {
        let mut py = state.python.lock().map_err(|e| e.to_string())?;
        if py.is_none() {
            *py = Some(PythonEngine::spawn()?);
        }
        py.take().ok_or("Python engine not available")?
    };

    // Make RPC request to estimate featurization
    let result = engine.send_request(
        "estimate_featurization",
        json!({
            "selections": selections,
            "n_compounds": n_compounds,
        }),
    );

    // Release Python engine back to the pool
    {
        let mut py = state.python.lock().map_err(|e| e.to_string())?;
        *py = Some(engine);
    }

    result
}

#[tauri::command]
pub fn test_custom_expression(
    state: State<'_, AppState>,
    smiles: Vec<String>,
    expression: String,
) -> Result<serde_json::Value, String> {
    // Acquire Python engine
    let mut engine = {
        let mut py = state.python.lock().map_err(|e| e.to_string())?;
        if py.is_none() {
            *py = Some(PythonEngine::spawn()?);
        }
        py.take().ok_or("Python engine not available")?
    };

    // Make RPC request to test custom expression
    let result = engine.send_request(
        "test_custom_expression",
        json!({
            "smiles": smiles,
            "expression": expression,
        }),
    );

    // Release Python engine back to the pool
    {
        let mut py = state.python.lock().map_err(|e| e.to_string())?;
        *py = Some(engine);
    }

    result
}

#[tauri::command]
pub fn save_arena_run(
    state: State<'_, AppState>,
    name: String,
    shared: serde_json::Value,
    models: serde_json::Value,
    ranking: serde_json::Value,
    provenance: serde_json::Value,
    curation_report: serde_json::Value,
) -> Result<crate::models::ArenaRun, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    let id = Uuid::new_v4().to_string();
    let now = Utc::now().to_rfc3339();

    let shared_str = shared.to_string();
    let models_str = models.to_string();
    let ranking_str = ranking.to_string();
    let provenance_str = provenance.to_string();
    let curation_report_str = curation_report.to_string();

    db.execute(
        "INSERT INTO arena_runs (id, name, created_at, shared, models, ranking, provenance, curation_report)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
        params![id, name, now, shared_str, models_str, ranking_str, provenance_str, curation_report_str],
    )
    .map_err(|e| e.to_string())?;

    Ok(crate::models::ArenaRun {
        id,
        name,
        created_at: now,
        shared: shared_str,
        models: models_str,
        ranking: ranking_str,
        provenance: provenance_str,
        curation_report: curation_report_str,
    })
}

#[tauri::command]
pub fn list_arena_runs(state: State<'_, AppState>) -> Result<Vec<crate::models::ArenaRun>, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;

    let mut stmt = db
        .prepare("SELECT id, name, created_at, shared, models, ranking, provenance, curation_report FROM arena_runs ORDER BY created_at DESC")
        .map_err(|e| e.to_string())?;

    let runs = stmt
        .query_map([], |row| {
            Ok(crate::models::ArenaRun {
                id: row.get(0)?,
                name: row.get(1)?,
                created_at: row.get(2)?,
                shared: row.get(3)?,
                models: row.get(4)?,
                ranking: row.get(5)?,
                provenance: row.get(6)?,
                curation_report: row.get(7)?,
            })
        })
        .map_err(|e| e.to_string())?
        .collect::<Result<Vec<_>, _>>()
        .map_err(|e| e.to_string())?;

    Ok(runs)
}

#[tauri::command]
pub fn load_arena_run(state: State<'_, AppState>, id: String) -> Result<crate::models::ArenaRun, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;

    let run = db.query_row(
        "SELECT id, name, created_at, shared, models, ranking, provenance, curation_report FROM arena_runs WHERE id = ?1",
        params![id],
        |row| {
            Ok(crate::models::ArenaRun {
                id: row.get(0)?,
                name: row.get(1)?,
                created_at: row.get(2)?,
                shared: row.get(3)?,
                models: row.get(4)?,
                ranking: row.get(5)?,
                provenance: row.get(6)?,
                curation_report: row.get(7)?,
            })
        },
    )
    .map_err(|e| e.to_string())?;

    Ok(run)
}

#[tauri::command]
pub fn delete_arena_run(state: State<'_, AppState>, id: String) -> Result<(), String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;

    let rows = db
        .execute("DELETE FROM arena_runs WHERE id = ?1", params![id])
        .map_err(|e| e.to_string())?;

    if rows == 0 {
        return Err("Arena run not found".to_string());
    }

    Ok(())
}

#[tauri::command]
pub fn promote_arena_model(
    app: tauri::AppHandle,
    state: State<'_, AppState>,
    run_id: String,
    algorithm: String,
) -> Result<SavedModel, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;

    // Load the arena run
    let run = db.query_row(
        "SELECT name, shared, models, provenance, curation_report FROM arena_runs WHERE id = ?1",
        params![run_id],
        |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, String>(2)?,
                row.get::<_, String>(3)?,
                row.get::<_, String>(4)?,
            ))
        },
    )
    .map_err(|e| e.to_string())?;

    let (run_name, shared_json, models_json, provenance_json, curation_report_json) = run;

    // Parse structures
    let shared: serde_json::Value = serde_json::from_str(&shared_json).map_err(|e| e.to_string())?;
    let models: serde_json::Value = serde_json::from_str(&models_json).map_err(|e| e.to_string())?;
    
    // Find the specific model matching the requested algorithm
    let models_arr = models.as_array().ok_or("Invalid models array in arena run")?;
    let model_entry = models_arr.iter()
        .find(|m| m.get("algorithm").and_then(|v| v.as_str()) == Some(&algorithm))
        .ok_or(format!("Algorithm {} not found in arena run", algorithm))?;

    if let Some(err) = model_entry.get("error") {
        if !err.is_null() {
            return Err(format!("Cannot promote failed model: {}", err));
        }
    }

    let model_type = shared.get("model_type").and_then(|v| v.as_str()).unwrap_or("regression").to_string();
    let features_val = shared.get("feature_names").cloned().unwrap_or(json!(Vec::<String>::new()));
    let metrics_val = model_entry.get("metrics").cloned().unwrap_or(json!({}));
    let importances_val = model_entry.get("importances").cloned().unwrap_or(json!({}));
    let cv_results_val = model_entry.get("cv_results").cloned().unwrap_or(json!([]));
    let y_scramble_val = model_entry.get("y_scramble").cloned().unwrap_or(json!({}));
    let search_results_val = model_entry.get("search_results").cloned().unwrap_or(json!({}));
    let ad_ref_val = model_entry.get("ad_reference");
    let ad_ref_bytes: Option<Vec<u8>> = ad_ref_val.and_then(|v| serde_json::from_value(v.clone()).ok());
    let shap_val = model_entry.get("shap_values");
    let shap_bytes: Option<Vec<u8>> = shap_val.and_then(|v| serde_json::from_value(v.clone()).ok());
    let est_val = model_entry.get("estimator");
    let est_bytes: Option<Vec<u8>> = est_val.and_then(|v| serde_json::from_value(v.clone()).ok());
    let bg_val = model_entry.get("x_train_bg");
    let bg_bytes: Option<Vec<u8>> = bg_val.and_then(|v| serde_json::from_value(v.clone()).ok());

    let diagnostics_val = model_entry.get("diagnostics").cloned().unwrap_or(json!({}));
    let diag_str = diagnostics_val.to_string();

    // Rehydrate model save
    let id = Uuid::new_v4().to_string();
    let now = Utc::now().to_rfc3339();
    let name = format!("{} (Promoted {})", run_name, algorithm.to_uppercase());

    let features_str = features_val.to_string();
    let metrics_str = metrics_val.to_string();
    let importances_str = importances_val.to_string();
    let provenance_str = provenance_json;
    let curation_report_str = curation_report_json;
    let cv_results_str = cv_results_val.to_string();
    let y_scramble_str = y_scramble_val.to_string();
    let search_results_str = search_results_val.to_string();

    db.execute(
        "INSERT INTO saved_models (id, name, type, algorithm, features, metrics, importances, provenance, curation_report, cv_results, y_scramble, search_results, created_at, ad_reference, shap_values, diagnostics, cliffs, schema_version)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15, ?16, ?17, 4)",
        params![id, name, model_type, algorithm, features_str, metrics_str, importances_str, provenance_str, curation_report_str, cv_results_str, y_scramble_str, search_results_str, now, ad_ref_bytes, shap_bytes, diag_str, "{}"],
    )
    .map_err(|e| e.to_string())?;

    // Save estimator binary and background training data to user's AppData directory
    let default_data_dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
    let models_dir = default_data_dir.join("models");
    std::fs::create_dir_all(&models_dir).map_err(|e| e.to_string())?;

    if let Some(e_bytes) = est_bytes {
        let est_path = models_dir.join(format!("{}.pkl", id));
        let _ = std::fs::write(&est_path, e_bytes);
    }

    if let Some(b_bytes) = bg_bytes {
        let bg_path = models_dir.join(format!("{}_bg.pkl", id));
        let _ = std::fs::write(&bg_path, b_bytes);
    }

    Ok(SavedModel {
        id,
        name,
        r#type: model_type,
        algorithm,
        features: features_str,
        metrics: metrics_str,
        importances: importances_str,
        provenance: provenance_str,
        curation_report: curation_report_str,
        cv_results: cv_results_str,
        y_scramble: y_scramble_str,
        search_results: search_results_str,
        created_at: now,
        ad_reference: ad_ref_bytes,
        shap_values: shap_bytes,
        diagnostics: diag_str,
        cliffs: "{}".to_string(),
        schema_version: 4,
        deploy_target: None,
        deployed_at: None,
        deployment_status: "undeployed".to_string(),
    })
}

#[tauri::command]
pub fn get_shap_summary(
    state: State<'_, AppState>,
    model_id: String,
) -> Result<serde_json::Value, String> {
    let shap = if model_id == "active" {
        let latest = get_latest_shap().lock().map_err(|e| e.to_string())?;
        latest.as_ref().map(|c| c.shap_values.clone()).ok_or("No active SHAP values found. Please train a model first.")?
    } else {
        let db = state.db.lock().map_err(|e| e.to_string())?;
        let shap_bytes: Option<Vec<u8>> = db.query_row(
            "SELECT shap_values FROM saved_models WHERE id = ?1",
            params![model_id],
            |row| row.get(0),
        )
        .map_err(|e| e.to_string())?;
        shap_bytes.ok_or("SHAP values not found for this model")?
    };
    
    // Acquire Python engine
    let mut engine = {
        let mut py = state.python.lock().map_err(|e| e.to_string())?;
        if py.is_none() {
            *py = Some(PythonEngine::spawn()?);
        }
        py.take().ok_or("Python engine not available")?
    };
    
    let result = engine.send_request("get_shap_summary", json!({ "shap_values": shap }));
    
    // Release Python engine
    {
        let mut py = state.python.lock().map_err(|e| e.to_string())?;
        *py = Some(engine);
    }
    
    result
}

#[tauri::command]
pub fn get_shap_for_compound(
    state: State<'_, AppState>,
    model_id: String,
    compound_idx: usize,
) -> Result<serde_json::Value, String> {
    let shap = if model_id == "active" {
        let latest = get_latest_shap().lock().map_err(|e| e.to_string())?;
        latest.as_ref().map(|c| c.shap_values.clone()).ok_or("No active SHAP values found.")?
    } else {
        let db = state.db.lock().map_err(|e| e.to_string())?;
        let shap_bytes: Option<Vec<u8>> = db.query_row(
            "SELECT shap_values FROM saved_models WHERE id = ?1",
            params![model_id],
            |row| row.get(0),
        )
        .map_err(|e| e.to_string())?;
        shap_bytes.ok_or("SHAP values not found for this model")?
    };
    
    // Acquire Python engine
    let mut engine = {
        let mut py = state.python.lock().map_err(|e| e.to_string())?;
        if py.is_none() {
            *py = Some(PythonEngine::spawn()?);
        }
        py.take().ok_or("Python engine not available")?
    };
    
    let result = engine.send_request(
        "get_shap_for_compound",
        json!({ "shap_values": shap, "compound_idx": compound_idx }),
    );
    
    // Release Python engine
    {
        let mut py = state.python.lock().map_err(|e| e.to_string())?;
        *py = Some(engine);
    }
    
    result
}

#[tauri::command]
pub fn explain_new_compound(
    app: tauri::AppHandle,
    state: State<'_, AppState>,
    model_id: String,
    smiles: String,
) -> Result<serde_json::Value, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    
    // Load model metadata from SQL
    let (algorithm, model_type, features_str) = db.query_row(
        "SELECT algorithm, type, features FROM saved_models WHERE id = ?1",
        params![model_id],
        |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, String>(2)?,
            ))
        },
    )
    .map_err(|e| e.to_string())?;
    
    let feature_names: Vec<String> = serde_json::from_str(&features_str).map_err(|e| e.to_string())?;
    
    // Load estimator and x_train_bg from disk
    let default_data_dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
    let models_dir = default_data_dir.join("models");
    
    let est_path = models_dir.join(format!("{}.pkl", model_id));
    let bg_path = models_dir.join(format!("{}_bg.pkl", model_id));
    
    if !est_path.exists() || !bg_path.exists() {
        return Err("Trained model files not found on disk. Explanation unavailable.".to_string());
    }
    
    let est_bytes = std::fs::read(&est_path).map_err(|e| e.to_string())?;
    let bg_bytes = std::fs::read(&bg_path).map_err(|e| e.to_string())?;
    
    // Load the diagnostics string from the DB
    let diag_str: String = db.query_row(
        "SELECT diagnostics FROM saved_models WHERE id = ?1",
        params![model_id],
        |row| row.get(0),
    )
    .map_err(|e| e.to_string())?;
    
    let diag: serde_json::Value = serde_json::from_str(&diag_str).map_err(|e| e.to_string())?;
    let featurizer_selections = diag.get("featurizer_selections").cloned().unwrap_or(json!([]));
    
    // Acquire Python engine
    let mut engine = {
        let mut py = state.python.lock().map_err(|e| e.to_string())?;
        if py.is_none() {
            *py = Some(PythonEngine::spawn()?);
        }
        py.take().ok_or("Python engine not available")?
    };
    
    let result = engine.send_request(
        "explain_new_compound",
        json!({
            "estimator": est_bytes,
            "x_train_bg": bg_bytes,
            "algorithm": algorithm,
            "model_type": model_type,
            "smiles": smiles,
            "featurizer_selections": featurizer_selections,
            "feature_names": feature_names
        }),
    );
    
    // Release Python engine
    {
        let mut py = state.python.lock().map_err(|e| e.to_string())?;
        *py = Some(engine);
    }
    
    result
}

#[tauri::command]
pub fn render_atom_map(
    app: tauri::AppHandle,
    state: State<'_, AppState>,
    model_id: String,
    smiles: String,
    morgan_block_idx: usize,
) -> Result<String, String> {
    let featurizer_selections;
    let feature_names;
    let algorithm;
    let model_type;
    let shap_values;
    let mut estimator = Vec::<u8>::new();
    let mut x_train_bg = Vec::<u8>::new();
    let mut compound_idx: Option<usize> = None;

    if model_id == "active" {
        let latest_opt = get_latest_shap().lock().map_err(|e| e.to_string())?.clone();
        let cache = latest_opt.ok_or("No active SHAP values or model cached.")?;
        
        featurizer_selections = cache.featurizer_selections;
        feature_names = cache.feature_names;
        algorithm = cache.algorithm;
        model_type = cache.model_type;
        shap_values = cache.shap_values;
        estimator = cache.estimator;
        x_train_bg = cache.x_train_bg;

        // Try to find the smiles string in plot_data.points to get compound_idx
        if let Some(points) = cache.plot_data.get("points").and_then(|p| p.as_array()) {
            for (idx, p) in points.iter().enumerate() {
                if let Some(p_smi) = p.get("smiles").and_then(|s| s.as_str()) {
                    if p_smi == smiles {
                        compound_idx = Some(idx);
                        break;
                    }
                }
            }
        }
    } else {
        let db = state.db.lock().map_err(|e| e.to_string())?;
        
        let (algo, m_type, features_str, diag_str, shap_bytes_opt) = db.query_row(
            "SELECT algorithm, type, features, diagnostics, shap_values FROM saved_models WHERE id = ?1",
            params![model_id],
            |row| {
                Ok((
                    row.get::<_, String>(0)?,
                    row.get::<_, String>(1)?,
                    row.get::<_, String>(2)?,
                    row.get::<_, String>(3)?,
                    row.get::<_, Option<Vec<u8>>>(4)?,
                ))
            },
        )
        .map_err(|e| e.to_string())?;

        algorithm = algo;
        model_type = m_type;
        feature_names = serde_json::from_str(&features_str).map_err(|e| e.to_string())?;
        shap_values = shap_bytes_opt.ok_or("SHAP values not found for this model.")?;

        let diag: serde_json::Value = serde_json::from_str(&diag_str).map_err(|e| e.to_string())?;
        featurizer_selections = diag.get("featurizer_selections").cloned().unwrap_or(serde_json::Value::Null);

        // Load files from disk if needed for Sandbox prediction
        let default_data_dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
        let models_dir = default_data_dir.join("models");
        
        let est_path = models_dir.join(format!("{}.pkl", model_id));
        let bg_path = models_dir.join(format!("{}_bg.pkl", model_id));
        
        if est_path.exists() && bg_path.exists() {
            estimator = std::fs::read(&est_path).unwrap_or_default();
            x_train_bg = std::fs::read(&bg_path).unwrap_or_default();
        }

        // Try to find the smiles string in diag.plot_data.points to get compound_idx
        if let Some(points) = diag.get("plot_data").and_then(|pd| pd.get("points")).and_then(|p| p.as_array()) {
            for (idx, p) in points.iter().enumerate() {
                if let Some(p_smi) = p.get("smiles").and_then(|s| s.as_str()) {
                    if p_smi == smiles {
                        compound_idx = Some(idx);
                        break;
                    }
                }
            }
        }
    }

    // Now invoke python rpc `"render_atom_map"`
    let mut engine = {
        let mut py = state.python.lock().map_err(|e| e.to_string())?;
        if py.is_none() {
            *py = Some(PythonEngine::spawn()?);
        }
        py.take().ok_or("Python engine not available")?
    };

    let result = engine.send_request(
        "render_atom_map",
        json!({
            "shap_values": shap_values,
            "smiles": smiles,
            "morgan_block_idx": morgan_block_idx,
            "featurizer_selections": featurizer_selections,
            "feature_names": feature_names,
            "compound_idx": compound_idx,
            "estimator": estimator,
            "x_train_bg": x_train_bg,
            "algorithm": algorithm,
            "model_type": model_type,
        }),
    );

    // Release Python engine
    {
        let mut py = state.python.lock().map_err(|e| e.to_string())?;
        *py = Some(engine);
    }

    let val = result?;
    let data_uri = val.as_str().ok_or_else(|| "Failed to generate contribution map image.".to_string())?;

    Ok(data_uri.to_string())
}

#[tauri::command]
pub fn save_atom_map_png(
    app: tauri::AppHandle,
    base64_data: String,
) -> Result<(), String> {
    use tauri_plugin_dialog::DialogExt;

    // Strip prefix like "data:image/png;base64," if present
    let raw_b64 = if base64_data.starts_with("data:image/png;base64,") {
        &base64_data["data:image/png;base64,".len()..]
    } else {
        &base64_data
    };

    use base64::prelude::*;
    let decoded = BASE64_STANDARD.decode(raw_b64).map_err(|e| e.to_string())?;

    // Open file dialog to choose target path
    let file_path = app.dialog()
        .file()
        .add_filter("PNG Image", &["png"])
        .set_file_name("atom_contribution_map.png")
        .blocking_save_file();

    if let Some(path) = file_path {
        let path_buf = path.into_path().map_err(|e| e.to_string())?;
        std::fs::write(&path_buf, decoded).map_err(|e| e.to_string())?;
    }

    Ok(())
}

#[tauri::command]
pub fn recompute_cliffs(
    _app: tauri::AppHandle,
    state: State<'_, AppState>,
    model_id: String,
    similarity_threshold: f32,
    activity_gap: f32,
) -> Result<serde_json::Value, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;

    // Load model type and curation report from SQL
    let (model_type, curation_report_str) = db.query_row(
        "SELECT type, curation_report FROM saved_models WHERE id = ?1",
        params![model_id],
        |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, String>(1)?,
            ))
        },
    )
    .map_err(|e| e.to_string())?;

    let curation_report: serde_json::Value = serde_json::from_str(&curation_report_str).map_err(|e| e.to_string())?;

    let smiles = curation_report.get("smiles")
        .ok_or_else(|| "Smiles list not found in saved model curation report. Recomputation unavailable.".to_string())?
        .clone();
    let activities = curation_report.get("activities")
        .ok_or_else(|| "Activities not found in saved model curation report. Recomputation unavailable.".to_string())?
        .clone();

    // Acquire Python engine
    let mut engine = {
        let mut py = state.python.lock().map_err(|e| e.to_string())?;
        if py.is_none() {
            *py = Some(PythonEngine::spawn()?);
        }
        py.take().ok_or("Python engine not available")?
    };

    let result = engine.send_request(
        "recompute_cliffs",
        json!({
            "smiles": smiles,
            "activities": activities,
            "model_type": model_type,
            "similarity_threshold": similarity_threshold,
            "activity_gap": activity_gap,
        }),
    );

    // Release Python engine
    {
        let mut py = state.python.lock().map_err(|e| e.to_string())?;
        *py = Some(engine);
    }

    let cliffs_val = result?;
    let cliffs_str = cliffs_val.to_string();

    db.execute(
        "UPDATE saved_models SET cliffs = ?1 WHERE id = ?2",
        params![cliffs_str, model_id],
    )
    .map_err(|e| e.to_string())?;

    Ok(cliffs_val)
}

#[tauri::command]
pub async fn model_predict(
    app: tauri::AppHandle,
    endpoint: String,
    smiles: Vec<String>,
    preferred_tier: Option<u8>,
) -> Result<Vec<crate::models::types::Prediction>, String> {
    let proxy = crate::models::proxy::BackendProxy::new(app);
    proxy.predict(&endpoint, smiles, preferred_tier)
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn model_list_for_endpoint(
    app: tauri::AppHandle,
    endpoint: String,
) -> Result<Vec<crate::models::types::ModelCard>, String> {
    let proxy = crate::models::proxy::BackendProxy::new(app);
    proxy.list_backends(&endpoint)
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn model_get_card(
    app: tauri::AppHandle,
    model_id: String,
) -> Result<crate::models::types::ModelCard, String> {
    let proxy = crate::models::proxy::BackendProxy::new(app);
    proxy.get_card(&model_id)
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn model_set_preference(
    app: tauri::AppHandle,
    endpoint: String,
    tier: u8,
) -> Result<(), String> {
    let proxy = crate::models::proxy::BackendProxy::new(app);
    proxy.set_preference(&endpoint, tier)
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn model_get_preference(
    _app: tauri::AppHandle,
    state: State<'_, AppState>,
    endpoint: String,
) -> Result<Option<u8>, String> {
    let conn = state.db.lock().map_err(|e| e.to_string())?;
    crate::models::preferences::get_preference(&conn, &endpoint)
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub fn model_list_endpoints() -> Vec<String> {
    vec![
        "bee_acute_oral_ld50".to_string(),
        "bee_acute_contact_ld50".to_string(),
        "fish_acute_lc50".to_string(),
        "daphnia_acute_ec50".to_string(),
        "algae_growth_ec50".to_string(),
        "earthworm_acute_lc50".to_string(),
        "bird_acute_oral_ld50".to_string(),
        "rat_acute_oral_ld50".to_string(),
        "skin_sensitization".to_string(),
        "eye_irritation".to_string(),
        "soil_koc".to_string(),
        "soil_dt50".to_string(),
        "gus_index".to_string(),
        "bcf".to_string(),
        "photostability_class".to_string(),
        "pesticide_likeness_tice".to_string(),
        "logp".to_string(),
        "pka".to_string(),
        "solubility".to_string(),
        "henrys_law".to_string(),
    ]
}

#[tauri::command]
pub async fn deploy_studio_model(
    app: tauri::AppHandle,
    state: State<'_, AppState>,
    saved_model_id: String,
    endpoint: String,
) -> Result<crate::models::types::ModelCard, String> {
    let proxy = crate::models::proxy::BackendProxy::new(app);
    let card = proxy.deploy_studio_model(&saved_model_id, &endpoint)
        .await
        .map_err(|e| e.to_string())?;

    // Record model_deployed in decision journal
    let summary = format!("Model '{}' deployed for endpoint '{}' (tier {})", card.name, endpoint, card.tier);
    let prov = serde_json::to_string(&card).unwrap_or_else(|_| "{}".to_string());

    let entry = crate::journal::JournalEntry::new_system(
        "global",
        "model_deployed",
        "model",
        &saved_model_id,
        &summary,
        &prov,
    );

    if let Ok(mut db) = state.db.lock() {
        let _ = crate::journal::append_standalone(&mut db, &entry);
    }

    Ok(card)
}

#[tauri::command]
pub async fn undeploy_studio_model(
    app: tauri::AppHandle,
    saved_model_id: String,
) -> Result<(), String> {
    let proxy = crate::models::proxy::BackendProxy::new(app);
    proxy.undeploy_studio_model(&saved_model_id)
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn get_calibration_diagnostics(
    app: tauri::AppHandle,
    model_id: String,
) -> Result<serde_json::Value, String> {
    let proxy = crate::models::proxy::BackendProxy::new(app);
    proxy.get_calibration_diagnostics(&model_id)
        .await
        .map_err(|e| e.to_string())
}


