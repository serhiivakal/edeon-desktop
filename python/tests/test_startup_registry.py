import os
import tempfile
import unittest

from edeon_models.endpoints import Endpoint
from edeon_models.registry import BackendRegistry
from edeon_models import build_default_registry, list_cards
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
)

class TestStartupRegistry(unittest.TestCase):
    
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        
    def tearDown(self):
        os.close(self.db_fd)
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_default_registry_persists_model_cards(self):
        """Assert build_default_registry saves all 12 ModelCards to DB."""
        reg = build_default_registry(db_path=self.db_path)
        cards = list_cards(db_path=self.db_path)
        self.assertEqual(len(cards), 12)
        
        # Verify specific fields/endpoints of persisted cards
        model_ids = {card.model_id for card in cards}
        for ep in [
            Endpoint.BEE_ACUTE_ORAL_LD50,
            Endpoint.FISH_ACUTE_LC50,
            Endpoint.DAPHNIA_ACUTE_EC50,
            Endpoint.EARTHWORM_ACUTE_LC50,
            Endpoint.BIRD_ACUTE_ORAL_LD50,
            Endpoint.RAT_ACUTE_ORAL_LD50,
            Endpoint.SKIN_SENSITIZATION,
            Endpoint.EYE_IRRITATION,
            Endpoint.SOIL_KOC,
            Endpoint.SOIL_DT50,
            Endpoint.GUS_INDEX,
            Endpoint.PHOTOSTABILITY_CLASS,
        ]:
            backend = reg.get(ep)
            self.assertIsNotNone(backend)
            self.assertIn(backend.metadata().model_id, model_ids)

    def test_default_registry_registration(self):
        """Assert build_default_registry registers all 12 T2 backends correctly."""
        reg = build_default_registry()
        self.assertIsInstance(reg, BackendRegistry)
        
        # Verify 12 distinct endpoints are mapped
        endpoints_to_test = [
            Endpoint.BEE_ACUTE_ORAL_LD50,
            Endpoint.FISH_ACUTE_LC50,
            Endpoint.DAPHNIA_ACUTE_EC50,
            Endpoint.EARTHWORM_ACUTE_LC50,
            Endpoint.BIRD_ACUTE_ORAL_LD50,
            Endpoint.RAT_ACUTE_ORAL_LD50,
            Endpoint.SKIN_SENSITIZATION,
            Endpoint.EYE_IRRITATION,
            Endpoint.SOIL_KOC,
            Endpoint.SOIL_DT50,
            Endpoint.GUS_INDEX,
            Endpoint.PHOTOSTABILITY_CLASS,
        ]
        
        for ep in endpoints_to_test:
            backend = reg.get(ep)
            self.assertIsNotNone(backend)
            self.assertEqual(backend.tier(), 2)
            self.assertEqual(backend.endpoint(), ep)
            
            # Verify active class type matches
            expected_class_name = {
                Endpoint.BEE_ACUTE_ORAL_LD50: "BeeLD50_T2",
                Endpoint.FISH_ACUTE_LC50: "FishLC50_T2",
                Endpoint.DAPHNIA_ACUTE_EC50: "DaphniaEC50_T2",
                Endpoint.EARTHWORM_ACUTE_LC50: "EarthwormLC50_T2",
                Endpoint.BIRD_ACUTE_ORAL_LD50: "MallardLD50_T2",
                Endpoint.RAT_ACUTE_ORAL_LD50: "RatLD50_T2",
                Endpoint.SKIN_SENSITIZATION: "SkinSensitization_T2",
                Endpoint.EYE_IRRITATION: "EyeIrritation_T2",
                Endpoint.SOIL_KOC: "SoilKoc_T2",
                Endpoint.SOIL_DT50: "SoilDT50_T2",
                Endpoint.GUS_INDEX: "GUSIndex_T2",
                Endpoint.PHOTOSTABILITY_CLASS: "Photostability_T2",
            }[ep]
            self.assertEqual(backend.__class__.__name__, expected_class_name)

if __name__ == "__main__":
    unittest.main()
