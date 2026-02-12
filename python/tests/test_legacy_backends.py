import unittest
import math

from edeon_models.types import Prediction, ModelCard
from edeon_models.endpoints import Endpoint
from edeon_models.backends.legacy import (
    BeeLD50_T2,
    FishLC50_T2,
    DaphniaEC50_T2,
    EarthwormLC50_T2,
    MallardLD50_T2,
    RatLD50_T2,
    SkinSensitization_T2,
    EyeIrritation_T2,
    SoilKoc_T2,
    SoilDT50_T2,
    GUSIndex_T2,
    Photostability_T2,
    BCF_T2,
)

class TestLegacyBackends(unittest.TestCase):
    
    def setUp(self):
        self.backends = [
            BeeLD50_T2(),
            FishLC50_T2(),
            DaphniaEC50_T2(),
            EarthwormLC50_T2(),
            MallardLD50_T2(),
            RatLD50_T2(),
            SkinSensitization_T2(),
            EyeIrritation_T2(),
            SoilKoc_T2(),
            SoilDT50_T2(),
            GUSIndex_T2(),
            Photostability_T2(),
            BCF_T2(),
        ]
        self.test_smiles = ["CCO", "CCC"]
        self.invalid_smiles = ["INVALID"]

    def test_interfaces_and_metadata(self):
        """Assert each backend returns valid endpoint, tier, and metadata Card."""
        for backend in self.backends:
            self.assertEqual(backend.tier(), 2)
            self.assertEqual(backend.version(), "0.1.0-legacy")
            self.assertTrue(backend.model_id().endswith("0.1.0-legacy"))
            
            card = backend.metadata()
            self.assertIsInstance(card, ModelCard)
            self.assertEqual(card.model_id, backend.model_id())
            self.assertEqual(card.tier, 2)
            self.assertEqual(card.version, "0.1.0-legacy")
            self.assertEqual(card.endpoint, backend.endpoint().value)

    def test_predictions_valid_smiles(self):
        """Assert each backend returns correct Predictions on valid SMILES."""
        for backend in self.backends:
            preds = backend.predict(self.test_smiles)
            self.assertEqual(len(preds), 2)
            for p in preds:
                self.assertIsInstance(p, Prediction)
                self.assertEqual(p.tier, 2)
                self.assertEqual(p.endpoint, backend.endpoint().value)
                self.assertEqual(p.model_version, "0.1.0-legacy")
                self.assertEqual(p.model_id, backend.model_id())
                
                # Check data format
                if backend.endpoint() in [
                    Endpoint.SKIN_SENSITIZATION,
                    Endpoint.EYE_IRRITATION,
                    Endpoint.PHOTOSTABILITY_CLASS
                ]:
                    self.assertEqual(p.value.kind, "categorical")
                    self.assertIsInstance(p.value.categorical, str)
                    self.assertIsNone(p.value.numeric)
                else:
                    self.assertEqual(p.value.kind, "numeric")
                    self.assertIsInstance(p.value.numeric, float)
                    self.assertFalse(math.isnan(p.value.numeric))
                    self.assertIsNone(p.value.categorical)

    def test_predictions_invalid_smiles_graceful_failures(self):
        """Assert each backend handles invalid SMILES gracefully and returns NaNs or Unknown category."""
        for backend in self.backends:
            preds = backend.predict(self.invalid_smiles)
            self.assertEqual(len(preds), 1)
            p = preds[0]
            self.assertIsInstance(p, Prediction)
            self.assertEqual(p.smiles, "INVALID")
            self.assertTrue(len(p.warnings) > 0)
            self.assertTrue(any("failed" in w or "Invalid" in w for w in p.warnings))
            
            if p.value.kind == "categorical":
                self.assertEqual(p.value.categorical, "Unknown")
            else:
                self.assertTrue(math.isnan(p.value.numeric))

if __name__ == "__main__":
    unittest.main()
