import os
import json
import sqlite3
import yaml
from datetime import datetime
from typing import Optional

from .types import ModelCard
from .endpoints import Endpoint

DEFAULT_DB_PATH = os.path.expanduser("~/.local/share/com.edeon.desktop/edeon.db")

def _init_table(cursor: sqlite3.Cursor) -> None:
    """Ensure the model_cards table and its indexes exist."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS model_cards (
            model_id TEXT PRIMARY KEY,
            endpoint TEXT NOT NULL,
            tier INTEGER NOT NULL,
            version TEXT NOT NULL,
            name TEXT NOT NULL,
            json_blob TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_model_cards_endpoint ON model_cards(endpoint);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_model_cards_tier ON model_cards(tier);")

def save_card(card: ModelCard, db_path: str = DEFAULT_DB_PATH) -> None:
    """Save a ModelCard to the SQLite database. Inserts or replaces existing.
    
    Args:
        card: The ModelCard instance to save.
        db_path: Path to the SQLite database file.
    """
    # Ensure directory exists for the database file
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        _init_table(cursor)
        
        now_str = datetime.utcnow().isoformat()
        
        # Check if the card already exists to preserve created_at
        cursor.execute("SELECT created_at FROM model_cards WHERE model_id = ?", (card.model_id,))
        row = cursor.fetchone()
        if row is not None:
            created_at = row[0]
        else:
            created_at = now_str
            
        updated_at = now_str
        
        cursor.execute(
            """
            INSERT OR REPLACE INTO model_cards (
                model_id, endpoint, tier, version, name, json_blob, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                card.model_id,
                card.endpoint,
                int(card.tier),
                card.version,
                card.name,
                json.dumps(card.model_dump(mode='json')),
                created_at,
                updated_at
            )
        )
        conn.commit()
    finally:
        conn.close()

def load_card(model_id: str, db_path: str = DEFAULT_DB_PATH) -> Optional[ModelCard]:
    """Load a ModelCard from the SQLite database by model_id.
    
    Args:
        model_id: The unique identifier of the model.
        db_path: Path to the SQLite database file.
        
    Returns:
        The deserialized ModelCard instance, or None if not found.
    """
    if not os.path.exists(db_path):
        return None
        
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        # In case the table hasn't been created yet
        _init_table(cursor)
        
        cursor.execute("SELECT json_blob FROM model_cards WHERE model_id = ?", (model_id,))
        row = cursor.fetchone()
        if row is None:
            return None
            
        return ModelCard.model_validate(json.loads(row[0]))
    finally:
        conn.close()

def list_cards(endpoint: Optional[Endpoint] = None, db_path: str = DEFAULT_DB_PATH) -> list[ModelCard]:
    """List ModelCards from the SQLite database, optionally filtered by endpoint.
    
    Args:
        endpoint: Optional Endpoint to filter the model cards.
        db_path: Path to the SQLite database file.
        
    Returns:
        List of loaded ModelCard instances.
    """
    if not os.path.exists(db_path):
        return []
        
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        _init_table(cursor)
        
        if endpoint is not None:
            # Handle both Endpoint enum and standard string values
            ep_val = endpoint.value if hasattr(endpoint, "value") else str(endpoint)
            cursor.execute("SELECT json_blob FROM model_cards WHERE endpoint = ?", (ep_val,))
        else:
            cursor.execute("SELECT json_blob FROM model_cards")
            
        rows = cursor.fetchall()
        return [ModelCard.model_validate(json.loads(row[0])) for row in rows]
    finally:
        conn.close()

def delete_card(model_id: str, db_path: str = DEFAULT_DB_PATH) -> bool:
    """Delete a ModelCard from the SQLite database.
    
    Args:
        model_id: The unique identifier of the model to delete.
        db_path: Path to the SQLite database file.
        
    Returns:
        True if the card was found and deleted, False otherwise.
    """
    if not os.path.exists(db_path):
        return False
        
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        _init_table(cursor)
        
        cursor.execute("SELECT 1 FROM model_cards WHERE model_id = ?", (model_id,))
        exists = cursor.fetchone() is not None
        
        if exists:
            cursor.execute("DELETE FROM model_cards WHERE model_id = ?", (model_id,))
            conn.commit()
            
        return exists
    finally:
        conn.close()

def card_to_yaml(card: ModelCard) -> str:
    """Serialize a ModelCard instance to a human-readable YAML string.
    
    Args:
        card: The ModelCard instance to serialize.
        
    Returns:
        A human-readable YAML string.
    """
    card_dict = card.model_dump(mode='json')
    return yaml.dump(card_dict, default_flow_style=False, sort_keys=False)

def card_from_yaml(yaml_str: str) -> ModelCard:
    """Deserialize a ModelCard instance from a YAML string.
    
    Args:
        yaml_str: The YAML string to deserialize.
        
    Returns:
        The validated ModelCard instance.
    """
    card_dict = yaml.safe_load(yaml_str)
    if not card_dict:
        raise ValueError("Invalid or empty YAML string.")
    return ModelCard.model_validate(card_dict)
