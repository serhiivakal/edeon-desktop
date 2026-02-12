import sqlite3
import json
import os
from pathlib import Path
from typing import List, Optional
from .schema import TransformationRule
from .library_builder import MANUAL_RULES, acquire_swissbioisostere, acquire_mmpdb_rules

DEFAULT_DB_PATH = Path("data/bioisostere/v1.0/bioisostere.db")

def build_database(db_path: Path = DEFAULT_DB_PATH):
    """Builds the SQLite database for bioisostere transformations."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("DROP TABLE IF EXISTS transformations")
    cursor.execute("""
        CREATE TABLE transformations (
            rule_id TEXT PRIMARY KEY,
            pattern_smarts TEXT NOT NULL,
            replacement_smarts TEXT NOT NULL,
            reaction_smarts TEXT NOT NULL,
            source TEXT NOT NULL,
            source_reference TEXT,
            context TEXT,
            occurrence_frequency INTEGER NOT NULL,
            occurrence_in_marketed_drugs INTEGER,
            direction_notes TEXT,
            synthetic_complexity_delta REAL,
            json_blob TEXT NOT NULL
        )
    """)
    
    cursor.execute("CREATE INDEX idx_source ON transformations(source)")
    cursor.execute("CREATE INDEX idx_occurrence ON transformations(occurrence_frequency DESC)")
    
    # Collect all rules
    all_rules = []
    
    # 1. Manual rules
    for r in MANUAL_RULES:
        all_rules.append(TransformationRule.model_validate(r))
        
    # 2. SwissBioisostere rules
    for r in acquire_swissbioisostere(str(db_path.parent)):
        all_rules.append(TransformationRule.model_validate(r))
        
    # 3. mmpdb rules
    for r in acquire_mmpdb_rules():
        all_rules.append(TransformationRule.model_validate(r))
        
    # Insert rules into SQLite
    for rule in all_rules:
        cursor.execute("""
            INSERT INTO transformations (
                rule_id, pattern_smarts, replacement_smarts, reaction_smarts,
                source, source_reference, context, occurrence_frequency,
                occurrence_in_marketed_drugs, direction_notes, synthetic_complexity_delta,
                json_blob
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            rule.rule_id,
            rule.pattern_smarts,
            rule.replacement_smarts,
            rule.reaction_smarts,
            rule.source,
            rule.source_reference,
            rule.context,
            rule.occurrence_frequency,
            rule.occurrence_in_marketed_drugs,
            rule.direction_notes,
            rule.synthetic_complexity_delta,
            rule.model_dump_json()
        ))
        
    conn.commit()
    
    # Write manifest.json
    manifest = {
        "version": "1.0",
        "build_date": "2026-06-02",
        "rule_counts": {
            "manual_curation": len(MANUAL_RULES),
            "swissbioisostere": len(acquire_swissbioisostere(str(db_path.parent))),
            "mmpdb_chembl_approved": len(acquire_mmpdb_rules()),
            "total": len(all_rules)
        }
    }
    with open(db_path.parent / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
        
    conn.close()

def load_rules(db_path: Path = DEFAULT_DB_PATH, source_filter: Optional[str] = None, min_occurrences: int = 1) -> List[TransformationRule]:
    """Loads transformation rules from the SQLite database."""
    if not db_path.exists():
        build_database(db_path)
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    query = "SELECT json_blob FROM transformations WHERE occurrence_frequency >= ?"
    params = [min_occurrences]
    
    if source_filter:
        query += " AND source = ?"
        params.append(source_filter)
        
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [TransformationRule.model_validate_json(row[0]) for row in rows]
