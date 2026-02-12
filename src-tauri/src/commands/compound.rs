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

#[tauri::command]
pub fn list_compounds(
    state: State<'_, AppState>,
    project_id: String,
    page: Option<i64>,
    page_size: Option<i64>,
    sort_by: Option<String>,
    sort_dir: Option<String>,
    search: Option<String>,
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

    // Count total matching
    let total: i64 = if let Some(ref pattern) = search_pattern {
        db.query_row(
            "SELECT COUNT(*) FROM compounds WHERE project_id = ?1 AND (name LIKE ?2 OR smiles LIKE ?2)",
            rusqlite::params![project_id, pattern],
            |row| row.get(0),
        )
        .map_err(|e| e.to_string())?
    } else {
        db.query_row(
            "SELECT COUNT(*) FROM compounds WHERE project_id = ?1",
            rusqlite::params![project_id],
            |row| row.get(0),
        )
        .map_err(|e| e.to_string())?
    };

    // Build and execute query — collect results immediately to avoid lifetime issues
    let compounds: Vec<Compound> = if has_search {
        let pattern = search_pattern.as_ref().unwrap();
        let query = format!(
            "SELECT id, project_id, name, smiles, mol_weight, logp, tpsa, hbd, hba, rotatable_bonds, created_at \
             FROM compounds WHERE project_id = ?1 AND (name LIKE ?2 OR smiles LIKE ?2) \
             ORDER BY {} {} LIMIT ?3 OFFSET ?4",
            sort_column, sort_direction
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
             FROM compounds WHERE project_id = ?1 \
             ORDER BY {} {} LIMIT ?2 OFFSET ?3",
            sort_column, sort_direction
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
