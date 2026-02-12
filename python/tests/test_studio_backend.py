import os
import tempfile
import pickle
import json
import sqlite3
import unittest
import numpy as np
from sklearn.ensemble import RandomForestRegressor

from edeon_models.types import Prediction, ModelCard, ADStatus
from edeon_models.endpoints import Endpoint
from edeon_models.backends.studio import StudioBackend

from edeon_engine.applicability import build_ad_reference


class TestStudioBackend(unittest.TestCase):

    def setUp(self):
        # 1. Create a temporary directory for DB and models
        self.test_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.test_dir.name, "edeon.db")
        
        # 2. Setup models subdirectory
        self.models_dir = os.path.join(self.test_dir.name, "models")
        os.makedirs(self.models_dir, exist_ok=True)
        
        # 3. Create active database and schema
        self.conn = sqlite3.connect(self.db_path)
        self.cur = self.conn.cursor()
        self.cur.execute("""
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
        self.conn.commit()

        # 4. Train a dummy scikit-learn model (fit on Lipinski descriptors: MolWt and MolLogP)
        # MolWt of CCO is 46.07, MolLogP is -0.1
        # MolWt of C is 16.04, MolLogP is 0.6
        # MolWt of O is 18.02, MolLogP is -0.5
        X_train = np.array([
            [46.07, -0.1],
            [16.04, 0.6],
            [18.02, -0.5],
            [32.04, -0.3],
            [58.08, 0.2],
            [44.05, -0.2],
            [30.07, 0.1],
            [72.10, 0.4],
            [74.08, -0.1],
            [46.07, -0.1]
        ])
        y_train = np.array([5.5, 3.2, 1.8, 4.1, 6.7, 5.0, 3.8, 7.2, 5.9, 5.5])
        
        self.estimator = RandomForestRegressor(n_estimators=5, random_state=42)
        self.estimator.fit(X_train, y_train)
        
        # Save model estimator to disk
        self.model_id = "test_qsar_model_123"
        self.estimator_path = os.path.join(self.models_dir, f"{self.model_id}.pkl")
        with open(self.estimator_path, "wb") as f:
            pickle.dump(self.estimator, f)

        # 5. Build AD Reference
        train_smiles = ["CCO", "C", "O", "CO", "CCC", "CCO", "CC", "CCCC", "CCCO", "CCO"]
        train_preds = self.estimator.predict(X_train)
        self.ad_ref = build_ad_reference(
            train_smiles=train_smiles,
            X_train=X_train,
            y_train=y_train,
            y_train_pred=train_preds
        )
        self.ad_ref_blob = pickle.dumps(self.ad_ref)

        # 6. Populate database row
        config = {
            "featurizer_selections": [
                {"id": "descriptors_2d", "params": {"selected": ["MolWt", "MolLogP"]}}
            ],
            "split_mode": "random",
            "cv_k": 5,
            "n_compounds_input": 10
        }
        provenance = {
            "config": config,
            "dataset_hash": "sha256:dummyhash12345",
            "n_compounds_input": 10,
            "split_mode": "random",
            "cv_k": 5
        }
        diagnostics = {
            "residuals_vs_fitted": [
                {"y_pred": float(p), "residual": float(abs(t - p))}
                for t, p in zip(y_train, train_preds)
            ]
        }
        metrics = {"rmse": 0.25, "r2": 0.92}
        
        self.cur.execute(
            "INSERT INTO saved_models (id, name, type, algorithm, features, metrics, importances, "
            "provenance, curation_report, cv_results, y_scramble, search_results, created_at, "
            "ad_reference, diagnostics, cliffs, deploy_target, deployment_status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                self.model_id,
                "Test QSAR Model",
                "regression",
                "Random Forest",
                json.dumps(["MolWt", "MolLogP"]),
                json.dumps(metrics),
                json.dumps({}),
                json.dumps(provenance),
                json.dumps({}),
                json.dumps([]),
                json.dumps({}),
                json.dumps({}),
                "2026-05-29T14:00:00Z",
                sqlite3.Binary(self.ad_ref_blob),
                json.dumps(diagnostics),
                json.dumps([]),
                "bee_acute_oral_ld50",
                "deployed"
            )
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.test_dir.cleanup()

    def test_studio_backend_initialization_and_metadata(self):
        """Verify StudioBackend initializes correctly and returns appropriate metadata."""
        backend = StudioBackend(
            saved_model_id=self.model_id,
            db_path=self.db_path,
            deploy_target=Endpoint.BEE_ACUTE_ORAL_LD50
        )
        
        self.assertEqual(backend.tier(), 4)
        self.assertEqual(backend.version(), f"studio-{self.model_id}")
        self.assertEqual(backend.model_id(), f"bee_acute_oral_ld50.t4.studio-{self.model_id}")
        self.assertEqual(backend.endpoint(), Endpoint.BEE_ACUTE_ORAL_LD50)

        # Verify model card metadata
        card = backend.metadata()
        self.assertIsInstance(card, ModelCard)
        self.assertEqual(card.name, "Test QSAR Model")
        self.assertEqual(card.tier, 4)
        self.assertEqual(card.endpoint, "bee_acute_oral_ld50")
        self.assertEqual(card.uncertainty_method, "ConformalUQ")
        self.assertIsNotNone(card.training_data)
        self.assertEqual(card.training_data.n_compounds, 10)
        self.assertEqual(card.training_data.sha256, "sha256:dummyhash12345")
        
        self.assertIsNotNone(card.applicability_domain)
        self.assertEqual(card.applicability_domain.method, "tanimoto_knn")
        self.assertEqual(card.applicability_domain.k, 5)

    def test_studio_backend_predict_valid_smiles(self):
        """Assert predict produces valid Prediction objects with conformal CI and AD status."""
        backend = StudioBackend(
            saved_model_id=self.model_id,
            db_path=self.db_path,
            deploy_target=Endpoint.BEE_ACUTE_ORAL_LD50
        )
        
        query_smiles = ["CCO", "INVALID_SMILES_STRING"]
        preds = backend.predict(query_smiles)
        
        self.assertEqual(len(preds), 2)
        
        # Valid SMILES prediction check
        p1 = preds[0]
        self.assertEqual(p1.smiles, "CCO")
        self.assertEqual(p1.endpoint, "bee_acute_oral_ld50")
        self.assertEqual(p1.value.kind, "numeric")
        self.assertIsInstance(p1.value.numeric, float)
        
        # Conformal intervals check
        self.assertIsNotNone(p1.ci_lower)
        self.assertIsNotNone(p1.ci_upper)
        self.assertTrue(p1.ci_lower < p1.value.numeric < p1.ci_upper)
        
        # AD checks
        self.assertEqual(p1.ad_status, ADStatus.IN)
        self.assertIsNotNone(p1.ad_score)

        # Invalid SMILES prediction check (fails gracefully)
        p2 = preds[1]
        self.assertEqual(p2.smiles, "INVALID_SMILES_STRING")
        self.assertEqual(p2.ad_status, ADStatus.UNKNOWN)
        self.assertTrue(np.isnan(p2.value.numeric))
        self.assertTrue(len(p2.warnings) > 0)
        self.assertTrue(any("failed" in w or "Failed" in w for w in p2.warnings))

    def test_studio_backend_applicability_domain(self):
        """Assert applicability_domain method scores query SMILES correctly."""
        backend = StudioBackend(
            saved_model_id=self.model_id,
            db_path=self.db_path,
            deploy_target=Endpoint.BEE_ACUTE_ORAL_LD50
        )
        
        query_smiles = ["CCO", "[Na+].[Cl-]", "INVALID_SMILES"]
        statuses = backend.applicability_domain(query_smiles)
        
        self.assertEqual(len(statuses), 3)
        self.assertEqual(statuses[0], ADStatus.IN)
        self.assertEqual(statuses[1], ADStatus.OUT)
        self.assertEqual(statuses[2], ADStatus.UNKNOWN)

    def test_deployment_service_success_and_failures(self):
        """Verify successful deployment, type checking, and undeployment services."""
        from edeon_models.registry import BackendRegistry
        from edeon_models import deploy_studio_model, undeploy_studio_model
        from edeon_models.card import load_card
        
        registry = BackendRegistry()
        
        # 1. Success path
        card = deploy_studio_model(
            saved_model_id=self.model_id,
            endpoint=Endpoint.BEE_ACUTE_ORAL_LD50,
            registry=registry,
            db_path=self.db_path
        )
        
        self.assertIsInstance(card, ModelCard)
        self.assertEqual(card.endpoint, "bee_acute_oral_ld50")
        
        # Check that it's registered
        backend = registry.get(Endpoint.BEE_ACUTE_ORAL_LD50)
        self.assertEqual(backend.tier(), 4)
        self.assertEqual(backend.version(), f"studio-{self.model_id}")
        
        # Check database updates
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT deploy_target, deployment_status FROM saved_models WHERE id = ?", (self.model_id,))
        row = cur.fetchone()
        conn.close()
        
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "bee_acute_oral_ld50")
        self.assertEqual(row[1], "deployed")
        
        # Verify ModelCard was saved to database
        loaded_card = load_card(backend.model_id(), db_path=self.db_path)
        self.assertIsNotNone(loaded_card)
        self.assertEqual(loaded_card.name, "Test QSAR Model")
        
        # 2. Type validation failure (incompatible output type)
        # Skin sensitization is category-based, but our custom model is a regression model.
        with self.assertRaises(ValueError) as context:
            deploy_studio_model(
                saved_model_id=self.model_id,
                endpoint=Endpoint.SKIN_SENSITIZATION,
                registry=registry,
                db_path=self.db_path
            )
        self.assertIn("incompatible", str(context.exception))
        
        # 3. Undeployment path
        undeploy_studio_model(
            saved_model_id=self.model_id,
            registry=registry,
            db_path=self.db_path
        )
        
        # Assert that it is unregistered
        with self.assertRaises(KeyError):
            registry.get(Endpoint.BEE_ACUTE_ORAL_LD50)
            
        # Assert database updates are reverted
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT deploy_target, deployment_status FROM saved_models WHERE id = ?", (self.model_id,))
        row = cur.fetchone()
        conn.close()
        
        self.assertIsNotNone(row)
        self.assertIsNone(row[0])
        self.assertEqual(row[1], "undeployed")
        
        # Assert ModelCard was deleted from database
        deleted_card = load_card(backend.model_id(), db_path=self.db_path)
        self.assertIsNone(deleted_card)


if __name__ == "__main__":
    unittest.main()
