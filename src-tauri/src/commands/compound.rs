/// Edeon Desktop — Compound Commands
///
/// Tauri IPC handlers for compound import, listing, and management.

use crate::models::{Compound, CompoundPage};
use crate::AppState;
use tauri::State;
use uuid::Uuid;
use chrono::Utc;
use std::path::Path;

#[tauri::command]
pub fn import_compounds_csv(
    state: State<'_, AppState>,
    project_id: String,
    file_path: String,
) -> Result<i64, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    let path = Path::new(&file_path);

    if !path.exists() {
        return Err(format!("File not found: {}", file_path));
    }

    let mut reader = csv::ReaderBuilder::new()
        .has_headers(true)
        .flexible(true)
        .from_path(path)
        .map_err(|e| format!("Failed to read CSV: {}", e))?;

    // Detect column indices from headers
    let headers = reader.headers().map_err(|e| e.to_string())?.clone();
    let name_idx = headers.iter().position(|h| {
        let h = h.to_lowercase();
        h == "name" || h == "compound_name" || h == "compound"
    });
    let smiles_idx = headers.iter().position(|h| {
        let h = h.to_lowercase();
        h == "smiles" || h == "canonical_smiles" || h == "smi"
    });

    let smiles_idx = smiles_idx.ok_or_else(|| {
        "CSV must contain a 'smiles' (or 'smi', 'canonical_smiles') column".to_string()
    })?;

    let now = Utc::now().to_rfc3339();
    let mut imported: i64 = 0;

    // Use a transaction for batch insert performance
    db.execute("BEGIN TRANSACTION", []).map_err(|e| e.to_string())?;

    for (row_num, result) in reader.records().enumerate() {
        let record = result.map_err(|e| format!("Row {}: {}", row_num + 2, e))?;

        let smiles = record.get(smiles_idx).unwrap_or("").trim();
        if smiles.is_empty() {
            continue; // Skip rows with empty SMILES
        }

        let name = match name_idx {
            Some(idx) => {
                let n = record.get(idx).unwrap_or("").trim();
                if n.is_empty() {
                    format!("Compound-{}", row_num + 1)
                } else {
                    n.to_string()
                }
            }
            None => format!("Compound-{}", row_num + 1),
        };

        let id = Uuid::new_v4().to_string();

        db.execute(
            "INSERT INTO compounds (id, project_id, name, smiles, created_at) VALUES (?1, ?2, ?3, ?4, ?5)",
            rusqlite::params![id, project_id, name, smiles, now],
        )
        .map_err(|e| format!("Failed to insert compound '{}': {}", name, e))?;

        imported += 1;
    }

    // Update project compound count
    db.execute(
        "UPDATE projects SET compound_count = (SELECT COUNT(*) FROM compounds WHERE project_id = ?1), updated_at = ?2 WHERE id = ?1",
        rusqlite::params![project_id, now],
    )
    .map_err(|e| e.to_string())?;

    db.execute("COMMIT", []).map_err(|e| e.to_string())?;

    Ok(imported)
}

#[derive(serde::Deserialize, Clone, Debug)]
pub struct PropertyFilters {
    pub mw_min: Option<f64>,
    pub mw_max: Option<f64>,
    pub logp_min: Option<f64>,
    pub logp_max: Option<f64>,
    pub tpsa_min: Option<f64>,
    pub tpsa_max: Option<f64>,
    pub hbd_min: Option<i64>,
    pub hbd_max: Option<i64>,
}

#[tauri::command]
pub fn list_compounds(
    state: State<'_, AppState>,
    project_id: String,
    page: Option<i64>,
    page_size: Option<i64>,
    sort_by: Option<String>,
    sort_dir: Option<String>,
    search: Option<String>,
    filters: Option<PropertyFilters>,
) -> Result<CompoundPage, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;

    let page = page.unwrap_or(1).max(1);
    let page_size = page_size.unwrap_or(25).clamp(1, 500);
    let offset = (page - 1) * page_size;

    // Validate sort column to prevent SQL injection
    let sort_column = match sort_by.as_deref() {
        Some("name") => "name",
        Some("smiles") => "smiles",
        Some("mol_weight") => "mol_weight",
        Some("logp") => "logp",
        Some("tpsa") => "tpsa",
        Some("hbd") => "hbd",
        Some("created_at") => "created_at",
        _ => "name",
    };

    let sort_direction = match sort_dir.as_deref() {
        Some("desc") | Some("DESC") => "DESC",
        _ => "ASC",
    };

    let search_pattern = search
        .as_ref()
        .filter(|s| !s.is_empty())
        .map(|s| format!("%{}%", s));

    let has_search = search_pattern.is_some();

    // Construct property ranges filters clause
    let mut filters_clause = String::new();
    if let Some(ref f) = filters {
        if let Some(val) = f.mw_min { filters_clause.push_str(&format!(" AND mol_weight >= {}", val)); }
        if let Some(val) = f.mw_max { filters_clause.push_str(&format!(" AND mol_weight <= {}", val)); }
        if let Some(val) = f.logp_min { filters_clause.push_str(&format!(" AND logp >= {}", val)); }
        if let Some(val) = f.logp_max { filters_clause.push_str(&format!(" AND logp <= {}", val)); }
        if let Some(val) = f.tpsa_min { filters_clause.push_str(&format!(" AND tpsa >= {}", val)); }
        if let Some(val) = f.tpsa_max { filters_clause.push_str(&format!(" AND tpsa <= {}", val)); }
        if let Some(val) = f.hbd_min { filters_clause.push_str(&format!(" AND hbd >= {}", val)); }
        if let Some(val) = f.hbd_max { filters_clause.push_str(&format!(" AND hbd <= {}", val)); }
    }

    // Count total matching
    let total: i64 = if let Some(ref pattern) = search_pattern {
        let sql = format!(
            "SELECT COUNT(*) FROM compounds WHERE project_id = ?1 AND (name LIKE ?2 OR smiles LIKE ?2){}",
            filters_clause
        );
        db.query_row(&sql, rusqlite::params![project_id, pattern], |row| row.get(0))
            .map_err(|e| e.to_string())?
    } else {
        let sql = format!(
            "SELECT COUNT(*) FROM compounds WHERE project_id = ?1{}",
            filters_clause
        );
        db.query_row(&sql, rusqlite::params![project_id], |row| row.get(0))
            .map_err(|e| e.to_string())?
    };

    // Build and execute query — collect results immediately to avoid lifetime issues
    let compounds: Vec<Compound> = if has_search {
        let pattern = search_pattern.as_ref().unwrap();
        let query = format!(
            "SELECT id, project_id, name, smiles, mol_weight, logp, tpsa, hbd, hba, rotatable_bonds, created_at \
             FROM compounds WHERE project_id = ?1 AND (name LIKE ?2 OR smiles LIKE ?2){} \
             ORDER BY {} {} LIMIT ?3 OFFSET ?4",
            filters_clause, sort_column, sort_direction
        );
        let mut stmt = db.prepare(&query).map_err(|e| e.to_string())?;
        let rows = stmt.query_map(
            rusqlite::params![project_id, pattern, page_size, offset],
            row_to_compound,
        ).map_err(|e| e.to_string())?;
        rows.collect::<Result<Vec<_>, _>>().map_err(|e| e.to_string())?
    } else {
        let query = format!(
            "SELECT id, project_id, name, smiles, mol_weight, logp, tpsa, hbd, hba, rotatable_bonds, created_at \
             FROM compounds WHERE project_id = ?1{} \
             ORDER BY {} {} LIMIT ?2 OFFSET ?3",
            filters_clause, sort_column, sort_direction
        );
        let mut stmt = db.prepare(&query).map_err(|e| e.to_string())?;
        let rows = stmt.query_map(
            rusqlite::params![project_id, page_size, offset],
            row_to_compound,
        ).map_err(|e| e.to_string())?;
        rows.collect::<Result<Vec<_>, _>>().map_err(|e| e.to_string())?
    };

    Ok(CompoundPage {
        compounds,
        total,
        page,
        page_size,
    })
}

fn row_to_compound(row: &rusqlite::Row) -> rusqlite::Result<Compound> {
    Ok(Compound {
        id: row.get(0)?,
        project_id: row.get(1)?,
        name: row.get(2)?,
        smiles: row.get(3)?,
        mol_weight: row.get(4)?,
        logp: row.get(5)?,
        tpsa: row.get(6)?,
        hbd: row.get(7)?,
        hba: row.get(8)?,
        rotatable_bonds: row.get(9)?,
        created_at: row.get(10)?,
    })
}

#[tauri::command]
pub fn get_compound(state: State<'_, AppState>, compound_id: String) -> Result<Compound, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;

    db.query_row(
        "SELECT id, project_id, name, smiles, mol_weight, logp, tpsa, hbd, hba, rotatable_bonds, created_at \
         FROM compounds WHERE id = ?1",
        rusqlite::params![compound_id],
        row_to_compound,
    )
    .map_err(|e| e.to_string())
}

#[tauri::command]
pub fn add_compound(
    state: State<'_, AppState>,
    project_id: String,
    name: String,
    smiles: String,
) -> Result<Compound, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    let id = Uuid::new_v4().to_string();
    let now = Utc::now().to_rfc3339();

    db.execute(
        "INSERT INTO compounds (id, project_id, name, smiles, created_at) VALUES (?1, ?2, ?3, ?4, ?5)",
        rusqlite::params![id, project_id, name, smiles, now],
    )
    .map_err(|e| e.to_string())?;

    // Update project compound count
    db.execute(
        "UPDATE projects SET compound_count = (SELECT COUNT(*) FROM compounds WHERE project_id = ?1), updated_at = ?2 WHERE id = ?1",
        rusqlite::params![project_id, now],
    )
    .map_err(|e| e.to_string())?;

    Ok(Compound {
        id,
        project_id,
        name,
        smiles,
        mol_weight: None,
        logp: None,
        tpsa: None,
        hbd: None,
        hba: None,
        rotatable_bonds: None,
        created_at: now,
    })
}

#[tauri::command]
pub fn delete_compounds(
    state: State<'_, AppState>,
    project_id: String,
    compound_ids: Vec<String>,
) -> Result<i64, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;

    if compound_ids.is_empty() {
        return Ok(0);
    }

    let now = Utc::now().to_rfc3339();
    let mut deleted: i64 = 0;

    db.execute("BEGIN TRANSACTION", []).map_err(|e| e.to_string())?;

    for id in &compound_ids {
        // Delete referencing workflow results first to prevent foreign key constraint failure
        let _ = db.execute("DELETE FROM workflow_results WHERE compound_id = ?1", rusqlite::params![id]);

        let rows = db
            .execute("DELETE FROM compounds WHERE id = ?1", rusqlite::params![id])
            .map_err(|e| e.to_string())?;
        deleted += rows as i64;
    }

    // Update project compound count
    db.execute(
        "UPDATE projects SET compound_count = (SELECT COUNT(*) FROM compounds WHERE project_id = ?1), updated_at = ?2 WHERE id = ?1",
        rusqlite::params![project_id, now],
    )
    .map_err(|e| e.to_string())?;

    db.execute("COMMIT", []).map_err(|e| e.to_string())?;

    Ok(deleted)
}

/// Parse an SDF file using RDKit/Python and batch insert compounds into the project's library.
#[tauri::command]
pub async fn import_compounds_sdf(
    state: State<'_, AppState>,
    project_id: String,
    file_path: String,
) -> Result<i64, String> {
    let path = std::path::Path::new(&file_path);
    if !path.exists() {
        return Err(format!("File not found: {}", file_path));
    }

    let python_cmd = crate::python::find_python()?;

    let python_code = r#"
import sys
import json
from rdkit import Chem
from rdkit.Chem import Descriptors, Crippen

sdf_path = sys.argv[1]
supplier = Chem.SDMolSupplier(sdf_path)

results = []
if supplier is not None:
    for i, mol in enumerate(supplier):
        if mol is None:
            continue
        
        name = mol.GetProp("_Name") if mol.HasProp("_Name") else ""
        if not name or name.strip() == "":
            name = f"Compound-{i+1}"
            
        try:
            smiles = Chem.MolToSmiles(mol, canonical=True)
        except Exception:
            smiles = ""
            for tag in ["SMILES", "smiles", "SMI", "smi"]:
                if mol.HasProp(tag):
                    smiles = mol.GetProp(tag)
                    break
                    
        if not smiles:
            continue
            
        try:
            mw = float(Descriptors.MolWt(mol))
            logp = float(Crippen.MolLogP(mol))
            tpsa = float(Descriptors.TPSA(mol))
            hbd = int(Descriptors.NumHDonors(mol))
            hba = int(Descriptors.NumHAcceptors(mol))
            rot = int(Descriptors.NumRotatableBonds(mol))
        except Exception:
            mw = None
            logp = None
            tpsa = None
            hbd = None
            hba = None
            rot = None
            
        results.append({
            "name": name,
            "smiles": smiles,
            "mol_weight": mw,
            "logp": logp,
            "tpsa": tpsa,
            "hbd": hbd,
            "hba": hba,
            "rotatable_bonds": rot
        })

print(json.dumps(results))
"#;

    let output = std::process::Command::new(&python_cmd)
        .args(["-c", python_code, &file_path])
        .output()
        .map_err(|e| format!("Failed to spawn Python: {e}"))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("SDF parsing failed: {stderr}"));
    }

    let stdout_str = String::from_utf8(output.stdout)
        .map_err(|e| format!("Invalid UTF-8 in Python output: {e}"))?;

    let parsed_compounds: Vec<serde_json::Value> = serde_json::from_str(&stdout_str)
        .map_err(|e| format!("Failed to parse JSON from Python: {e}"))?;

    let now = Utc::now().to_rfc3339();
    let mut imported: i64 = 0;

    let db = state.db.lock().map_err(|e| e.to_string())?;
    db.execute("BEGIN TRANSACTION", []).map_err(|e| e.to_string())?;

    for cmp in parsed_compounds {
        let name = cmp.get("name").and_then(|v| v.as_str()).unwrap_or("Unnamed Compound");
        let smiles = match cmp.get("smiles").and_then(|v| v.as_str()) {
            Some(s) if !s.trim().is_empty() => s,
            _ => continue,
        };

        let mw = cmp.get("mol_weight").and_then(|v| v.as_f64());
        let logp = cmp.get("logp").and_then(|v| v.as_f64());
        let tpsa = cmp.get("tpsa").and_then(|v| v.as_f64());
        let hbd = cmp.get("hbd").and_then(|v| v.as_i64());
        let hba = cmp.get("hba").and_then(|v| v.as_i64());
        let rot = cmp.get("rotatable_bonds").and_then(|v| v.as_i64());

        let id = Uuid::new_v4().to_string();

        db.execute(
            "INSERT INTO compounds (id, project_id, name, smiles, mol_weight, logp, tpsa, hbd, hba, rotatable_bonds, created_at) \
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11)",
            rusqlite::params![
                id,
                project_id,
                name,
                smiles,
                mw,
                logp,
                tpsa,
                hbd,
                hba,
                rot,
                now
            ],
        )
        .map_err(|e| format!("Failed to insert compound '{}': {}", name, e))?;

        imported += 1;
    }

    // Update project compound count
    db.execute(
        "UPDATE projects SET compound_count = (SELECT COUNT(*) FROM compounds WHERE project_id = ?1), updated_at = ?2 WHERE id = ?1",
        rusqlite::params![project_id, now],
    )
    .map_err(|e| e.to_string())?;

    db.execute("COMMIT", []).map_err(|e| e.to_string())?;

    Ok(imported)
}

#[tauri::command]
pub fn replace_project_compounds(
    state: State<'_, AppState>,
    project_id: String,
    compounds: Vec<serde_json::Value>,
) -> Result<i64, String> {
    let mut db = state.db.lock().map_err(|e| e.to_string())?;
    let now = Utc::now().to_rfc3339();
    let mut imported: i64 = 0;

    // Use a transaction for atomic and fast deletion/insertion
    let tx = db.transaction().map_err(|e| e.to_string())?;

    // 1. Delete all workflow results referencing compounds in this project
    tx.execute(
        "DELETE FROM workflow_results WHERE compound_id IN (SELECT id FROM compounds WHERE project_id = ?1)",
        rusqlite::params![project_id],
    ).map_err(|e| format!("Failed to clear workflow results: {}", e))?;

    // 2. Delete all existing compounds in this project
    tx.execute(
        "DELETE FROM compounds WHERE project_id = ?1",
        rusqlite::params![project_id],
    ).map_err(|e| format!("Failed to clear compounds: {}", e))?;

    // 3. Insert the new compounds
    for cmp in compounds {
        let name = cmp.get("name").and_then(|v| v.as_str()).unwrap_or("Unnamed Compound");
        let smiles = match cmp.get("smiles").and_then(|v| v.as_str()) {
            Some(s) if !s.trim().is_empty() => s,
            _ => continue,
        };

        let id = Uuid::new_v4().to_string();

        tx.execute(
            "INSERT INTO compounds (id, project_id, name, smiles, created_at) VALUES (?1, ?2, ?3, ?4, ?5)",
            rusqlite::params![id, project_id, name, smiles, now],
        )
        .map_err(|e| format!("Failed to insert compound '{}': {}", name, e))?;

        imported += 1;
    }

    // 4. Update project compound count
    tx.execute(
        "UPDATE projects SET compound_count = ?1, updated_at = ?2 WHERE id = ?3",
        rusqlite::params![imported, now, project_id],
    )
    .map_err(|e| format!("Failed to update project compound count: {}", e))?;

    tx.commit().map_err(|e| e.to_string())?;

    Ok(imported)
}

