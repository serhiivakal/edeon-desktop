import os
import sqlite3
from typing import Any, Optional, Dict
from edeon_models import build_default_registry, Endpoint
from edeon_models.card import DEFAULT_DB_PATH

# Singleton BackendRegistry built at startup
REGISTRY = build_default_registry(DEFAULT_DB_PATH)

# Initialize Experimental Value Overlay Index & Service once on startup
from edeon_models.overlay.lookup import ExperimentalValueIndex
from edeon_models.overlay.service import OverlayService

OVERLAY_INDEX = ExperimentalValueIndex.build()
OVERLAY_SERVICE = OverlayService(OVERLAY_INDEX)

def _init_pref_table(conn: sqlite3.Connection):
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS model_tier_preferences (
            endpoint TEXT PRIMARY KEY,
            tier INTEGER NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()

def set_db_preference(endpoint: str, tier: int, db_path: Optional[str] = None) -> None:
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        _init_pref_table(conn)
        cursor = conn.cursor()
        from datetime import datetime
        now_str = datetime.utcnow().isoformat()
        cursor.execute(
            "INSERT OR REPLACE INTO model_tier_preferences (endpoint, tier, updated_at) VALUES (?, ?, ?)",
            (endpoint, tier, now_str)
        )
        conn.commit()
    finally:
        conn.close()

def get_db_preference(endpoint: str, db_path: Optional[str] = None) -> Optional[int]:
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    if not os.path.exists(db_path):
        return None
    conn = sqlite3.connect(db_path)
    try:
        _init_pref_table(conn)
        cursor = conn.cursor()
        cursor.execute("SELECT tier FROM model_tier_preferences WHERE endpoint = ?", (endpoint,))
        row = cursor.fetchone()
        return row[0] if row is not None else None
    finally:
        conn.close()

def execute_command(command: str, args: Dict[str, Any], db_path: Optional[str] = None) -> Any:
    """Execute a single engine command by mapping it to registry actions."""
    if db_path is None:
        db_path = DEFAULT_DB_PATH
        
    if command == "predict":
        endpoint_str = args.get("endpoint")
        smiles = args.get("smiles", [])
        preferred_tier = args.get("preferred_tier")
        
        # preference-aware resolution if not supplied
        if preferred_tier is None:
            preferred_tier = get_db_preference(endpoint_str, db_path=db_path)
            
        endpoint = Endpoint(endpoint_str)
        
        # Get backend from registry with the correct preferred_tier argument name
        backend = REGISTRY.get(endpoint, preferred_tier=preferred_tier)
        if backend is None:
            raise ValueError(f"No backend registered for endpoint '{endpoint_str}' with tier {preferred_tier}")
            
        predictions = backend.predict(smiles)
        enriched_predictions = OVERLAY_SERVICE.enrich(predictions)
        return [pred.model_dump(mode='json') for pred in enriched_predictions]
        
    elif command == "list_for_endpoint" or command == "list_backends":
        endpoint_str = args.get("endpoint")
        endpoint = Endpoint(endpoint_str)
        backends = REGISTRY.list_for_endpoint(endpoint)
        return [b.metadata().model_dump(mode='json') for b in backends]
        
    elif command == "get_card":
        model_id = args.get("model_id")
        
        # Search registry._backends manually by matching metadata model_id
        backend = None
        for tier_dict in REGISTRY._backends.values():
            for b in tier_dict.values():
                if b.metadata().model_id == model_id:
                    backend = b
                    break
            if backend is not None:
                break
                
        if backend is None:
            raise ValueError(f"Model '{model_id}' not found in registry")
        return backend.metadata().model_dump(mode='json')
        
    elif command == "set_preference":
        endpoint_str = args.get("endpoint")
        tier = args.get("tier")
        set_db_preference(endpoint_str, int(tier), db_path=db_path)
        return True
        
    elif command == "get_preference":
        endpoint_str = args.get("endpoint")
        return get_db_preference(endpoint_str, db_path=db_path)
        
    elif command == "list_endpoints":
        return [ep.value for ep in Endpoint]
        
    elif command == "deploy_studio_model":
        saved_model_id = args.get("saved_model_id")
        endpoint_str = args.get("endpoint")
        endpoint = Endpoint(endpoint_str)
        
        from edeon_models import deploy_studio_model
        card = deploy_studio_model(
            saved_model_id=saved_model_id,
            endpoint=endpoint,
            registry=REGISTRY,
            db_path=db_path
        )
        return card.model_dump(mode='json')
        
    elif command == "undeploy_studio_model":
        saved_model_id = args.get("saved_model_id")
        
        from edeon_models import undeploy_studio_model
        undeploy_studio_model(
            saved_model_id=saved_model_id,
            registry=REGISTRY,
            db_path=db_path
        )
        return True
        
    elif command == "get_calibration_diagnostics":
        model_id = args.get("model_id")
        from edeon_models.diagnostics import get_calibration_diagnostics
        return get_calibration_diagnostics(model_id=model_id, db_path=db_path)
        
    else:
        raise ValueError(f"Unknown command: '{command}'")
