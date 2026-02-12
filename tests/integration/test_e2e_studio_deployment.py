import subprocess
import json
import os
import sys
import tempfile
import sqlite3
import pickle
import numpy as np
from pathlib import Path
from sklearn.linear_model import Ridge

def test_e2e_studio_deployment():
    # 1. Setup isolated temporary directory for HOME/USERPROFILE to not touch production data
    temp_dir = tempfile.TemporaryDirectory()
    temp_dir_path = Path(temp_dir.name)
    
    db_dir = temp_dir_path / ".local" / "share" / "com.edeon.desktop"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "edeon.db"
    
    models_dir = db_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    
    # 2. Train a trivial regression model and save pickle
    estimator = Ridge()
    X = np.random.rand(10, 2)
    y = np.random.rand(10)
    estimator.fit(X, y)
    
    model_id = "test_e2e_studio_999"
    with open(models_dir / f"{model_id}.pkl", "wb") as f:
        pickle.dump(estimator, f)
        
    # 3. Initialize SQLite saved_models table and insert row
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS saved_models (
            id            TEXT PRIMARY KEY,
            name          TEXT NOT NULL,
            type          TEXT NOT NULL,
            algorithm     TEXT NOT NULL,
            features      TEXT NOT NULL,
            metrics       TEXT NOT NULL,
            importances   TEXT NOT NULL,
            provenance    TEXT DEFAULT '{}',
            curation_report TEXT DEFAULT '{}',
            cv_results    TEXT DEFAULT '{}',
            y_scramble    TEXT DEFAULT '{}',
            search_results TEXT DEFAULT '{}',
            created_at    TEXT NOT NULL,
            ad_reference  BLOB,
            diagnostics   TEXT DEFAULT '{}',
            cliffs        TEXT DEFAULT '{}',
            schema_version INTEGER DEFAULT 4,
            deploy_target TEXT,
            deployed_at   TEXT,
            deployment_status TEXT DEFAULT 'undeployed'
        );
    """)
    config = {
        "featurizer_selections": [
            {"id": "descriptors_2d", "params": {"selected": ["MolWt", "MolLogP"]}}
        ]
    }
    provenance = {"config": config, "dataset_hash": "sha256:dummy"}
    cur.execute(
        "INSERT INTO saved_models (id, name, type, algorithm, features, metrics, importances, "
        "provenance, created_at, deployment_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (model_id, "E2E Studio Model", "regression", "Ridge", "[]", "{}", "{}", json.dumps(provenance), "2026-05-29", "undeployed")
    )
    conn.commit()
    conn.close()
    
    # 4. Start the Python IPC server subprocess
    server_path = Path(__file__).parents[2] / "python"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(server_path)
    env["HOME"] = str(temp_dir_path)
    env["USERPROFILE"] = str(temp_dir_path)
    
    process = subprocess.Popen(
        [sys.executable, "-m", "edeon_models.ipc.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env
    )
    
    try:
        # Read the initial "ready" signal from standard output
        ready_line = process.stdout.readline().strip()
        ready_data = json.loads(ready_line)
        assert ready_data.get("result") == "ready"
        
        # Helper to send JSON-RPC requests
        def send_request(method: str, params: dict) -> dict:
            request = {"id": "req-id", "method": method, "params": params}
            process.stdin.write(json.dumps(request) + "\n")
            process.stdin.flush()
            response_line = process.stdout.readline().strip()
            return json.loads(response_line)
            
        # 5. Calls model_predict — asserts tier=2 (fallback/initial state)
        resp1 = send_request("predict", {
            "endpoint": "bcf",
            "smiles": ["CCO"],
            "preferred_tier": None
        })
        assert resp1.get("error") is None
        preds1 = resp1.get("result")
        assert len(preds1) == 1
        assert preds1[0]["tier"] == 2
        
        # 6. Calls deploy_studio_model(saved_id, "bcf")
        resp_deploy = send_request("deploy_studio_model", {
            "saved_model_id": model_id,
            "endpoint": "bcf"
        })
        assert resp_deploy.get("error") is None
        card = resp_deploy.get("result")
        assert card["tier"] == 4
        
        # 7. Calls model_predict — asserts tier=4 (the newly deployed custom model)
        resp2 = send_request("predict", {
            "endpoint": "bcf",
            "smiles": ["CCO"],
            "preferred_tier": 4
        })
        assert resp2.get("error") is None
        preds2 = resp2.get("result")
        assert len(preds2) == 1
        assert preds2[0]["tier"] == 4
        
        # 8. Calls undeploy_studio_model(saved_id)
        resp_undeploy = send_request("undeploy_studio_model", {
            "saved_model_id": model_id
        })
        assert resp_undeploy.get("error") is None
        assert resp_undeploy.get("result") is True
        
        # 9. Calls model_predict again — asserts tier=2 (falls back cleanly)
        resp3 = send_request("predict", {
            "endpoint": "bcf",
            "smiles": ["CCO"],
            "preferred_tier": 4  # Since Tier 4 is unregistered, registry.get falls back to lowest (Tier 2)
        })
        assert resp3.get("error") is None
        preds3 = resp3.get("result")
        assert len(preds3) == 1
        assert preds3[0]["tier"] == 2
        
    finally:
        # Send quit signal or terminate process
        try:
            process.stdin.write(json.dumps({"command": "quit"}) + "\n")
            process.stdin.flush()
            process.wait(timeout=2)
        except Exception:
            process.kill()
        process.stdin.close()
        process.stdout.close()
        process.stderr.close()
        temp_dir.cleanup()
