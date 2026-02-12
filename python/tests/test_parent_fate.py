import unittest
import math
from edeon_engine.fate.parent_fate import environmental_fate_batch

class TestParentFate(unittest.TestCase):

    def test_environmental_fate_batch(self):
        # Test valid compounds: Atrazine and DDT
        smiles_list = [
            "C1=NC(=NC(=N1)Cl)NC(C)C",  # Atrazine
            "C1=CC(=CC=C1C(C2=CC=C(C=C2)Cl)C(Cl)(Cl)Cl)Cl"  # DDT
        ]
        
        results = environmental_fate_batch(smiles_list)
        self.assertEqual(len(results), 2)
        
        # Atrazine assertions
        atr = results[0]
        self.assertEqual(atr["smiles"], smiles_list[0])
        self.assertGreater(atr["dt50_soil"]["value"], 0)
        self.assertGreater(atr["koc"]["value"], 0)
        self.assertIsNotNone(atr["gus"]["value"])
        # Atrazine is traditionally classified as a leacher (GUS > 2.8)
        self.assertEqual(atr["gus"]["class"], "leacher")
        self.assertIn("pbt", atr)
        self.assertIn("verdict", atr["pbt"])
        
        # DDT assertions
        ddt = results[1]
        self.assertEqual(ddt["smiles"], smiles_list[1])
        # DDT has a very high Koc (highly sorbing) and high BCF (highly bioaccumulative)
        self.assertGreater(ddt["koc"]["value"], 1000)
        self.assertGreater(ddt["bcf"]["value"], 2000)
        self.assertEqual(ddt["gus"]["class"], "non-leacher")
        self.assertTrue(ddt["pbt"]["b"])
        self.assertTrue(ddt["pbt"]["vb"])

    def test_invalid_smiles_handling(self):
        # Assert graceful error envelope is returned for invalid SMILES
        results = environmental_fate_batch(["INVALID_SMILES"])
        self.assertEqual(len(results), 1)
        res = results[0]
        self.assertIsNone(res["dt50_soil"]["value"])
        self.assertEqual(res["gus"]["class"], "unknown")
        self.assertEqual(res["pbt"]["verdict"], "Failed")

if __name__ == "__main__":
    unittest.main()
