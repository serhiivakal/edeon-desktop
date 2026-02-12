/// Edeon Desktop — Tauri application library
///
/// Phase 3: Python engine, cheminformatics workflows.

mod db;
mod models;
mod commands;
mod python;
mod journal;

use std::sync::Mutex;
use rusqlite::Connection;
use tauri::Manager;

use std::collections::HashSet;

use python::PythonEngine;

use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize, Default)]
struct LocalConfig {
    database_dir: Option<String>,
}

pub struct AppState {
    pub db: Mutex<Connection>,
    pub python: Mutex<Option<PythonEngine>>,
    pub cancelled_workflows: Mutex<HashSet<String>>,
}

impl AppState {
    /// Lock the Python engine Mutex, automatically verifying process health and respawning if dead.
    pub fn get_python_engine(&self) -> Result<std::sync::MutexGuard<'_, Option<PythonEngine>>, String> {
        let mut py = self.python.lock().map_err(|e| e.to_string())?;
        
        let need_spawn = match &mut *py {
            Some(engine) => !engine.is_alive(),
            None => true,
        };

        if need_spawn {
            *py = Some(PythonEngine::spawn()?);
        }
        
        Ok(py)
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            let default_data_dir = app.path().app_data_dir().map_err(|e| {
                Box::new(std::io::Error::new(std::io::ErrorKind::Other, e.to_string()))
                    as Box<dyn std::error::Error>
            })?;
            std::fs::create_dir_all(&default_data_dir)?;

            let config_path = default_data_dir.join("config.json");
            let mut db_path = default_data_dir.join("edeon.db");

            if config_path.exists() {
                if let Ok(config_str) = std::fs::read_to_string(&config_path) {
                    if let Ok(config) = serde_json::from_str::<LocalConfig>(&config_str) {
                        if let Some(ref custom_dir) = config.database_dir {
                            let custom_path = std::path::PathBuf::from(custom_dir);
                            if custom_path.exists() && custom_path.is_dir() {
                                db_path = custom_path.join("edeon.db");
                            }
                        }
                    }
                }
            }

            let conn = db::init_db(&db_path).map_err(|e| {
                Box::new(std::io::Error::new(std::io::ErrorKind::Other, e.to_string()))
                    as Box<dyn std::error::Error>
            })?;

            app.manage(AppState {
                db: Mutex::new(conn),
                python: Mutex::new(None), // Lazily spawned on first workflow
                cancelled_workflows: Mutex::new(HashSet::new()),
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
            commands::compound::import_compounds_sdf,
            commands::compound::list_compounds,
            commands::compound::get_compound,
            commands::compound::add_compound,
            commands::compound::delete_compounds,
            commands::compound::replace_project_compounds,
            // Workflow commands
            commands::workflow::start_workflow,
            commands::workflow::get_workflow_status,
            commands::workflow::get_workflow_results,
            commands::workflow::list_workflows,
            commands::workflow::check_python_engine,
            commands::workflow::depict_compound,
            commands::workflow::generate_3d_conformer,
            commands::workflow::compute_mcs,
            commands::workflow::depict_mcs,
            commands::workflow::standardize,
            commands::workflow::cancel_workflow,
            commands::workflow::export_results_csv,
            commands::workflow::export_results_sdf,
            commands::workflow::export_library_csv,
            commands::workflow::invoke_python_rpc,
            commands::workflow::list_available_workflows,
            commands::workflow::get_workflow_details,
            commands::workflow::run_named_workflow,
            // Export commands
            commands::export::export_workflow_pdf,
            commands::export::export_environmental_dossier,
            commands::export::export_selectivity_chartbook,
            // Models commands
            commands::models::list_saved_models,
            commands::models::save_model,
            commands::models::delete_model,
            commands::models::train_custom_model,
            commands::models::run_arena,
            commands::models::curate_dataset,
            commands::models::estimate_featurization,
            commands::models::test_custom_expression,
            commands::models::save_arena_run,
            commands::models::list_arena_runs,
            commands::models::load_arena_run,
            commands::models::delete_arena_run,
            commands::models::promote_arena_model,
            commands::models::get_shap_summary,
            commands::models::get_shap_for_compound,
            commands::models::explain_new_compound,
            commands::models::render_atom_map,
            commands::models::save_atom_map_png,
            commands::models::recompute_cliffs,
            commands::models::model_predict,
            commands::models::model_list_for_endpoint,
            commands::models::model_get_card,
            commands::models::model_set_preference,
            commands::models::model_get_preference,
            commands::models::model_list_endpoints,
            commands::models::deploy_studio_model,
            commands::models::undeploy_studio_model,
            commands::models::get_calibration_diagnostics,
            // Knowledge commands
            commands::knowledge::search_knowledge,
            commands::knowledge::knowledge_qa_ask,
            commands::knowledge::knowledge_qa_list_conversations,
            commands::knowledge::knowledge_qa_load_conversation,
            commands::knowledge::knowledge_qa_star_conversation,
            commands::knowledge::knowledge_qa_delete_conversation,
            commands::knowledge::knowledge_qa_reindex,
            commands::knowledge::ollama_check_status,
            commands::knowledge::ollama_start_sidecar,
            // Settings commands
            commands::settings::get_setting,
            commands::settings::set_setting,
            commands::settings::get_database_dir,
            commands::settings::set_database_dir,
            commands::settings::get_python_engine_info,
            commands::settings::restart_python_engine,
            commands::workflow::bioisostere_suggest,
            commands::design::suggest_analogs,
            commands::design::crem_generate,
            commands::design::easydock_dock,
            commands::design::crem_dock_run,
            commands::design::generation_history_list,
            commands::design::generation_history_load,
            commands::design::generation_history_delete,
            commands::design::gen_reaction_list_templates,
            commands::design::gen_reaction_enumerate,
            commands::docking::receptor_load_from_source,
            commands::docking::receptor_get_het_list,
            commands::docking::receptor_reprepare,
            commands::docking::ligand_prepare,
            commands::docking::pocket_detect,
            commands::docking::docking_run,
            commands::docking::docking_cancel,
            commands::docking::analysis_interactions,
            commands::docking::generate_2d_interaction_map,
            commands::docking::analysis_distance,
            commands::docking::history_list,
            commands::docking::history_load,
            commands::docking::history_star,
            commands::docking::history_delete,
            commands::docking::read_text_file,
            commands::docking::cluster_poses,
            commands::fate::compute_environmental_fate,
            commands::fate::predict_transformation_products,
            // Regulatory commands
            commands::regulatory::assess_registration_risk,
            commands::regulatory::assess_registration_risk_batch,
            // Reference commands
            commands::reference::list_reference_actives,
            // App Meta commands
            commands::app_meta::app_meta_get_first_launch_state,
            commands::app_meta::app_meta_mark_first_launch_complete,
            commands::app_meta::app_meta_get_system_info,
            commands::app_meta::app_meta_get_status,
            commands::app_meta::retrosynthesis_predict,
            commands::app_meta::citation_generate,
            commands::app_meta::app_meta_get_verification_report,
            // Bottleneck commands
            commands::bottleneck::bottleneck_analyze,
            commands::bottleneck::bottleneck_compound,
            commands::bottleneck::bottleneck_attrition,
            commands::bottleneck::bottleneck_suggest_weights,
            commands::bottleneck::bottleneck_list_profiles,
            // Journal commands
            commands::journal::journal_list,
            commands::journal::journal_get,
            commands::journal::journal_lineage,
            commands::journal::journal_override_analytics,
            commands::journal::journal_add_note,
            commands::journal::journal_record_override,
            commands::journal::journal_export,
            // Speciation commands
            commands::speciation::speciation_enumerate,
            commands::speciation::speciation_dominant_at_ph,
            commands::speciation::speciation_profile_curve,
            // Mobility commands
            commands::mobility::mobility_predict,
            // Retro commands
            commands::retro::retro_sascore,
            commands::retro::retro_route_search,
            commands::retro::retro_gate_batch,
            commands::retro::retro_import_stock,
            commands::sar::sar_mmp_index,
            commands::sar::sar_mmp_suggest_transforms,
            commands::sar::sar_free_wilson_fit,
            commands::cartography::cartography_compute_tmap,
            commands::shape::shape_screen_3d,
            commands::active_learning::al_suggest_next_batch,
        ])
        .run(tauri::generate_context!())

        .expect("error while running Edeon Desktop");
}
