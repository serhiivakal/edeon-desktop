import sqlite3
from datetime import datetime

def get_first_launch_state(db_path: str) -> dict:
    """Check if the first-launch tour has been completed in settings."""
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        # Ensure table exists (precaution)
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)"
        )
        cursor.execute("SELECT value FROM settings WHERE key = 'first_launch_completed_at'")
        row = cursor.fetchone()
        if row is not None:
            return {"has_completed": True, "completed_at": row[0]}
        else:
            return {"has_completed": False, "completed_at": None}
    except Exception as e:
        return {"has_completed": False, "completed_at": None, "error": str(e)}
    finally:
        conn.close()

def mark_first_launch_complete(db_path: str) -> bool:
    """Mark first-launch tour completed in settings by writing current timestamp."""
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)"
        )
        now_str = datetime.utcnow().isoformat()
        cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('first_launch_completed_at', ?)",
            (now_str,)
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()
