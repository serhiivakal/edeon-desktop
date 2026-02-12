/// Edeon Desktop — Settings & Preferences Commands
///
/// Handles database-persisted preferences, custom database directory path,
/// and Python computational engine lifecycle management.

use tauri::{AppHandle, Manager, State};
use crate::AppState;
use crate::python::PythonEngine;

/// Get a persistent preference value from the SQLite settings table.
#[tauri::command]
pub fn get_setting(state: State<'_, AppState>, key: String) -> Result<Option<String>, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;

    let result = db.query_row(
        "SELECT value FROM settings WHERE key = ?1",
        rusqlite::params![key],
        |row| row.get::<_, String>(0),
    );

    let val_opt = match result {
        Ok(val) => Some(val),
        Err(rusqlite::Error::QueryReturnedNoRows) => None,
        Err(e) => return Err(e.to_string()),
    };

    if let Some(val) = val_opt {
        if key == "anthropic_api_key" {
            let mut py = state.get_python_engine()?;
            let engine = py.as_mut().ok_or("Python engine not available")?;
            let res = engine.send_request("decrypt_api_key", serde_json::json!({ "value": val }))?;
            let decrypted = res.as_str().ok_or("Failed to decrypt API key")?.to_string();
            Ok(Some(decrypted))
        } else {
            Ok(Some(val))
        }
    } else {
        Ok(None)
    }
}

/// Set a persistent preference value in the SQLite settings table.
#[tauri::command]
pub fn set_setting(state: State<'_, AppState>, key: String, value: String) -> Result<(), String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;

    let value_to_save = if key == "anthropic_api_key" {
        let mut py = state.get_python_engine()?;
        let engine = py.as_mut().ok_or("Python engine not available")?;
        let res = engine.send_request("encrypt_api_key", serde_json::json!({ "value": value }))?;
        res.as_str().ok_or("Failed to encrypt API key")?.to_string()
    } else {
        value
    };

    db.execute(
        "INSERT INTO settings (key, value) VALUES (?1, ?2)
         ON CONFLICT(key) DO UPDATE SET value = ?2",
        rusqlite::params![key, value_to_save],
    )
    .map_err(|e| e.to_string())?;

    Ok(())
}

/// Retrieve the active database directory from local config.json.
/// Defaults to Edeon's standard app data directory.
#[tauri::command]
pub fn get_database_dir(app: AppHandle) -> Result<String, String> {
    let default_data_dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
    let config_path = default_data_dir.join("config.json");

    if config_path.exists() {
        if let Ok(config_str) = std::fs::read_to_string(&config_path) {
            if let Ok(config) = serde_json::from_str::<serde_json::Value>(&config_str) {
                if let Some(custom_dir) = config.get("database_dir").and_then(|v| v.as_str()) {
                    return Ok(custom_dir.to_string());
                }
            }
        }
    }

    Ok(default_data_dir.to_string_lossy().to_string())
}

/// Save a new custom database directory path to config.json.
#[tauri::command]
pub fn set_database_dir(app: AppHandle, dir: String) -> Result<(), String> {
    let default_data_dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
    let config_path = default_data_dir.join("config.json");

    // Ensure target custom directory exists
    let custom_path = std::path::PathBuf::from(&dir);
    if !custom_path.exists() {
        std::fs::create_dir_all(&custom_path).map_err(|e| e.to_string())?;
    }

    let mut config = serde_json::Map::new();
    if config_path.exists() {
        if let Ok(config_str) = std::fs::read_to_string(&config_path) {
            if let Ok(serde_json::Value::Object(map)) = serde_json::from_str::<serde_json::Value>(&config_str) {
                config = map;
            }
        }
    }

    config.insert("database_dir".to_string(), serde_json::Value::String(dir));

    let updated_config_str = serde_json::to_string_pretty(&serde_json::Value::Object(config))
        .map_err(|e| e.to_string())?;

    std::fs::write(&config_path, updated_config_str).map_err(|e| e.to_string())?;

    Ok(())
}

/// Query diagnostic parameters from the Python computational engine.
#[tauri::command]
pub fn get_python_engine_info(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    let mut py = state.python.lock().map_err(|e| e.to_string())?;

    // Ensure the engine is spawned
    if py.is_none() {
        *py = Some(PythonEngine::spawn()?);
    }

    let engine = py.as_mut().ok_or("Python computational engine not initialized")?;
    engine.send_request("info", serde_json::json!({}))
}

/// Kill the current Python engine process and start a clean new one.
#[tauri::command]
pub fn restart_python_engine(state: State<'_, AppState>) -> Result<bool, String> {
    let mut py = state.python.lock().map_err(|e| e.to_string())?;

    // Shutdown existing process if present
    if let Some(mut engine) = py.take() {
        engine.shutdown();
    }

    // Spawn a fresh process
    match PythonEngine::spawn() {
        Ok(engine) => {
            *py = Some(engine);
            Ok(true)
        }
        Err(e) => Err(format!("Failed to restart Python computational engine: {}", e)),
    }
}
