import unittest
import math
from edeon_engine.selectivity import compute_single_selectivity, selectivity_batch

class TestSelectivity(unittest.TestCase):

    def test_selectivity_predicted_mode(self):
        """Test compute_single_selectivity in default predicted target potency mode."""
        # Test with a simple molecule (ethanol)
        res = compute_single_selectivity("CCO", target_mode="predicted")
        
        self.assertIn("profiles", res)
        self.assertIn("min_selectivity", res)
        self.assertIn("overall_level", res)
        self.assertIn("uq", res)
        
        # We expect 6 profiles
        self.assertEqual(len(res["profiles"]), 6)
        
        organisms = [p["organism"] for p in res["profiles"]]
        expected_organisms = ["Honeybee", "Earthworm", "Fish", "Bird", "Daphnia", "Mammal"]
        for org in expected_organisms:
            self.assertIn(org, organisms)
            
        # Check profile structures
        for p in res["profiles"]:
            self.assertIn("organism", p)
            self.assertIn("latin", p)
            self.assertIn("selectivity_index", p)
            self.assertIn("level", p)
            self.assertIn("detail", p)
            self.assertIn("ci_lower", p)
            self.assertIn("ci_upper", p)
            self.assertIn("ad_status", p)
            
            self.assertIsInstance(p["selectivity_index"], float)
            self.assertIsInstance(p["ci_lower"], float)
            self.assertIsInstance(p["ci_upper"], float)
            self.assertIn(p["level"], ["safe", "moderate", "danger"])
            
        # Check MPO/UQ fields
        self.assertIsInstance(res["min_selectivity"], float)
        self.assertIn(res["overall_level"], ["safe", "moderate", "danger"])
        self.assertEqual(res["uq"]["coverage"], 0.90)
        self.assertIsInstance(res["uq"]["lower"], float)
        self.assertIsInstance(res["uq"]["upper"], float)

    def test_selectivity_user_mode(self):
        """Test compute_single_selectivity with user-supplied target potency."""
        # Test with a very potent target requirement (0.01 uM)
        res_high = compute_single_selectivity("CCO", target_potency_uM=0.01, target_mode="user")
        
        # Test with a weak target requirement (100.0 uM)
        res_low = compute_single_selectivity("CCO", target_potency_uM=100.0, target_mode="user")
        
        # We expect safety margins to be much higher when target requirement is potent (0.01 uM)
        self.assertGreater(res_high["min_selectivity"], res_low["min_selectivity"])

    def test_selectivity_batch(self):
        """Test batch selectivity calculations."""
        compounds = [
            {"smiles": "CCO", "mol_weight": 46.0, "logp": -0.1},
            {"smiles": "CCC", "mol_weight": 44.0, "logp": 1.0}
        ]
        
        # Run batch with predicted mode
        res_pred = selectivity_batch(compounds)
        self.assertEqual(len(res_pred), 2)
        
        # Run batch with user mode and scalar value
        target = {"mode": "user", "value": 5.0}
        res_user = selectivity_batch(compounds, target_potency=target)
        self.assertEqual(len(res_user), 2)

    def test_selectivity_invalid_smiles(self):
        """Assert compute_single_selectivity handles invalid SMILES gracefully."""
        res = compute_single_selectivity("INVALID_SMILES")
        self.assertEqual(res["min_selectivity"], 0.0)
        self.assertEqual(res["overall_level"], "danger")
        self.assertEqual(res["uq"]["ad_status"], "unknown")
        for p in res["profiles"]:
            self.assertEqual(p["selectivity_index"], 0.0)
            self.assertEqual(p["level"], "danger")

if __name__ == "__main__":
    unittest.main()
