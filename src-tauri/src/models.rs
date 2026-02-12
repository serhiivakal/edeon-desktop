/// Edeon Desktop — Data Models
///
/// Rust structs matching the SQLite schema.
/// All types derive Serialize/Deserialize for Tauri IPC.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Project {
    pub id: String,
    pub name: String,
    pub created_at: String,
    pub updated_at: String,
    pub compound_count: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Compound {
    pub id: String,
    pub project_id: String,
    pub name: String,
    pub smiles: String,
    pub mol_weight: Option<f64>,
    pub logp: Option<f64>,
    pub tpsa: Option<f64>,
    pub hbd: Option<i32>,
    pub hba: Option<i32>,
    pub rotatable_bonds: Option<i32>,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompoundPage {
    pub compounds: Vec<Compound>,
    pub total: i64,
    pub page: i64,
    pub page_size: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkflowRecord {
    pub id: String,
    pub project_id: String,
    pub name: String,
    pub status: String,
    pub stages_complete: i32,
    pub total_stages: i32,
    pub compounds_processed: i64,
    pub compounds_total: i64,
    pub current_stage: Option<String>,
    pub started_at: String,
    pub completed_at: Option<String>,
    pub workflow_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SavedModel {
    pub id: String,
    pub name: String,
    pub r#type: String,
    pub algorithm: String,
    pub features: String,
    pub metrics: String,
    pub importances: String,
    pub provenance: String,
    pub curation_report: String,
    pub cv_results: String,
    pub y_scramble: String,
    pub search_results: String,
    pub created_at: String,
    pub ad_reference: Option<Vec<u8>>,
    pub shap_values: Option<Vec<u8>>,
    pub diagnostics: String,
    pub cliffs: String,
    pub schema_version: i32,
    pub deploy_target: Option<String>,
    pub deployed_at: Option<String>,
    pub deployment_status: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ArenaRun {
    pub id: String,
    pub name: String,
    pub created_at: String,
    pub shared: String,
    pub models: String,
    pub ranking: String,
    pub provenance: String,
    pub curation_report: String,
}

pub mod types;
pub mod proxy;
pub mod preferences;




