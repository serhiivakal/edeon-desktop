/// Edeon Desktop — Workflow Commands
///
/// Tauri IPC handlers for running cheminformatics workflows.
/// 6 Stages: Standardize → Properties → Pesticide-likeness
///           → Selectivity → Resistance → MPO Score

use crate::models::WorkflowRecord;
use crate::python::PythonEngine;
use crate::AppState;
use chrono::Utc;
use rusqlite::params;
use serde_json::json;
use tauri::{Emitter, State};
use uuid::Uuid;

const TOTAL_STAGES: i32 = 7;

/// Helper to emit a progress event.
fn emit_progress(
    app: &tauri::AppHandle,
    workflow_id: &str,
    status: &str,
    current_stage: Option<&str>,
    stages_complete: i32,
    total: i64,
    processed: i64,
) {
    let _ = app.emit("workflow://progress", json!({
        "workflow_id": workflow_id,
        "status": status,
        "current_stage": current_stage,
        "stages_complete": stages_complete,
        "total_stages": TOTAL_STAGES,
        "compounds_processed": processed,
        "compounds_total": total,
    }));
}

/// Start a workflow on the active project's compounds.
#[tauri::command]
pub fn start_workflow(
    app: tauri::AppHandle,
    state: State<'_, AppState>,
    project_id: String,
    workflow_name: Option<String>,
    enabled_stages: Option<Vec<String>>,
    mpo_weights: Option<std::collections::HashMap<String, f64>>,
) -> Result<WorkflowRecord, String> {
    let workflow_id = Uuid::new_v4().to_string();
    let name = workflow_name.unwrap_or_else(|| "Resistance-Aware Lead Optimization".to_string());
    let now = Utc::now().to_rfc3339();
    let config_json = serde_json::to_string(&enabled_stages.clone().unwrap_or_default()).ok();

    // Create workflow record
    {
        let db = state.db.lock().map_err(|e| e.to_string())?;
        db.execute(
            "INSERT INTO workflows (id, project_id, name, status, config_json, started_at) VALUES (?1, ?2, ?3, 'running', ?4, ?5)",
            params![workflow_id, project_id, name, config_json, now],
        ).map_err(|e| e.to_string())?;
    }

    // Load all compound SMILES
    let compounds: Vec<(String, String, String)> = {
        let db = state.db.lock().map_err(|e| e.to_string())?;
        let mut stmt = db.prepare(
            "SELECT id, name, smiles FROM compounds WHERE project_id = ?1 ORDER BY name"
        ).map_err(|e| e.to_string())?;
        let rows = stmt.query_map(params![project_id], |row| {
            Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?, row.get::<_, String>(2)?))
        }).map_err(|e| e.to_string())?;
        rows.collect::<Result<Vec<_>, _>>().map_err(|e| e.to_string())?
    };

    let total = compounds.len() as i64;
    if total == 0 {
        let db = state.db.lock().map_err(|e| e.to_string())?;
        db.execute("UPDATE workflows SET status = 'failed', completed_at = ?1 WHERE id = ?2",
            params![Utc::now().to_rfc3339(), workflow_id]).map_err(|e| e.to_string())?;
        return Err("No compounds in project to process".to_string());
    }

    let is_enabled = |stage_name: &str| -> bool {
        match &enabled_stages {
            Some(stages) => stages.iter().any(|s| s == stage_name),
            None => true,
        }
    };

    emit_progress(&app, &workflow_id, "running", Some("Standardize"), 0, total, 0);

    // Spawn Python engine
    let mut engine = {
        let mut py = state.python.lock().map_err(|e| e.to_string())?;
        if py.is_none() {
            *py = Some(PythonEngine::spawn()?);
        }
        py.take().ok_or("Python engine not available")?
    };

    // Macro to check cancellation and return engine on cancel/error
    macro_rules! try_stage {
        ($expr:expr, $stage:expr, $state:expr, $engine:expr, $wf_id:expr) => {
            {
                let cancelled = $state.cancelled_workflows.lock().map_err(|e| e.to_string())?;
                if cancelled.contains($wf_id) {
                    let mut py = $state.python.lock().map_err(|e2| e2.to_string())?;
                    *py = Some($engine);
                    update_workflow_failed(&$state, $wf_id)?;
                    return Err(format!("Workflow cancelled by user"));
                }
                drop(cancelled);
                match $expr {
                    Ok(val) => val,
                    Err(e) => {
                        let mut py = $state.python.lock().map_err(|e2| e2.to_string())?;
                        *py = Some($engine);
                        update_workflow_failed(&$state, $wf_id)?;
                        return Err(format!("{} failed: {}", $stage, e));
                    }
                }
            }
        };
    }

    // ─── Stage 1: Standardize ───────────────────────────────
    let smiles_list: Vec<&str> = compounds.iter().map(|(_, _, s)| s.as_str()).collect();
    let std_result = try_stage!(
        engine.send_request("standardize", json!({"smiles": smiles_list})),
        "Standardize", state, engine, &workflow_id
    );
    let standardized = std_result.as_array().ok_or("Expected array from standardize")?.clone();

    // Update canonical SMILES in DB
    {
        let db = state.db.lock().map_err(|e| e.to_string())?;
        for (i, item) in standardized.iter().enumerate() {
            if let Some(canonical) = item.get("canonical").and_then(|v| v.as_str()) {
                let _ = db.execute("UPDATE compounds SET smiles = ?1 WHERE id = ?2",
                    params![canonical, compounds[i].0]);
            }
        }
    }

    let valid_count = standardized.iter()
        .filter(|s| s.get("valid").and_then(|v| v.as_bool()).unwrap_or(false)).count() as i64;

    emit_progress(&app, &workflow_id, "running", Some("Properties"), 1, total, valid_count);

    // ─── Stage 2: Compute Properties ────────────────────────
    let valid_smiles: Vec<&str> = standardized.iter()
        .filter_map(|s| {
            if s.get("valid").and_then(|v| v.as_bool()).unwrap_or(false) {
                s.get("canonical").and_then(|v| v.as_str())
            } else { None }
        }).collect();

    let props_result = try_stage!(
        engine.send_request("compute_properties", json!({"smiles": valid_smiles})),
        "Properties", state, engine, &workflow_id
    );
    let properties = props_result.as_array().ok_or("Expected array from compute_properties")?.clone();

    // Update compound properties in DB
    {
        let db = state.db.lock().map_err(|e| e.to_string())?;
        let mut pi = 0;
        for (i, std_item) in standardized.iter().enumerate() {
            if !std_item.get("valid").and_then(|v| v.as_bool()).unwrap_or(false) { continue; }
            if pi >= properties.len() { break; }
            let p = &properties[pi];
            let _ = db.execute(
                "UPDATE compounds SET mol_weight=?1, logp=?2, tpsa=?3, hbd=?4, hba=?5, rotatable_bonds=?6 WHERE id=?7",
                params![
                    p.get("mol_weight").and_then(|v| v.as_f64()),
                    p.get("logp").and_then(|v| v.as_f64()),
                    p.get("tpsa").and_then(|v| v.as_f64()),
                    p.get("hbd").and_then(|v| v.as_i64()),
                    p.get("hba").and_then(|v| v.as_i64()),
                    p.get("rotatable_bonds").and_then(|v| v.as_i64()),
                    compounds[i].0,
                ]);
            pi += 1;
        }
    }

    emit_progress(&app, &workflow_id, "running", Some("Pesticide-likeness"), 2, total, valid_count);

    // ─── Stage 3: Pesticide-likeness ────────────────────────
    let tice_results = if is_enabled("Pesticide-likeness") {
        let tice_result = try_stage!(
            engine.send_request("pesticide_likeness", json!({"compounds": properties})),
            "Pesticide-likeness", state, engine, &workflow_id
        );
        tice_result.as_array().ok_or("Expected array from pesticide_likeness")?.clone()
    } else {
        vec![json!({"level": "High", "violations": [], "disabled": true}); properties.len()]
    };

    emit_progress(&app, &workflow_id, "running", Some("Selectivity"), 3, total, valid_count);

    // ─── Stage 4: Cross-species Selectivity ─────────────────
    let selectivity_results = if is_enabled("Selectivity") {
        let sel_result = try_stage!(
            engine.send_request("selectivity", json!({"compounds": properties})),
            "Selectivity", state, engine, &workflow_id
        );
        sel_result.as_array().ok_or("Expected array from selectivity")?.clone()
    } else {
        vec![json!({"min_selectivity": 10.0, "overall_level": "safe", "profiles": [], "disabled": true}); properties.len()]
    };

    emit_progress(&app, &workflow_id, "running", Some("Resistance"), 4, total, valid_count);

    // ─── Stage 5: Resistance Analysis ───────────────────────
    let resistance_results = if is_enabled("Resistance") {
        let res_result = try_stage!(
            engine.send_request("resistance", json!({"compounds": properties})),
            "Resistance", state, engine, &workflow_id
        );
        res_result.as_array().ok_or("Expected array from resistance")?.clone()
    } else {
        vec![json!({"level": "Low", "risk_score": 0.0, "factors": [], "disabled": true}); properties.len()]
    };

    emit_progress(&app, &workflow_id, "running", Some("Toxicity"), 5, total, valid_count);

    // ─── Stage 6: Toxicity Prediction ───────────────────────
    let toxicity_results = if is_enabled("Toxicity") {
        let tox_result = try_stage!(
            engine.send_request("toxicity", json!({"compounds": properties})),
            "Toxicity", state, engine, &workflow_id
        );
        tox_result.as_array().ok_or("Expected array from toxicity")?.clone()
    } else {
        vec![json!({
            "overall_level": "Low",
            "predictions": [],
            "applicability_domain": {"status": "in_domain", "confidence": 1.0, "warnings": []},
            "disabled": true
        }); properties.len()]
    };

    emit_progress(&app, &workflow_id, "running", Some("MPO Score"), 6, total, valid_count);

    // ─── Stage 7: MPO Composite Scoring ─────────────────────
    let mpo_result = try_stage!(
        engine.send_request("mpo_score", json!({
            "properties": properties,
            "tice_results": tice_results,
            "selectivity_results": selectivity_results,
            "resistance_results": resistance_results,
            "toxicity_results": toxicity_results,
            "weights": mpo_weights,
        })),
        "MPO Score", state, engine, &workflow_id
    );
    let mpo_results = mpo_result.as_array().ok_or("Expected array from mpo_score")?.clone();

    // ─── Store all results ──────────────────────────────────
    {
        let db = state.db.lock().map_err(|e| e.to_string())?;
        let mut pi = 0;
        for (i, std_item) in standardized.iter().enumerate() {
            if !std_item.get("valid").and_then(|v| v.as_bool()).unwrap_or(false) { continue; }
            if pi >= mpo_results.len() { break; }

            let tice = &tice_results[pi];
            let sel = &selectivity_results[pi];
            let res = &resistance_results[pi];
            let tox = &toxicity_results[pi];
            let mpo = &mpo_results[pi];

            let result_id = Uuid::new_v4().to_string();
            let results_json = json!({
                "pesticide_likeness": tice.get("level"),
                "pesticide_likeness_disabled": tice.get("disabled"),
                "tice_violations": tice.get("violations"),
                "selectivity": sel,
                "resistance": res,
                "toxicity": tox,
                "mpo": mpo,
                "score": mpo.get("score"),
            }).to_string();

            let score = mpo.get("score").and_then(|v| v.as_f64()).unwrap_or(0.0);

            let uq_json = json!({
                "toxicity": {
                    "ad_status": tox.get("applicability_domain").and_then(|ad| ad.get("status")).unwrap_or(&json!("unknown")),
                    "ad_score": tox.get("applicability_domain").and_then(|ad| ad.get("confidence")).unwrap_or(&json!(null)),
                    "ci_lower": null,
                    "ci_upper": null,
                }
            }).to_string();

            let _ = db.execute(
                "INSERT OR REPLACE INTO workflow_results (id, workflow_id, compound_id, stage, results_json, score, uq_json) VALUES (?1, ?2, ?3, 'mpo', ?4, ?5, ?6)",
                params![result_id, workflow_id, compounds[i].0, results_json, score, uq_json],
            );
            pi += 1;
        }
    }

    // Put engine back
    {
        let mut py = state.python.lock().map_err(|e| e.to_string())?;
        *py = Some(engine);
    }

    // Mark complete
    let completed_at = Utc::now().to_rfc3339();
    {
        let db = state.db.lock().map_err(|e| e.to_string())?;
        db.execute("UPDATE workflows SET status = 'complete', completed_at = ?1 WHERE id = ?2",
            params![completed_at, workflow_id]).map_err(|e| e.to_string())?;
    }

    emit_progress(&app, &workflow_id, "complete", None, TOTAL_STAGES, total, total);

    Ok(WorkflowRecord {
        id: workflow_id,
        project_id,
        name,
        status: "complete".to_string(),
        stages_complete: TOTAL_STAGES,
        total_stages: TOTAL_STAGES,
        compounds_processed: total,
        compounds_total: total,
        current_stage: None,
        started_at: now,
        completed_at: Some(completed_at),
        workflow_id: None,
    })
}

/// Get workflow results (compounds with all scored data).
#[tauri::command]
pub fn get_workflow_results(
    state: State<'_, AppState>,
    workflow_id: String,
) -> Result<Vec<serde_json::Value>, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;

    let mut stmt = db.prepare(
        "SELECT c.id, c.name, c.smiles, c.mol_weight, c.logp, c.tpsa, c.hbd, c.hba, c.rotatable_bonds,
                wr.results_json, wr.score, wr.uq_json
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
            .unwrap_or(serde_json::json!({}));

        let uq_json: Option<String> = row.get(11)?;
        let parsed_uq = uq_json
            .as_ref()
            .and_then(|s| serde_json::from_str::<serde_json::Value>(s).ok())
            .unwrap_or(serde_json::json!({}));

        let mut result_obj = match parsed {
            serde_json::Value::Object(map) => map,
            _ => serde_json::Map::new(),
        };

        result_obj.insert("id".to_string(), serde_json::json!(row.get::<_, String>(0)?));
        result_obj.insert("name".to_string(), serde_json::json!(row.get::<_, String>(1)?));
        result_obj.insert("smiles".to_string(), serde_json::json!(row.get::<_, String>(2)?));
        if let Some(val) = row.get::<_, Option<f64>>(3)? {
            result_obj.insert("mol_weight".to_string(), serde_json::json!(val));
        }
        if let Some(val) = row.get::<_, Option<f64>>(4)? {
            result_obj.insert("logp".to_string(), serde_json::json!(val));
        }
        if let Some(val) = row.get::<_, Option<f64>>(5)? {
            result_obj.insert("tpsa".to_string(), serde_json::json!(val));
        }
        if let Some(val) = row.get::<_, Option<i32>>(6)? {
            result_obj.insert("hbd".to_string(), serde_json::json!(val));
        }
        if let Some(val) = row.get::<_, Option<i32>>(7)? {
            result_obj.insert("hba".to_string(), serde_json::json!(val));
        }
        if let Some(val) = row.get::<_, Option<i32>>(8)? {
            result_obj.insert("rotatable_bonds".to_string(), serde_json::json!(val));
        }
        result_obj.insert("score".to_string(), serde_json::json!(row.get::<_, Option<f64>>(10)?));
        result_obj.insert("uq".to_string(), parsed_uq);

        Ok(serde_json::Value::Object(result_obj))
    }).map_err(|e| e.to_string())?;


    rows.collect::<Result<Vec<_>, _>>().map_err(|e| e.to_string())
}

/// Get workflow status.
#[tauri::command]
pub fn get_workflow_status(
    state: State<'_, AppState>,
    workflow_id: String,
) -> Result<WorkflowRecord, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    db.query_row(
        "SELECT id, project_id, name, status, started_at, completed_at, workflow_id FROM workflows WHERE id = ?1",
        params![workflow_id],
        |row| {
            let status: String = row.get(3)?;
            Ok(WorkflowRecord {
                id: row.get(0)?,
                project_id: row.get(1)?,
                name: row.get(2)?,
                stages_complete: if status == "complete" { TOTAL_STAGES } else { 0 },
                total_stages: TOTAL_STAGES,
                compounds_processed: 0,
                compounds_total: 0,
                current_stage: None,
                status,
                started_at: row.get(4)?,
                completed_at: row.get(5)?,
                workflow_id: row.get(6)?,
            })
        },
    ).map_err(|e| e.to_string())
}

/// List workflows for a project.
#[tauri::command]
pub fn list_workflows(
    state: State<'_, AppState>,
    project_id: String,
) -> Result<Vec<WorkflowRecord>, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    let mut stmt = db.prepare(
        "SELECT id, project_id, name, status, started_at, completed_at, workflow_id FROM workflows WHERE project_id = ?1 ORDER BY started_at DESC"
    ).map_err(|e| e.to_string())?;

    let rows = stmt.query_map(params![project_id], |row| {
        let status: String = row.get(3)?;
        Ok(WorkflowRecord {
            id: row.get(0)?,
            project_id: row.get(1)?,
            name: row.get(2)?,
            stages_complete: if status == "complete" { TOTAL_STAGES } else { 0 },
            total_stages: TOTAL_STAGES,
            compounds_processed: 0,
            compounds_total: 0,
            current_stage: None,
            status,
            started_at: row.get(4)?,
            completed_at: row.get(5)?,
            workflow_id: row.get(6)?,
        })
    }).map_err(|e| e.to_string())?;

    rows.collect::<Result<Vec<_>, _>>().map_err(|e| e.to_string())
}

/// Check Python engine availability.
#[tauri::command]
pub fn check_python_engine(state: State<'_, AppState>) -> Result<bool, String> {
    match state.get_python_engine() {
        Ok(mut py) => {
            if let Some(ref mut engine) = *py {
                Ok(engine.ping().unwrap_or(false))
            } else {
                Ok(false)
            }
        }
        Err(_) => Ok(false),
    }
}
/// Generate SVG depiction of a compound from its SMILES.
#[tauri::command]
pub async fn depict_compound(
    smiles: String,
) -> Result<String, String> {
    let python_cmd = crate::python::find_python()?;

    let python_code = r#"
import sys, io
from rdkit import Chem
from rdkit.Chem.Draw import rdMolDraw2D

smiles = sys.argv[1]
mol = Chem.MolFromSmiles(smiles)
if mol is None:
    sys.exit("Invalid SMILES")

from rdkit.Chem import rdDepictor
rdDepictor.Compute2DCoords(mol)

drawer = rdMolDraw2D.MolDraw2DSVG(250, 180)
opts = drawer.drawOptions()
opts.addStereoAnnotation = True
opts.bondLineWidth = 1.2
opts.padding = 0.12
opts.clearBackground = False  # Transparent background
drawer.DrawMolecule(mol)
drawer.FinishDrawing()
svg = drawer.GetDrawingText()
# Strip XML declaration if present
if svg.startswith('<?xml'):
    svg = svg[svg.index('?>') + 2:].strip()
print(svg)
"#;

    let output = std::process::Command::new(&python_cmd)
        .args(["-c", python_code, &smiles])
        .output()
        .map_err(|e| format!("Failed to spawn Python: {e}"))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Depiction failed: {stderr}"));
    }

    let svg = String::from_utf8(output.stdout)
        .map_err(|e| format!("Invalid UTF-8 in SVG output: {e}"))?;

    if svg.trim().is_empty() {
        return Err("Empty SVG returned".into());
    }

    Ok(svg)
}

/// Invoke a general JSON-RPC method on the Python engine.
#[tauri::command]
pub fn invoke_python_rpc(
    state: State<'_, AppState>,
    method: String,
    params: serde_json::Value,
) -> Result<serde_json::Value, String> {
    let mut py = state.python.lock().map_err(|e| e.to_string())?;
    if py.is_none() {
        *py = Some(PythonEngine::spawn()?);
    }
    let engine = py.as_mut().ok_or("Python engine not available")?;
    engine.send_request(&method, params)
}

/// Compute Maximum Common Substructure across a set of SMILES.
#[tauri::command]
pub fn compute_mcs(
    state: State<'_, AppState>,
    smiles: Vec<String>,
) -> Result<serde_json::Value, String> {
    let mut py = state.python.lock().map_err(|e| e.to_string())?;
    if py.is_none() {
        *py = Some(PythonEngine::spawn()?);
    }
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request("compute_mcs", json!({
        "smiles": smiles,
        "timeout": 30,
    }))
}

/// Standardize a list of SMILES using the Python engine.
#[tauri::command]
pub fn standardize(
    state: State<'_, AppState>,
    smiles: Vec<String>,
) -> Result<serde_json::Value, String> {
    let mut py = state.python.lock().map_err(|e| e.to_string())?;
    if py.is_none() {
        *py = Some(PythonEngine::spawn()?);
    }
    let engine = py.as_mut().ok_or("Python engine not available")?;

    engine.send_request("standardize", json!({
        "smiles": smiles,
    }))
}

/// Depict a molecule with MCS atoms highlighted.
#[tauri::command]
pub async fn depict_mcs(
    smiles: String,
    mcs_smarts: String,
) -> Result<String, String> {
    let python_cmd = crate::python::find_python()?;

    let python_code = r#"
import sys
from rdkit import Chem
from rdkit.Chem import rdDepictor, AllChem
from rdkit.Chem.Draw import rdMolDraw2D

smiles = sys.argv[1]
mcs_smarts = sys.argv[2]

mol = Chem.MolFromSmiles(smiles)
if mol is None:
    sys.exit("Invalid SMILES")

rdDepictor.Compute2DCoords(mol)

pattern = Chem.MolFromSmarts(mcs_smarts)
highlight_atoms = []
highlight_bonds = []
if pattern:
    match = mol.GetSubstructMatch(pattern)
    if match:
        highlight_atoms = list(match)
        for bond in pattern.GetBonds():
            aid1 = match[bond.GetBeginAtomIdx()]
            aid2 = match[bond.GetEndAtomIdx()]
            bond_idx = mol.GetBondBetweenAtoms(aid1, aid2)
            if bond_idx:
                highlight_bonds.append(bond_idx.GetIdx())

drawer = rdMolDraw2D.MolDraw2DSVG(250, 180)
opts = drawer.drawOptions()
opts.addStereoAnnotation = True
opts.bondLineWidth = 1.2
opts.padding = 0.12
opts.clearBackground = False  # Transparent background

from rdkit.Geometry import Point2D
if highlight_atoms:
    colors_atoms = {a: (0.37, 0.73, 0.55, 0.3) for a in highlight_atoms}
    colors_bonds = {b: (0.37, 0.73, 0.55, 0.5) for b in highlight_bonds}
    radii = {a: 0.3 for a in highlight_atoms}
    drawer.DrawMolecule(
        mol,
        highlightAtoms=highlight_atoms,
        highlightBonds=highlight_bonds,
        highlightAtomColors=colors_atoms,
        highlightBondColors=colors_bonds,
        highlightAtomRadii=radii,
    )
else:
    drawer.DrawMolecule(mol)

drawer.FinishDrawing()
svg = drawer.GetDrawingText()
if svg.startswith('<?xml'):
    svg = svg[svg.index('?>') + 2:].strip()
print(svg)
"#;

    let output = std::process::Command::new(&python_cmd)
        .args(["-c", python_code, &smiles, &mcs_smarts])
        .output()
        .map_err(|e| format!("Failed to spawn Python: {e}"))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("MCS depiction failed: {stderr}"));
    }

    let svg = String::from_utf8(output.stdout)
        .map_err(|e| format!("Invalid UTF-8 in SVG output: {e}"))?;

    if svg.trim().is_empty() {
        return Err("Empty SVG returned".into());
    }

    Ok(svg)
}

/// Cancel a running workflow by updating the database and adding it to the cancelled set.
#[tauri::command]
pub fn cancel_workflow(
    state: State<'_, AppState>,
    workflow_id: String,
) -> Result<(), String> {
    let mut cancelled = state.cancelled_workflows.lock().map_err(|e| e.to_string())?;
    cancelled.insert(workflow_id.clone());
    
    let db = state.db.lock().map_err(|e| e.to_string())?;
    db.execute(
        "UPDATE workflows SET status = 'failed', completed_at = ?1 WHERE id = ?2",
        params![Utc::now().to_rfc3339(), workflow_id],
    ).map_err(|e| e.to_string())?;
    
    Ok(())
}

fn update_workflow_failed(state: &State<'_, AppState>, workflow_id: &str) -> Result<(), String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    db.execute("UPDATE workflows SET status = 'failed', completed_at = ?1 WHERE id = ?2",
        params![Utc::now().to_rfc3339(), workflow_id]).map_err(|e| e.to_string())?;
    Ok(())
}

/// Generate 3D optimized coordinates (SDF format block) from a SMILES.
/// Uses the persistent PythonEngine for fast turnaround (avoids re-importing RDKit).
#[tauri::command]
pub fn generate_3d_conformer(
    state: State<'_, AppState>,
    smiles: String,
) -> Result<String, String> {
    let mut py = state.python.lock().map_err(|e| e.to_string())?;
    if py.is_none() {
        *py = Some(PythonEngine::spawn()?);
    }
    let engine = py.as_mut().ok_or("Python engine not available")?;

    let result = engine.send_request("generate_3d_conformer", json!({
        "smiles": smiles,
    }))?;

    // The result is the SDF block string
    match result.as_str() {
        Some(sdf) if !sdf.trim().is_empty() => Ok(sdf.to_string()),
        _ => Err("Empty or invalid SDF returned from conformer generation".into()),
    }
}

/// Export workflow results as a CSV string returned to the frontend.
#[tauri::command]
pub fn export_results_csv(
    state: State<'_, AppState>,
    workflow_id: String,
) -> Result<String, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    let mut stmt = db.prepare(
        "SELECT c.name, c.smiles, c.mol_weight, c.logp, c.tpsa, c.hbd, c.hba, c.rotatable_bonds, \
                wr.results_json, wr.score \
         FROM workflow_results wr \
         JOIN compounds c ON wr.compound_id = c.id \
         WHERE wr.workflow_id = ?1 \
         ORDER BY wr.score DESC"
    ).map_err(|e| e.to_string())?;

    let mut csv = String::from(
        "Name,SMILES,MW,LogP,TPSA,HBD,HBA,RotBonds,MPO Score,Rank,Pesticide Likeness,Tice Violations,Selectivity Level,Resistance Level,Toxicity Level\n"
    );

    let rows = stmt.query_map(params![workflow_id], |row| {
        Ok((
            row.get::<_, String>(0)?,
            row.get::<_, String>(1)?,
            row.get::<_, Option<f64>>(2)?,
            row.get::<_, Option<f64>>(3)?,
            row.get::<_, Option<f64>>(4)?,
            row.get::<_, Option<i32>>(5)?,
            row.get::<_, Option<i32>>(6)?,
            row.get::<_, Option<i32>>(7)?,
            row.get::<_, Option<String>>(8)?,
            row.get::<_, Option<f64>>(9)?,
        ))
    }).map_err(|e| e.to_string())?;

    for row in rows {
        let (name, smiles, mw, logp, tpsa, hbd, hba, rot, results_json, score) =
            row.map_err(|e| e.to_string())?;
        let parsed: serde_json::Value = results_json
            .as_ref()
            .and_then(|s| serde_json::from_str(s).ok())
            .unwrap_or(serde_json::json!({}));

        let rank = parsed.pointer("/mpo/rank_category").and_then(|v| v.as_str()).unwrap_or("—");
        let tice_level = parsed.get("pesticide_likeness").and_then(|v| v.as_str()).unwrap_or("—");
        let tice_viol = parsed.pointer("/tice_violations")
            .and_then(|v| v.as_array())
            .map(|a| a.len().to_string())
            .unwrap_or_else(|| "0".to_string());
        let sel_level = parsed.pointer("/selectivity/overall_level").and_then(|v| v.as_str()).unwrap_or("—");
        let res_level = parsed.pointer("/resistance/level").and_then(|v| v.as_str()).unwrap_or("—");
        let tox_level = parsed.pointer("/toxicity/overall_level").and_then(|v| v.as_str()).unwrap_or("—");

        let esc = |s: &str| -> String {
            if s.contains(',') || s.contains('"') || s.contains('\n') {
                format!("\"{}\"", s.replace('"', "\"\""))
            } else {
                s.to_string()
            }
        };

        csv.push_str(&format!(
            "{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}\n",
            esc(&name), esc(&smiles),
            mw.map(|v| format!("{:.2}", v)).unwrap_or_default(),
            logp.map(|v| format!("{:.3}", v)).unwrap_or_default(),
            tpsa.map(|v| format!("{:.1}", v)).unwrap_or_default(),
            hbd.map(|v| v.to_string()).unwrap_or_default(),
            hba.map(|v| v.to_string()).unwrap_or_default(),
            rot.map(|v| v.to_string()).unwrap_or_default(),
            score.map(|v| format!("{:.1}", v)).unwrap_or_default(),
            rank, tice_level, tice_viol, sel_level, res_level, tox_level,
        ));
    }
    Ok(csv)
}

/// Export library compounds as a CSV string.
#[tauri::command]
pub fn export_library_csv(
    state: State<'_, AppState>,
    project_id: String,
) -> Result<String, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    let mut stmt = db.prepare(
        "SELECT name, smiles, mol_weight, logp, tpsa, hbd, hba, rotatable_bonds \
         FROM compounds WHERE project_id = ?1 ORDER BY name"
    ).map_err(|e| e.to_string())?;

    let mut csv = String::from("Name,SMILES,MW,LogP,TPSA,HBD,HBA,RotBonds\n");
    let rows = stmt.query_map(params![project_id], |row| {
        Ok((
            row.get::<_, String>(0)?,
            row.get::<_, String>(1)?,
            row.get::<_, Option<f64>>(2)?,
            row.get::<_, Option<f64>>(3)?,
            row.get::<_, Option<f64>>(4)?,
            row.get::<_, Option<i32>>(5)?,
            row.get::<_, Option<i32>>(6)?,
            row.get::<_, Option<i32>>(7)?,
        ))
    }).map_err(|e| e.to_string())?;

    for row in rows {
        let (name, smiles, mw, logp, tpsa, hbd, hba, rot) = row.map_err(|e| e.to_string())?;
        let esc = |s: &str| -> String {
            if s.contains(',') || s.contains('"') || s.contains('\n') {
                format!("\"{}\"", s.replace('"', "\"\""))
            } else {
                s.to_string()
            }
        };
        csv.push_str(&format!(
            "{},{},{},{},{},{},{},{}\n",
            esc(&name), esc(&smiles),
            mw.map(|v| format!("{:.2}", v)).unwrap_or_default(),
            logp.map(|v| format!("{:.3}", v)).unwrap_or_default(),
            tpsa.map(|v| format!("{:.1}", v)).unwrap_or_default(),
            hbd.map(|v| v.to_string()).unwrap_or_default(),
            hba.map(|v| v.to_string()).unwrap_or_default(),
            rot.map(|v| v.to_string()).unwrap_or_default(),
        ));
    }
    Ok(csv)
}

/// Export workflow results as an SDF string.
/// The SDF is assembled from SMILES and property data via Python and RDKit.
#[tauri::command]
pub fn export_results_sdf(
    state: State<'_, AppState>,
    workflow_id: String,
) -> Result<String, String> {
    // 1. Fetch workflow results from database
    let compounds_data = {
        let db = state.db.lock().map_err(|e| e.to_string())?;
        let mut stmt = db.prepare(
            "SELECT c.name, c.smiles, c.mol_weight, c.logp, c.tpsa, c.hbd, c.hba, c.rotatable_bonds, \
                    wr.results_json, wr.score \
             FROM workflow_results wr \
             JOIN compounds c ON wr.compound_id = c.id \
             WHERE wr.workflow_id = ?1 \
             ORDER BY wr.score DESC"
        ).map_err(|e| e.to_string())?;

        let rows = stmt.query_map(params![workflow_id], |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, Option<f64>>(2)?,
                row.get::<_, Option<f64>>(3)?,
                row.get::<_, Option<f64>>(4)?,
                row.get::<_, Option<i32>>(5)?,
                row.get::<_, Option<i32>>(6)?,
                row.get::<_, Option<i32>>(7)?,
                row.get::<_, Option<String>>(8)?,
                row.get::<_, Option<f64>>(9)?,
            ))
        }).map_err(|e| e.to_string())?;

        let mut data = Vec::new();
        for row in rows {
            let (name, smiles, mw, logp, tpsa, hbd, hba, rot, results_json, score) = row.map_err(|e| e.to_string())?;
            let parsed: serde_json::Value = results_json
                .as_ref()
                .and_then(|s| serde_json::from_str(s).ok())
                .unwrap_or(serde_json::json!({}));

            let rank = parsed.pointer("/mpo/rank_category").and_then(|v| v.as_str()).unwrap_or("—");
            let tice_level = parsed.get("pesticide_likeness").and_then(|v| v.as_str()).unwrap_or("—");
            let sel_level = parsed.pointer("/selectivity/overall_level").and_then(|v| v.as_str()).unwrap_or("—");
            let res_level = parsed.pointer("/resistance/level").and_then(|v| v.as_str()).unwrap_or("—");
            let tox_level = parsed.pointer("/toxicity/overall_level").and_then(|v| v.as_str()).unwrap_or("—");

            data.push(serde_json::json!({
                "name": name,
                "smiles": smiles,
                "mol_weight": mw,
                "logp": logp,
                "tpsa": tpsa,
                "hbd": hbd,
                "hba": hba,
                "rotatable_bonds": rot,
                "score": score,
                "rank": rank,
                "pesticide_likeness": tice_level,
                "selectivity_level": sel_level,
                "resistance_level": res_level,
                "toxicity_level": tox_level
            }));
        }
        data
    };

    // 2. Call Python engine to generate SDF
    let mut engine = {
        let mut py = state.python.lock().map_err(|e| e.to_string())?;
        if py.is_none() {
            *py = Some(PythonEngine::spawn()?);
        }
        py.take().ok_or("Python engine not available")?
    };

    let result = engine.send_request("export_results_sdf", serde_json::json!({
        "compounds": compounds_data
    }));

    // Put engine back
    {
        let mut py = state.python.lock().map_err(|e| e.to_string())?;
        *py = Some(engine);
    }

    let sdf_val = result?;
    let sdf_str = sdf_val.as_str().ok_or("Expected string from export_results_sdf")?;
    Ok(sdf_str.to_string())
}

#[tauri::command]
pub fn bioisostere_suggest(
    state: State<'_, AppState>,
    smiles: String,
    top_n: Option<usize>,
    sort_by: Option<String>,
    weights: Option<serde_json::Value>,
) -> Result<serde_json::Value, String> {
    let mut engine = {
        let mut py = state.python.lock().map_err(|e| e.to_string())?;
        if py.is_none() {
            *py = Some(PythonEngine::spawn()?);
        }
        py.take().ok_or("Python engine not available")?
    };

    let result = engine.send_request("bioisostere_suggest", serde_json::json!({
        "smiles": smiles,
        "top_n": top_n.unwrap_or(50),
        "sort_by": sort_by.unwrap_or_else(|| "composite".to_string()),
        "weights": weights
    }));

    {
        let mut py = state.python.lock().map_err(|e| e.to_string())?;
        *py = Some(engine);
    }

    result
}

#[tauri::command]
pub fn list_available_workflows(
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    let mut py = state.python.lock().map_err(|e| e.to_string())?;
    if py.is_none() {
        *py = Some(PythonEngine::spawn()?);
    }
    let engine = py.as_mut().ok_or("Python engine not available")?;
    engine.send_request("list_workflows", serde_json::json!({}))
}

#[tauri::command]
pub fn get_workflow_details(
    state: State<'_, AppState>,
    workflow_id: String,
) -> Result<serde_json::Value, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    db.query_row(
        "SELECT id, project_id, name, status, started_at, completed_at, workflow_id, params_json, verdict_json, provenance_json FROM workflows WHERE id = ?1",
        params![workflow_id],
        |row| {
            let params_json: Option<String> = row.get(7)?;
            let verdict_json: Option<String> = row.get(8)?;
            let provenance_json: Option<String> = row.get(9)?;

            let parsed_params = params_json
                .as_ref()
                .and_then(|s| serde_json::from_str::<serde_json::Value>(s).ok())
                .unwrap_or(serde_json::json!({}));

            let parsed_verdict = verdict_json
                .as_ref()
                .and_then(|s| serde_json::from_str::<serde_json::Value>(s).ok())
                .unwrap_or(serde_json::Value::Null);

            let parsed_provenance = provenance_json
                .as_ref()
                .and_then(|s| serde_json::from_str::<serde_json::Value>(s).ok())
                .unwrap_or(serde_json::json!({}));

            Ok(serde_json::json!({
                "id": row.get::<_, String>(0)?,
                "project_id": row.get::<_, String>(1)?,
                "name": row.get::<_, String>(2)?,
                "status": row.get::<_, String>(3)?,
                "started_at": row.get::<_, String>(4)?,
                "completed_at": row.get::<_, Option<String>>(5)?,
                "workflow_id": row.get::<_, Option<String>>(6)?,
                "params": parsed_params,
                "verdict": parsed_verdict,
                "provenance": parsed_provenance,
            }))
        },
    ).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn run_named_workflow(
    app: tauri::AppHandle,
    state: State<'_, AppState>,
    project_id: String,
    workflow_id: String,
    workflow_name: Option<String>,
    params: serde_json::Value,
) -> Result<WorkflowRecord, String> {
    let run_uuid = Uuid::new_v4().to_string();
    let now = Utc::now().to_rfc3339();
    let params_str = serde_json::to_string(&params).unwrap_or_else(|_| "{}".to_string());

    // 1. Insert workflow run record
    {
        let db = state.db.lock().map_err(|e| e.to_string())?;
        db.execute(
            "INSERT INTO workflows (id, project_id, name, status, started_at, workflow_id, params_json) VALUES (?1, ?2, ?3, 'running', ?4, ?5, ?6)",
            params![
                run_uuid,
                project_id,
                workflow_name.clone().unwrap_or_else(|| workflow_id.clone()),
                now,
                workflow_id,
                params_str
            ],
        ).map_err(|e| e.to_string())?;
    }

    // 2. Fetch compounds
    let compounds: Vec<(String, String, String)> = {
        let db = state.db.lock().map_err(|e| e.to_string())?;
        let mut stmt = db.prepare(
            "SELECT id, name, smiles FROM compounds WHERE project_id = ?1 ORDER BY name"
        ).map_err(|e| e.to_string())?;
        let rows = stmt.query_map(params![project_id], |row| {
            Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?, row.get::<_, String>(2)?))
        }).map_err(|e| e.to_string())?;
        rows.collect::<Result<Vec<_>, _>>().map_err(|e| e.to_string())?
    };

    let total = compounds.len() as i64;
    if total == 0 {
        let db = state.db.lock().map_err(|e| e.to_string())?;
        db.execute(
            "UPDATE workflows SET status = 'failed', completed_at = ?1 WHERE id = ?2",
            params![Utc::now().to_rfc3339(), run_uuid]
        ).map_err(|e| e.to_string())?;
        return Err("No compounds in project to process".to_string());
    }

    // Emit initial progress
    let _ = app.emit("workflow://progress", serde_json::json!({
        "workflow_id": run_uuid,
        "status": "running",
        "current_stage": "starting",
        "stages_complete": 0,
        "total_stages": 10,
        "compounds_processed": 0,
        "compounds_total": total,
    }));

    // 3. Acquire Python engine
    let mut engine = {
        let mut py = state.python.lock().map_err(|e| e.to_string())?;
        if py.is_none() {
            *py = Some(PythonEngine::spawn()?);
        }
        py.take().ok_or("Python engine not available")?
    };

    // 4. Run the workflow in Python (which writes [WORKFLOW_PROGRESS] to stdout)
    let smiles_list: Vec<&str> = compounds.iter().map(|(_, _, s)| s.as_str()).collect();
    let req_payload = serde_json::json!({
        "run_id": run_uuid,
        "workflow_id": workflow_id,
        "input": {
            "smiles": smiles_list,
        },
        "params": params,
    });

    let run_res = engine.send_request_with_app("run_workflow", req_payload, Some(&app));

    // Put engine back
    {
        let mut py = state.python.lock().map_err(|e| e.to_string())?;
        *py = Some(engine);
    }

    let result_val = match run_res {
        Ok(val) => val,
        Err(err) => {
            let db = state.db.lock().map_err(|e| e.to_string())?;
            db.execute(
                "UPDATE workflows SET status = 'failed', completed_at = ?1 WHERE id = ?2",
                params![Utc::now().to_rfc3339(), run_uuid]
            ).map_err(|e| e.to_string())?;
            return Err(format!("Workflow failed: {}", err));
        }
    };

    // 5. Parse output and store in database
    let overall_verdict_val = serde_json::json!({
        "overall": result_val.get("overall"),
        "sections": result_val.get("sections"),
        "warnings": result_val.get("warnings")
    });
    let overall_verdict_str = Some(overall_verdict_val.to_string());
    let provenance_str = result_val.get("provenance")
        .map(|v| v.to_string())
        .unwrap_or_else(|| "{}".to_string());

    // Update workflow record in DB and record journal entry atomically
    let completed_at = Utc::now().to_rfc3339();
    {
        let mut db = state.db.lock().map_err(|e| e.to_string())?;
        let tx = db.transaction().map_err(|e| e.to_string())?;

        tx.execute(
            "UPDATE workflows SET status = 'complete', completed_at = ?1, verdict_json = ?2, provenance_json = ?3 WHERE id = ?4",
            params![completed_at, overall_verdict_str, provenance_str, run_uuid]
        ).map_err(|e| e.to_string())?;

        let verdict_summary = result_val.pointer("/overall/band")
            .and_then(|v| v.as_str())
            .unwrap_or("completed");
        let summary_text = format!(
            "Workflow '{}: {}' completed: band '{}' ({}/{} compounds processed)",
            workflow_id, workflow_name.as_deref().unwrap_or(""), verdict_summary, total, total
        );

        let entry = crate::journal::JournalEntry::new_system(
            &project_id,
            "workflow_verdict",
            "workflow",
            &run_uuid,
            &summary_text,
            &provenance_str,
        );
        let _ = crate::journal::append(&tx, &entry);

        tx.commit().map_err(|e| e.to_string())?;
    }

    // Save per-compound results
    if let Some(per_compound) = result_val.get("per_compound").and_then(|v| v.as_array()) {
        let db = state.db.lock().map_err(|e| e.to_string())?;
        for (i, compound_res) in per_compound.iter().enumerate() {
            if i >= compounds.len() {
                break;
            }
            let res_uuid = Uuid::new_v4().to_string();
            let score = compound_res.pointer("/mpo/score")
                .or_else(|| compound_res.get("score"))
                .and_then(|v| v.as_f64())
                .unwrap_or(0.0);

            let results_json = compound_res.to_string();

            // UQ json structure
            let uq_json = serde_json::json!({
                "toxicity": {
                    "ad_status": compound_res.pointer("/verdict/confidence").unwrap_or(&serde_json::Value::Null),
                    "ad_score": null,
                    "ci_lower": null,
                    "ci_upper": null,
                }
            }).to_string();

            let _ = db.execute(
                "INSERT OR REPLACE INTO workflow_results (id, workflow_id, compound_id, stage, results_json, score, uq_json) VALUES (?1, ?2, ?3, 'final', ?4, ?5, ?6)",
                params![res_uuid, run_uuid, compounds[i].0, results_json, score, uq_json],
            );
        }
    }

    // Emit final complete event
    let _ = app.emit("workflow://progress", serde_json::json!({
        "workflow_id": run_uuid,
        "status": "complete",
        "current_stage": serde_json::Value::Null,
        "stages_complete": 10,
        "total_stages": 10,
        "compounds_processed": total,
        "compounds_total": total,
    }));

    Ok(WorkflowRecord {
        id: run_uuid,
        project_id,
        name: workflow_name.unwrap_or_else(|| workflow_id.clone()),
        status: "complete".to_string(),
        stages_complete: 10,
        total_stages: 10,
        compounds_processed: total,
        compounds_total: total,
        current_stage: None,
        started_at: now,
        completed_at: Some(completed_at),
        workflow_id: Some(workflow_id),
    })
}


