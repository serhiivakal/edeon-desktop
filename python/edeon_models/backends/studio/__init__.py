import sqlite3
from datetime import datetime
from edeon_models.endpoints import Endpoint, endpoint_metadata
from edeon_models.card import save_card, delete_card
from .studio_backend import StudioBackend

__all__ = ["StudioBackend", "deploy_studio_model", "undeploy_studio_model"]


def deploy_studio_model(saved_model_id: str, endpoint: Endpoint, registry, db_path: str):
    """Deploy a QSAR Studio model as a T4 backend for the given endpoint.

    Steps:
    1. Load saved model from QSAR Studio storage.
    2. Validate model output type matches endpoint expectation.
    3. Construct StudioBackend.
    4. Register in registry (replaces any prior T4 for the endpoint).
    5. Save ModelCard to SQLite.
    6. Update saved_models table: deploy_target, deployed_at, deployment_status='deployed'.
    7. Return the ModelCard.
    """
    resolved_endpoint = Endpoint(endpoint)

    # 1. Load saved model type from SQLite
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT type FROM saved_models WHERE id = ?", (saved_model_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Saved model '{saved_model_id}' not found in database.")
    model_type = row[0]

    # 2. Validate model output type matches endpoint expectation
    meta = endpoint_metadata(resolved_endpoint)
    is_category_endpoint = meta.get("units") == "category"
    is_classification_model = model_type == "classification"

    if is_category_endpoint != is_classification_model:
        conn.close()
        raise ValueError(
            f"Model type '{model_type}' is incompatible with endpoint "
            f"'{resolved_endpoint.value}' which expects units of '{meta.get('units')}'."
        )

    # 3. Construct StudioBackend
    backend = StudioBackend(saved_model_id, db_path, resolved_endpoint)

    # 4. Register in registry (overwrites existing T4 for this endpoint)
    registry.register(backend)

    # 5. Save ModelCard to SQLite
    card = backend.metadata()
    save_card(card, db_path=db_path)

    # 6. Update saved_models table
    now_str = datetime.utcnow().isoformat()
    cur.execute(
        "UPDATE saved_models SET deploy_target = ?, deployed_at = ?, deployment_status = 'deployed' WHERE id = ?",
        (resolved_endpoint.value, now_str, saved_model_id)
    )
    conn.commit()
    conn.close()

    # 7. Return the ModelCard
    return card


def undeploy_studio_model(saved_model_id: str, registry, db_path: str) -> None:
    """Reverse the deploy: remove from registry, update saved_models status."""
    # 1. Fetch current deploy target from saved_models
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT deploy_target FROM saved_models WHERE id = ?", (saved_model_id,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return

    deploy_target = row[0]

    # 2. Update saved_models table to undeployed status
    cur.execute(
        "UPDATE saved_models SET deploy_target = NULL, deployed_at = NULL, deployment_status = 'undeployed' WHERE id = ?",
        (saved_model_id,)
    )
    conn.commit()
    conn.close()

    # 3. Remove from registry and delete active model card
    if deploy_target:
        endpoint = Endpoint(deploy_target)
        if endpoint in registry._backends:
            if 4 in registry._backends[endpoint]:
                del registry._backends[endpoint][4]
            if not registry._backends[endpoint]:
                del registry._backends[endpoint]

        # Delete active ModelCard from DB
        card_id = f"{endpoint.value}.t4.studio-{saved_model_id}"
        delete_card(card_id, db_path=db_path)
