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

        -- Saved Models (QSAR Custom Models)
        CREATE TABLE IF NOT EXISTS saved_models (
            id            TEXT PRIMARY KEY,
            name          TEXT NOT NULL,
            type          TEXT NOT NULL,
            algorithm     TEXT NOT NULL,
            features      TEXT NOT NULL,
            metrics       TEXT NOT NULL,
            importances   TEXT NOT NULL,
            created_at    TEXT NOT NULL
        );
        ",
    )?;

    // Create migrations table if not exists
    conn.execute(
        "CREATE TABLE IF NOT EXISTS migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        );",
        [],
    )?;

    let version: i32 = conn.query_row(
        "SELECT IFNULL(MAX(version), 0) FROM migrations",
        [],
        |row| row.get(0),
    ).unwrap_or(0);

    if version < 2 {
        let columns = [
            ("provenance", "TEXT DEFAULT '{}'"),
            ("curation_report", "TEXT DEFAULT '{}'"),
            ("cv_results", "TEXT DEFAULT '{}'"),
            ("y_scramble", "TEXT DEFAULT '{}'"),
        ];
        for (col_name, col_def) in columns {
            match conn.execute(&format!("ALTER TABLE saved_models ADD COLUMN {} {}", col_name, col_def), []) {
                Ok(_) => {},
                Err(e) => {
                    let msg = e.to_string();
                    if !msg.contains("duplicate column name") {
                        return Err(e);
                    }
                }
            }
        }
        conn.execute("INSERT OR REPLACE INTO migrations (version, applied_at) VALUES (2, datetime('now'))", [])?;
    }

    if version < 3 {
        match conn.execute("ALTER TABLE saved_models ADD COLUMN search_results TEXT DEFAULT '{}'", []) {
            Ok(_) => {},
            Err(e) => {
                let msg = e.to_string();
                if !msg.contains("duplicate column name") {
                    return Err(e);
                }
            }
        }

        conn.execute(
            "CREATE TABLE IF NOT EXISTS arena_runs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                shared TEXT NOT NULL,
                models TEXT NOT NULL,
                ranking TEXT NOT NULL,
                provenance TEXT NOT NULL,
                curation_report TEXT NOT NULL
            );",
            [],
        )?;

        conn.execute("INSERT OR REPLACE INTO migrations (version, applied_at) VALUES (3, datetime('now'))", [])?;
    }

    if version < 4 {
        let columns = [
            ("ad_reference", "BLOB"),
            ("shap_values", "BLOB"),
            ("diagnostics", "TEXT DEFAULT '{}'"),
            ("cliffs", "TEXT DEFAULT '{}'"),
            ("schema_version", "INTEGER NOT NULL DEFAULT 3"),
        ];
        for (col_name, col_def) in columns {
            match conn.execute(&format!("ALTER TABLE saved_models ADD COLUMN {} {}", col_name, col_def), []) {
                Ok(_) => {},
                Err(e) => {
                    let msg = e.to_string();
                    if !msg.contains("duplicate column name") {
                        return Err(e);
                    }
                }
            }
        }
        conn.execute("INSERT OR REPLACE INTO migrations (version, applied_at) VALUES (4, datetime('now'))", [])?;
    }

    if version < 5 {
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS model_cards (
                model_id TEXT PRIMARY KEY,
                endpoint TEXT NOT NULL,
                tier INTEGER NOT NULL,
                version TEXT NOT NULL,
                name TEXT NOT NULL,
                json_blob TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_model_cards_endpoint ON model_cards(endpoint);
            CREATE INDEX IF NOT EXISTS idx_model_cards_tier ON model_cards(tier);",
        )?;
        conn.execute("INSERT OR REPLACE INTO migrations (version, applied_at) VALUES (5, datetime('now'))", [])?;
    }

    if version < 6 {
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS model_tier_preferences (
                endpoint TEXT PRIMARY KEY,
                tier INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            );",
        )?;
        conn.execute("INSERT OR REPLACE INTO migrations (version, applied_at) VALUES (6, datetime('now'))", [])?;
    }

    if version < 7 {
        let columns = [
            ("deploy_target", "TEXT"),
            ("deployed_at", "TEXT"),
            ("deployment_status", "TEXT NOT NULL DEFAULT 'undeployed'"),
        ];
        for (col_name, col_def) in columns {
            match conn.execute(&format!("ALTER TABLE saved_models ADD COLUMN {} {}", col_name, col_def), []) {
                Ok(_) => {},
                Err(e) => {
                    let msg = e.to_string();
                    if !msg.contains("duplicate column name") {
                        return Err(e);
                    }
                }
            }
        }
        conn.execute("INSERT OR REPLACE INTO migrations (version, applied_at) VALUES (7, datetime('now'))", [])?;
    }

    if version < 8 {
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS docking_jobs (
                job_id TEXT PRIMARY KEY,
                receptor_id TEXT NOT NULL,
                receptor_display_name TEXT,
                ligand_smiles TEXT NOT NULL,
                ligand_display_name TEXT,
                box_center_x REAL, box_center_y REAL, box_center_z REAL,
                box_size_x REAL, box_size_y REAL, box_size_z REAL,
                top_score REAL,
                num_poses INTEGER,
                elapsed_seconds REAL,
                completed_at TEXT NOT NULL,
                starred INTEGER DEFAULT 0,
                job_spec_json TEXT NOT NULL,
                result_path TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_jobs_receptor ON docking_jobs(receptor_id);
            CREATE INDEX IF NOT EXISTS idx_jobs_completed ON docking_jobs(completed_at DESC);",
        )?;
        conn.execute("INSERT OR REPLACE INTO migrations (version, applied_at) VALUES (8, datetime('now'))", [])?;
    }

    if version < 9 {
        match conn.execute("ALTER TABLE workflow_results ADD COLUMN uq_json TEXT DEFAULT '{}'", []) {
            Ok(_) => {},
            Err(e) => {
                let msg = e.to_string();
                if !msg.contains("duplicate column name") {
                    return Err(e);
                }
            }
        }
        conn.execute("INSERT OR REPLACE INTO migrations (version, applied_at) VALUES (9, datetime('now'))", [])?;
    }

    if version < 10 {
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS transformation_products (
                id             TEXT PRIMARY KEY,
                compound_id    TEXT NOT NULL REFERENCES compounds(id) ON DELETE CASCADE,
                parent_tp_id   TEXT,
                smiles         TEXT NOT NULL,
                route          TEXT,
                rule           TEXT,
                probability    REAL,
                fate_json      TEXT,
                tox_json       TEXT,
                risk_flag      INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_tp_compound ON transformation_products(compound_id);",
        )?;
        conn.execute("INSERT OR REPLACE INTO migrations (version, applied_at) VALUES (10, datetime('now'))", [])?;
    }

    if version < 11 {
        let columns = [
            ("workflow_id", "TEXT"),
            ("params_json", "TEXT"),
            ("verdict_json", "TEXT"),
            ("provenance_json", "TEXT"),
        ];
        for (col_name, col_def) in columns {
            match conn.execute(&format!("ALTER TABLE workflows ADD COLUMN {} {}", col_name, col_def), []) {
                Ok(_) => {},
                Err(e) => {
                    let msg = e.to_string();
                    if !msg.contains("duplicate column name") {
                        return Err(e);
                    }
                }
            }
        }
        conn.execute("INSERT OR REPLACE INTO migrations (version, applied_at) VALUES (11, datetime('now'))", [])?;
    }

    if version < 12 {
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS knowledge_conversations (
                conversation_id TEXT PRIMARY KEY,
                user_id TEXT,
                title TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                starred INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS knowledge_messages (
                message_id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL REFERENCES knowledge_conversations(conversation_id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                citations_json TEXT,
                retrieved_sources_json TEXT,
                tokens_used_json TEXT,
                timestamp TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_messages_conversation ON knowledge_messages(conversation_id);",
        )?;
        conn.execute("INSERT OR REPLACE INTO migrations (version, applied_at) VALUES (12, datetime('now'))", [])?;
    }

    if version < 13 {
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS generation_jobs (
                job_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                mode TEXT NOT NULL,
                parent_smiles TEXT,
                receptor_id TEXT,
                receptor_display_name TEXT,
                parameters_json TEXT NOT NULL,
                results_json TEXT NOT NULL,
                total_generated INTEGER,
                total_docked INTEGER,
                elapsed_seconds REAL,
                completed_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_gen_jobs_completed ON generation_jobs(completed_at DESC);",
        )?;
        conn.execute("INSERT OR REPLACE INTO migrations (version, applied_at) VALUES (13, datetime('now'))", [])?;
    }

    if version < 14 {
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS decision_journal (
                entry_id      TEXT PRIMARY KEY,
                project_id    TEXT NOT NULL,
                created_at    TEXT NOT NULL DEFAULT (datetime('now')),
                actor         TEXT NOT NULL CHECK (actor IN ('system','user')),
                decision_kind TEXT NOT NULL,
                subject_type  TEXT NOT NULL,
                subject_id    TEXT NOT NULL,
                summary       TEXT NOT NULL,
                rationale_json     TEXT,
                alternatives_json  TEXT,
                confidence_json    TEXT,
                provenance_json    TEXT NOT NULL,
                override_of   TEXT REFERENCES decision_journal(entry_id),
                supersedes_id TEXT REFERENCES decision_journal(entry_id),
                user_note     TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_journal_project_time  ON decision_journal(project_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_journal_subject       ON decision_journal(subject_type, subject_id);
            CREATE INDEX IF NOT EXISTS idx_journal_kind          ON decision_journal(project_id, decision_kind);
            CREATE INDEX IF NOT EXISTS idx_journal_override      ON decision_journal(override_of);",
        )?;
        conn.execute("INSERT OR REPLACE INTO migrations (version, applied_at) VALUES (14, datetime('now'))", [])?;
    }

    if version < 15 {
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS bottleneck_analyses (
                analysis_id   TEXT PRIMARY KEY,
                project_id    TEXT NOT NULL,
                workflow_id   TEXT,
                profile       TEXT NOT NULL,
                n_compounds   INTEGER NOT NULL,
                top_endpoint  TEXT,
                top_kind      TEXT,
                ambiguous     INTEGER NOT NULL DEFAULT 0,
                payload_json  TEXT NOT NULL,
                params_hash   TEXT NOT NULL,
                created_at    TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_bottleneck_project ON bottleneck_analyses(project_id, created_at DESC);",
        )?;
        conn.execute("INSERT OR REPLACE INTO migrations (version, applied_at) VALUES (15, datetime('now'))", [])?;
    }

    if version < 16 {
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS speciation_cache (
                input_inchikey TEXT NOT NULL,
                ph_target      REAL NOT NULL,
                payload_json   TEXT NOT NULL,
                created_at     TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (input_inchikey, ph_target)
            );",
        )?;
        conn.execute("INSERT OR REPLACE INTO migrations (version, applied_at) VALUES (16, datetime('now'))", [])?;
    }

    if version < 17 {
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS mobility_predictions (
                inchikey       TEXT PRIMARY KEY,
                class          TEXT NOT NULL,
                phloem_cf      REAL NOT NULL,
                xylem_index    REAL NOT NULL,
                phloem_index   REAL NOT NULL,
                confidence     TEXT NOT NULL,
                payload_json   TEXT NOT NULL,
                created_at     TEXT NOT NULL DEFAULT (datetime('now'))
            );",
        )?;
        conn.execute("INSERT OR REPLACE INTO migrations (version, applied_at) VALUES (17, datetime('now'))", [])?;
    }

    if version < 18 {
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS retro_routes (
                inchikey       TEXT NOT NULL,
                stock_id       TEXT NOT NULL,
                params_hash    TEXT NOT NULL,
                solved         INTEGER NOT NULL,
                feasibility    REAL,
                tier           TEXT,
                route_json     TEXT NOT NULL,
                created_at     TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (inchikey, stock_id, params_hash)
            );
            CREATE TABLE IF NOT EXISTS retro_stocks (
                stock_id TEXT PRIMARY KEY,
                name     TEXT NOT NULL,
                n_blocks INTEGER NOT NULL,
                path     TEXT NOT NULL
            );",
        )?;
        conn.execute("INSERT OR REPLACE INTO migrations (version, applied_at) VALUES (18, datetime('now'))", [])?;
    }

    if version < 19 {
        let _ = conn.execute("ALTER TABLE generation_jobs ADD COLUMN job_kind TEXT DEFAULT 'crem'", []);
        conn.execute("INSERT OR REPLACE INTO migrations (version, applied_at) VALUES (19, datetime('now'))", [])?;
    }

    if version < 20 {
        let _ = conn.execute("ALTER TABLE transformation_products ADD COLUMN source TEXT DEFAULT 'sygma'", []);
        let _ = conn.execute("ALTER TABLE transformation_products ADD COLUMN liability_flag INTEGER DEFAULT 0", []);
        conn.execute("INSERT OR REPLACE INTO migrations (version, applied_at) VALUES (20, datetime('now'))", [])?;
    }

    if version < 21 {
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS mmp_transforms (
                transform_id   TEXT PRIMARY KEY,
                transform      TEXT NOT NULL,
                r1             TEXT NOT NULL,
                r2             TEXT NOT NULL,
                count          INTEGER NOT NULL,
                mean_delta_sel REAL NOT NULL,
                created_at     TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS free_wilson_models (
                model_id    TEXT PRIMARY KEY,
                endpoint    TEXT NOT NULL,
                core_smiles TEXT NOT NULL,
                r2_score    REAL NOT NULL,
                model_json  TEXT NOT NULL,
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );",
        )?;
        conn.execute("INSERT OR REPLACE INTO migrations (version, applied_at) VALUES (21, datetime('now'))", [])?;
    }

    if version < 22 {
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS tmap_layouts (
                layout_id    TEXT PRIMARY KEY,
                project_id   TEXT NOT NULL,
                method       TEXT NOT NULL,
                n_compounds  INTEGER NOT NULL,
                nodes_json   TEXT NOT NULL,
                edges_json   TEXT NOT NULL,
                created_at   TEXT NOT NULL DEFAULT (datetime('now'))
            );",
        )?;
        conn.execute("INSERT OR REPLACE INTO migrations (version, applied_at) VALUES (22, datetime('now'))", [])?;
    }

    if version < 23 {
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS shape_screenings (
                screening_id TEXT PRIMARY KEY,
                ref_smiles    TEXT NOT NULL,
                n_candidates  INTEGER NOT NULL,
                results_json  TEXT NOT NULL,
                created_at    TEXT NOT NULL DEFAULT (datetime('now'))
            );",
        )?;
        conn.execute("INSERT OR REPLACE INTO migrations (version, applied_at) VALUES (23, datetime('now'))", [])?;
    }

    if version < 24 {
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS active_learning_campaigns (
                campaign_id  TEXT PRIMARY KEY,
                acquisition  TEXT NOT NULL,
                batch_size   INTEGER NOT NULL,
                r2_score     REAL NOT NULL,
                batch_json   TEXT NOT NULL,
                created_at   TEXT NOT NULL DEFAULT (datetime('now'))
            );",
        )?;
        conn.execute("INSERT OR REPLACE INTO migrations (version, applied_at) VALUES (24, datetime('now'))", [])?;
    }

    Ok(())
}
