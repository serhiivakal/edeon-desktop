import unittest
from edeon_engine.transformation.pathway import predict_transformation_pathway, check_risk_increase

class TestTransformation(unittest.TestCase):

    def test_predict_transformation_pathway(self):
        # Test parent compound: Atrazine
        smiles = "C1=NC(=NC(=N1)Cl)NC(C)C"
        
        # Test abiotic (custom rules) only
        res_abiotic = predict_transformation_pathway(smiles, ["abiotic"], max_depth=1)
        self.assertIn("nodes", res_abiotic)
        self.assertIn("edges", res_abiotic)
        self.assertGreater(len(res_abiotic["nodes"]), 0)
        
        # Check that parent node exists in nodes
        nodes = res_abiotic["nodes"]
        parent_nodes = [n for n in nodes if n["rule"] == "parent"]
        self.assertEqual(len(parent_nodes), 1)
        from rdkit import Chem
        self.assertEqual(parent_nodes[0]["smiles"], Chem.MolToSmiles(Chem.MolFromSmiles(smiles)))
        self.assertEqual(parent_nodes[0]["probability"], 1.0)
        
        # Test metabolic + abiotic combined
        res_all = predict_transformation_pathway(smiles, ["abiotic", "metabolic"], max_depth=1)
        self.assertGreater(len(res_all["nodes"]), len(res_abiotic["nodes"]))
        
        # Verify edge links
        for edge in res_all["edges"]:
            self.assertIn("source", edge)
            self.assertIn("target", edge)
            self.assertIn("rule", edge)
            self.assertIn("probability", edge)

    def test_check_risk_increase(self):
        # Construct mockup data for risk checks
        parent_fate = {"dt50_soil": {"value": 50.0}, "bcf": {"value": 100.0}, "gus": {"value": 1.5}}
        parent_tox = {"overall_level": "Low"}
        
        # Scenario 1: TP has same properties -> no risk increase
        tp_fate_same = {"dt50_soil": {"value": 50.0}, "bcf": {"value": 100.0}, "gus": {"value": 1.5}}
        tp_tox_same = {"overall_level": "Low"}
        self.assertFalse(check_risk_increase(parent_fate, parent_tox, tp_fate_same, tp_tox_same))
        
        # Scenario 2: TP is more persistent
        tp_fate_persist = {"dt50_soil": {"value": 60.0}, "bcf": {"value": 100.0}, "gus": {"value": 1.5}}
        self.assertTrue(check_risk_increase(parent_fate, parent_tox, tp_fate_persist, tp_tox_same))
        
        # Scenario 3: TP is more toxic
        tp_tox_high = {"overall_level": "High"}
        self.assertTrue(check_risk_increase(parent_fate, parent_tox, tp_fate_same, tp_tox_high))

    def test_invalid_smiles_handling(self):
        with self.assertRaises(ValueError):
            predict_transformation_pathway("INVALID_SMILES", ["abiotic"])

if __name__ == "__main__":
    unittest.main()
