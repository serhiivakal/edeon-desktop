/// Edeon Desktop — Tauri application library
///
/// Phase 3: Python engine, cheminformatics workflows.

mod db;
mod models;
mod commands;
mod python;

use std::sync::Mutex;
use rusqlite::Connection;
use tauri::Manager;

use python::PythonEngine;

pub struct AppState {
    pub db: Mutex<Connection>,
    pub python: Mutex<Option<PythonEngine>>,
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            let data_dir = app.path().app_data_dir().map_err(|e| {
                Box::new(std::io::Error::new(std::io::ErrorKind::Other, e.to_string()))
                    as Box<dyn std::error::Error>
            })?;
            std::fs::create_dir_all(&data_dir)?;
            let db_path = data_dir.join("edeon.db");
            let conn = db::init_db(&db_path).map_err(|e| {
                Box::new(std::io::Error::new(std::io::ErrorKind::Other, e.to_string()))
                    as Box<dyn std::error::Error>
            })?;
            app.manage(AppState {
                db: Mutex::new(conn),
                python: Mutex::new(None), // Lazily spawned on first workflow
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            // Project commands
            commands::project::create_project,
            commands::project::list_projects,
            commands::project::rename_project,
            commands::project::delete_project,
            commands::project::get_active_project_id,
            commands::project::set_active_project,
            // Compound commands
            commands::compound::import_compounds_csv,
            commands::compound::list_compounds,
            commands::compound::get_compound,
            commands::compound::add_compound,
            commands::compound::delete_compounds,
            // Workflow commands
            commands::workflow::start_workflow,
            commands::workflow::get_workflow_status,
            commands::workflow::get_workflow_results,
            commands::workflow::list_workflows,
            commands::workflow::check_python_engine,
        ])
        .run(tauri::generate_context!())
        .expect("error while running Edeon Desktop");
}
