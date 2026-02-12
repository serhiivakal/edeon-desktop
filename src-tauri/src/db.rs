/// Edeon Desktop — Database Module
///
/// Initializes SQLite database and runs schema creation.
/// Uses WAL journal mode for better concurrent read performance.

use rusqlite::{Connection, Result as SqlResult};
use std::path::Path;

/// Open (or create) the database file at `db_path` and ensure all tables exist.
pub fn init_db(db_path: &Path) -> SqlResult<Connection> {
    let conn = Connection::open(db_path)?;

    // Enable WAL mode for better performance with concurrent reads
    conn.execute_batch("PRAGMA journal_mode=WAL;")?;
    conn.execute_batch("PRAGMA foreign_keys=ON;")?;

    create_tables(&conn)?;

    Ok(conn)
}

fn create_tables(conn: &Connection) -> SqlResult<()> {
    conn.execute_batch(
        "
        -- Projects
        CREATE TABLE IF NOT EXISTS projects (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL,
            compound_count INTEGER DEFAULT 0
        );

        -- Compounds
        CREATE TABLE IF NOT EXISTS compounds (
            id              TEXT PRIMARY KEY,
            project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            name            TEXT NOT NULL,
            smiles          TEXT NOT NULL,
            mol_weight      REAL,
            logp            REAL,
            tpsa            REAL,
            hbd             INTEGER,
            hba             INTEGER,
            rotatable_bonds INTEGER,
            properties_json TEXT,
            created_at      TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_compounds_project
            ON compounds(project_id);

        -- Workflows (schema ready for Phase 3)
        CREATE TABLE IF NOT EXISTS workflows (
            id              TEXT PRIMARY KEY,
            project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            name            TEXT NOT NULL,
            template        TEXT,
            status          TEXT DEFAULT 'pending',
            config_json     TEXT,
            started_at      TEXT,
            completed_at    TEXT
        );

        -- Workflow Results (schema ready for Phase 3)
        CREATE TABLE IF NOT EXISTS workflow_results (
            id              TEXT PRIMARY KEY,
            workflow_id     TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
            compound_id     TEXT NOT NULL REFERENCES compounds(id),
            stage           TEXT NOT NULL,
            results_json    TEXT,
            score           REAL
        );

        -- Settings key-value store (active project, preferences, etc.)
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
        ",
    )?;

    Ok(())
}
