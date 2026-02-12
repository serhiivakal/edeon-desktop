import os
import sqlite3
import uuid
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

def _get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def create_conversation(db_path: str, title: str) -> str:
    """Create a new chat conversation session in the DB."""
    conn = _get_connection(db_path)
    conversation_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO knowledge_conversations (conversation_id, user_id, title, created_at, updated_at, starred)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            (conversation_id, "default_user", title, now, now)
        )
        conn.commit()
    finally:
        conn.close()
    return conversation_id

def list_conversations(db_path: str) -> List[Dict[str, Any]]:
    """Retrieve all conversations from Edeon db sorted by updated_at desc."""
    if not os.path.exists(db_path):
        return []
    conn = _get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT conversation_id, title, created_at, updated_at, starred FROM knowledge_conversations ORDER BY updated_at DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def load_conversation(db_path: str, conversation_id: str) -> Dict[str, Any]:
    """Retrieve conversation details and its complete message log list."""
    if not os.path.exists(db_path):
        return {}
    conn = _get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT conversation_id, title, created_at, updated_at, starred FROM knowledge_conversations WHERE conversation_id = ?",
            (conversation_id,)
        )
        conv_row = cursor.fetchone()
        if not conv_row:
            return {}
            
        cursor.execute(
            """
            SELECT message_id, role, content, citations_json, retrieved_sources_json, tokens_used_json, timestamp 
            FROM knowledge_messages 
            WHERE conversation_id = ? 
            ORDER BY timestamp ASC
            """,
            (conversation_id,)
        )
        message_rows = cursor.fetchall()
        
        messages = []
        for msg in message_rows:
            d = dict(msg)
            d["citations"] = json.loads(d.pop("citations_json") or "[]")
            d["retrieved_sources"] = json.loads(d.pop("retrieved_sources_json") or "[]")
            d["tokens_used"] = json.loads(d.pop("tokens_used_json") or "{}")
            messages.append(d)
            
        conv = dict(conv_row)
        conv["messages"] = messages
        return conv
    finally:
        conn.close()

def star_conversation(db_path: str, conversation_id: str, starred: bool) -> bool:
    """Toggles starred status on a conversation."""
    conn = _get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE knowledge_conversations SET starred = ?, updated_at = ? WHERE conversation_id = ?",
            (1 if starred else 0, datetime.utcnow().isoformat(), conversation_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()

def delete_conversation(db_path: str, conversation_id: str) -> bool:
    """Delete a conversation. CASCADE constraint deletes linked messages."""
    conn = _get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM knowledge_conversations WHERE conversation_id = ?", (conversation_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()

def save_message(db_path: str, conversation_id: str, role: str, content: str,
                 citations: List[Dict[str, Any]] = None,
                 retrieved_sources: List[Dict[str, Any]] = None,
                 tokens_used: Dict[str, int] = None) -> str:
    """Writes a message (user or assistant) to SQLite and updates conversation timestamp."""
    conn = _get_connection(db_path)
    message_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO knowledge_messages (
                message_id, conversation_id, role, content, citations_json, retrieved_sources_json, tokens_used_json, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                conversation_id,
                role,
                content,
                json.dumps(citations or []),
                json.dumps(retrieved_sources or []),
                json.dumps(tokens_used or {}),
                now
            )
        )
        # Update parent conversation timestamp
        cursor.execute(
            "UPDATE knowledge_conversations SET updated_at = ? WHERE conversation_id = ?",
            (now, conversation_id)
        )
        conn.commit()
    finally:
        conn.close()
    return message_id
