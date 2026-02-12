import unittest
from edeon_models.endpoints import Endpoint, endpoint_metadata

class TestEndpoints(unittest.TestCase):
    
    def test_canonical_endpoint_values(self):
        """Assert BEE_ACUTE_ORAL_LD50 value matches the spec verbatim."""
        self.assertEqual(Endpoint.BEE_ACUTE_ORAL_LD50, "bee_acute_oral_ld50")
        self.assertTrue(Endpoint.BEE_ACUTE_ORAL_LD50 == "bee_acute_oral_ld50")
        
    def test_all_16_endpoints_present(self):
        """Verify all 16 endpoints described in Section 4 are present."""
        expected_endpoints = {
            "bee_acute_oral_ld50",
            "bee_acute_contact_ld50",
            "fish_acute_lc50",
            "daphnia_acute_ec50",
            "algae_growth_ec50",
            "earthworm_acute_lc50",
            "bird_acute_oral_ld50",
            "rat_acute_oral_ld50",
            "skin_sensitization",
            "eye_irritation",
            "soil_koc",
            "soil_dt50",
            "gus_index",
            "bcf",
            "photostability_class",
            "pesticide_likeness_tice"
        }
        
        actual_endpoints = {ep.value for ep in Endpoint}
        self.assertEqual(actual_endpoints, expected_endpoints)
        self.assertEqual(len(Endpoint), 16)
        
    def test_endpoint_metadata(self):
        """Verify metadata fields for each of the 16 endpoints."""
        for ep in Endpoint:
            meta = endpoint_metadata(ep)
            self.assertIsInstance(meta, dict)
            self.assertIn("description", meta)
            self.assertIn("units", meta)
            self.assertIn("direction", meta)
            self.assertIsInstance(meta["description"], str)
            self.assertIsInstance(meta["units"], str)
            self.assertTrue(isinstance(meta["direction"], str) or meta["direction"] is None)
            
        # Check specific metadata values to ensure accuracy
        bee_oral_meta = endpoint_metadata(Endpoint.BEE_ACUTE_ORAL_LD50)
        self.assertEqual(bee_oral_meta["units"], "µg/bee")
        self.assertEqual(bee_oral_meta["direction"], "Lower = more toxic")
        
        gus_meta = endpoint_metadata(Endpoint.GUS_INDEX)
        self.assertEqual(gus_meta["units"], "unitless")
        self.assertEqual(gus_meta["direction"], "Higher = more leaching risk")

        photostability_meta = endpoint_metadata(Endpoint.PHOTOSTABILITY_CLASS)
        self.assertEqual(photostability_meta["direction"], "—")

        # Test passing string values to metadata function
        meta_str = endpoint_metadata("bee_acute_oral_ld50")
        self.assertEqual(meta_str["units"], "µg/bee")

        with self.assertRaises(ValueError):
            endpoint_metadata("invalid_endpoint_name")

if __name__ == "__main__":
    unittest.main()
