use rusqlite::{Connection, Result as SqlResult, OptionalExtension};
use chrono::Utc;
use std::collections::HashMap;

/// Set the preferred model tier for a given endpoint.
pub fn set_preference(conn: &Connection, endpoint: &str, tier: u8) -> SqlResult<()> {
    if tier == 0 {
        clear_preference(conn, endpoint)?;
        return Ok(());
    }
    let now = Utc::now().to_rfc3339();
    conn.execute(
        "INSERT OR REPLACE INTO model_tier_preferences (endpoint, tier, updated_at) VALUES (?1, ?2, ?3)",
        rusqlite::params![endpoint, tier, now],
    )?;
    Ok(())
}

/// Retrieve the preferred model tier for a given endpoint.
pub fn get_preference(conn: &Connection, endpoint: &str) -> SqlResult<Option<u8>> {
    conn.query_row(
        "SELECT tier FROM model_tier_preferences WHERE endpoint = ?1",
        rusqlite::params![endpoint],
        |row| row.get::<_, u8>(0),
    )
    .optional()
}

/// Clear the preferred model tier for a given endpoint.
pub fn clear_preference(conn: &Connection, endpoint: &str) -> SqlResult<bool> {
    let rows_affected = conn.execute(
        "DELETE FROM model_tier_preferences WHERE endpoint = ?1",
        rusqlite::params![endpoint],
    )?;
    Ok(rows_affected > 0)
}

/// Retrieve all endpoint tier preferences as a HashMap.
#[allow(dead_code)]
pub fn get_all_preferences(conn: &Connection) -> SqlResult<HashMap<String, u8>> {
    let mut stmt = conn.prepare("SELECT endpoint, tier FROM model_tier_preferences")?;
    let rows = stmt.query_map([], |row| {
        Ok((row.get::<_, String>(0)?, row.get::<_, u8>(1)?))
    })?;
    
    let mut prefs = HashMap::new();
    for row in rows {
        let (endpoint, tier) = row?;
        prefs.insert(endpoint, tier);
    }
    Ok(prefs)
}
