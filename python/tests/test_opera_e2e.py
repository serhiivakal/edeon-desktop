import os
import tempfile
import unittest
import sqlite3
import json
from pathlib import Path

from edeon_models.endpoints import Endpoint
from edeon_models.types import Prediction, PredictionValue, ADStatus
from edeon_models.registry import BackendRegistry
from edeon_models import build_default_registry
from edeon_models.backends.external.opera_backend import OperaTier3Backend, OperaCache

class TestOperaIntegration(unittest.TestCase):

    def setUp(self):
        # Create a temp file for cache database
        self.cache_fd, self.cache_path = tempfile.mkstemp(suffix=".db")
        # Initialize SQLite cache with it
        self.cache = OperaCache(self.cache_path)

    def tearDown(self):
        os.close(self.cache_fd)
        if os.path.exists(self.cache_path):
            try:
                os.remove(self.cache_path)
            except OSError:
                pass

    def test_opera_backends_registration(self):
        """Assert build_default_registry registers OPERA Tier-3 backends correctly."""
        reg = build_default_registry()
        self.assertIsInstance(reg, BackendRegistry)

        opera_endpoints = [
            Endpoint.SOIL_KOC,
            Endpoint.BCF,
            Endpoint.SOIL_DT50,
            Endpoint.RAT_ACUTE_ORAL_LD50,
            Endpoint.LOGP,
            Endpoint.PKA,
            Endpoint.SOLUBILITY,
            Endpoint.HENRYS_LAW,
        ]

        for ep in opera_endpoints:
            backend = reg.get(ep, preferred_tier=3)
            self.assertIsNotNone(backend, f"No Tier-3 backend registered for {ep}")
            self.assertEqual(backend.tier(), 3)
            self.assertEqual(backend.endpoint(), ep)
            self.assertEqual(backend.version(), "2.9")
            self.assertEqual(backend.model_id(), f"{ep.value}.t3.2.9")

    def test_mock_fallback_mode(self):
        """Verify deterministic mock prediction construction when OPERA binary is missing."""
        backend = OperaTier3Backend(Endpoint.LOGP, cache_path=self.cache_path)
        # Force mock mode
        backend._is_mock = True

        smiles = "CCO"
        predictions = backend.predict([smiles])
        self.assertEqual(len(predictions), 1)

        pred = predictions[0]
        self.assertEqual(pred.smiles, smiles)
        self.assertEqual(pred.endpoint, Endpoint.LOGP.value)
        self.assertEqual(pred.tier, 3)
        self.assertEqual(pred.value.kind, "numeric")
        self.assertIsNotNone(pred.value.numeric)
        
        # Verify mock mode warning
        self.assertTrue(any("mock mode" in w.lower() for w in pred.warnings))

    def test_mock_fallback_composite_pka(self):
        """Verify mock prediction constructs a composite categorical value for pKa."""
        backend = OperaTier3Backend(Endpoint.PKA, cache_path=self.cache_path)
        backend._is_mock = True

        predictions = backend.predict(["CCO"])
        self.assertEqual(len(predictions), 1)
        
        pred = predictions[0]
        self.assertEqual(pred.value.kind, "categorical")
        self.assertTrue("Acidic:" in pred.value.categorical)
        self.assertTrue("Basic:" in pred.value.categorical)
        self.assertIsNotNone(pred.provenance.get("pka_acidic"))
        self.assertIsNotNone(pred.provenance.get("pka_basic"))

    def test_sqlite_caching_layer(self):
        """Verify that predictions are cached and cache hits return cached data."""
        backend = OperaTier3Backend(Endpoint.LOGP, cache_path=self.cache_path)
        backend._is_mock = True

        smiles = "CCO"
        
        # 1. Run prediction first time (writes to cache)
        preds1 = backend.predict([smiles])
        self.assertEqual(len(preds1), 1)
        val1 = preds1[0].value.numeric

        # 2. Modify the cached value directly in DB to verify cache hit
        conn = sqlite3.connect(self.cache_path)
        try:
            # Let's verify row exists
            cursor = conn.cursor()
            cursor.execute("SELECT smiles, value_json FROM opera_cache")
            rows = cursor.fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0][0], smiles)

            # Change value in database to a custom number
            custom_val = {"kind": "numeric", "numeric": 99.9}
            conn.execute(
                "UPDATE opera_cache SET value_json = ? WHERE smiles = ?",
                (json.dumps(custom_val), smiles)
            )
            conn.commit()
        finally:
            conn.close()

        # 3. Predict again, should return custom_val (cache hit)
        preds2 = backend.predict([smiles])
        self.assertEqual(len(preds2), 1)
        self.assertEqual(preds2[0].value.numeric, 99.9)

        # 4. Verify batch caching
        smiles_list = ["CCO", "CCN", "CCC"]
        # CC and CCC will be predicted (and cached), CCN is already in cache (custom value 99.9)
        # Wait, smiles_list contains CCO, let's predict it
        preds_batch = backend.predict(smiles_list)
        self.assertEqual(len(preds_batch), 3)
        self.assertEqual(preds_batch[0].value.numeric, 99.9)  # Cache hit
        self.assertNotEqual(preds_batch[1].value.numeric, 99.9) # Calculated fallback
        self.assertNotEqual(preds_batch[2].value.numeric, 99.9) # Calculated fallback

if __name__ == "__main__":
    unittest.main()
