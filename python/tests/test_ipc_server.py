import unittest
import tempfile
import os
import sqlite3
import json
from edeon_models.ipc.commands import execute_command
from edeon_models.endpoints import Endpoint

class TestIPCServer(unittest.TestCase):
    
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()

    def tearDown(self):
        os.close(self.db_fd)
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_list_endpoints(self):
        result = execute_command("list_endpoints", {}, db_path=self.db_path)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 16)
        self.assertIn("bee_acute_oral_ld50", result)

    def test_set_and_get_preference(self):
        # Initial is None
        val_initial = execute_command("get_preference", {"endpoint": "bee_acute_oral_ld50"}, db_path=self.db_path)
        self.assertIsNone(val_initial)

        # Set preference
        set_res = execute_command("set_preference", {"endpoint": "bee_acute_oral_ld50", "tier": 2}, db_path=self.db_path)
        self.assertTrue(set_res)

        # Get preference
        val_after = execute_command("get_preference", {"endpoint": "bee_acute_oral_ld50"}, db_path=self.db_path)
        self.assertEqual(val_after, 2)

    def test_get_card(self):
        result = execute_command("get_card", {"model_id": "bee_acute_oral_ld50.t2.0.1.0-legacy"}, db_path=self.db_path)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["model_id"], "bee_acute_oral_ld50.t2.0.1.0-legacy")
        self.assertEqual(result["tier"], 2)

    def test_list_for_endpoint(self):
        result = execute_command("list_for_endpoint", {"endpoint": "bee_acute_oral_ld50"}, db_path=self.db_path)
        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0)
        self.assertEqual(result[0]["model_id"], "bee_acute_oral_ld50.t2.0.1.0-legacy")

    def test_predict(self):
        # Set preferred tier to 2
        execute_command("set_preference", {"endpoint": "bee_acute_oral_ld50", "tier": 2}, db_path=self.db_path)
        
        result = execute_command("predict", {
            "endpoint": "bee_acute_oral_ld50",
            "smiles": ["CCO", "CC(=O)O"],
            "preferred_tier": 2
        }, db_path=self.db_path)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["smiles"], "CCO")
        self.assertEqual(result[0]["endpoint"], "bee_acute_oral_ld50")
        self.assertIsNotNone(result[0]["value"])

    def test_ipc_deploy_undeploy(self):
        # 1. Create a dummy scikit-learn estimator file in temporary models dir
        models_dir = os.path.join(os.path.dirname(self.db_path), "models")
        os.makedirs(models_dir, exist_ok=True)
        
        from sklearn.linear_model import Ridge
        import pickle
        import numpy as np
        
        estimator = Ridge()
        # Train on simple 2D Lipinski descriptors mockup data (10 compounds)
        X = np.random.rand(10, 2)
        y = np.random.rand(10)
        estimator.fit(X, y)
        
        model_id = "test_ipc_model_999"
        with open(os.path.join(models_dir, f"{model_id}.pkl"), "wb") as f:
            pickle.dump(estimator, f)
            
        # 2. Insert mock row in saved_models table
        conn = sqlite3.connect(self.db_path)
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
            (model_id, "IPC Model", "regression", "Ridge", "[]", "{}", "{}", json.dumps(provenance), "2026-05-29", "undeployed")
        )
        conn.commit()
        conn.close()
        
        # 3. Test deploy_studio_model command
        deploy_res = execute_command("deploy_studio_model", {
            "saved_model_id": model_id,
            "endpoint": "bee_acute_oral_ld50"
        }, db_path=self.db_path)
        
        self.assertIsInstance(deploy_res, dict)
        self.assertEqual(deploy_res["model_id"], f"bee_acute_oral_ld50.t4.studio-{model_id}")
        self.assertEqual(deploy_res["endpoint"], "bee_acute_oral_ld50")
        
        # 4. Test undeploy_studio_model command
        undeploy_res = execute_command("undeploy_studio_model", {
            "saved_model_id": model_id
        }, db_path=self.db_path)
        self.assertTrue(undeploy_res)


if __name__ == "__main__":
    unittest.main()
