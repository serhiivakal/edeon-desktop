import unittest
import numpy as np
from rdkit import Chem
from edeon_engine.models.featurizers import FEATURIZER_REGISTRY, run_featurizers, _legacy_features_to_selections
from edeon_engine.models.featurizers.custom import _safe_eval, test_custom_expression
from edeon_engine.models.featurizers.descriptors_2d import LIPINSKI

class TestPhase2Featurizers(unittest.TestCase):
    def test_registry_populated(self):
        self.assertIn("descriptors_2d", FEATURIZER_REGISTRY)
        self.assertIn("morgan", FEATURIZER_REGISTRY)
        self.assertIn("fcfp", FEATURIZER_REGISTRY)
        self.assertIn("maccs", FEATURIZER_REGISTRY)
        self.assertIn("avalon", FEATURIZER_REGISTRY)
        self.assertIn("rdkit_topological", FEATURIZER_REGISTRY)
        self.assertIn("atom_pair", FEATURIZER_REGISTRY)
        self.assertIn("topological_torsion", FEATURIZER_REGISTRY)
        self.assertIn("pharm2d_gobbi", FEATURIZER_REGISTRY)
        self.assertIn("pharm2d_basic", FEATURIZER_REGISTRY)
        self.assertIn("custom", FEATURIZER_REGISTRY)

    def test_lipinski_morgan_exact_dim(self):
        # Selecting Lipinski (6 descriptors) + Morgan (r=2, 2048) produces total_dim == 2054 exactly
        selections = [
            {"id": "descriptors_2d", "params": {"selected": list(LIPINSKI)}},
            {"id": "morgan", "params": {"radius": 2, "n_bits": 2048}}
        ]
        smiles = ["CCO"]
        X, names = run_featurizers(smiles, selections)
        self.assertEqual(X.shape[1], 2054)
        self.assertEqual(len(names), 2054)

    def test_pharmacophore_folding(self):
        selections = [
            {"id": "pharm2d_gobbi", "params": {"n_bits": 1024}},
            {"id": "pharm2d_basic", "params": {"n_bits": 1024}}
        ]
        smiles = ["CCO", "CN1C=NC2=C1C(=O)N(C(=O)N2C)C"]
        X, names = run_featurizers(smiles, selections)
        self.assertEqual(X.shape, (2, 2048))

    def test_custom_sandbox_safety(self):
        mol = Chem.MolFromSmiles("CCO")
        # Allowed operations
        val = _safe_eval("Descriptors.MolWt(mol)", mol)
        self.assertAlmostEqual(val, 46.069, places=2)

        # Disallowed imports or names
        with self.assertRaises(Exception):
            _safe_eval("import os", mol)
        with self.assertRaises(ValueError):
            _safe_eval("os.system('echo 1')", mol)
        with self.assertRaises(ValueError):
            _safe_eval("mol.__class__", mol)

    def test_custom_expression_runner(self):
        smiles = ["CCO", "CN1C=NC2=C1C(=O)N(C(=O)N2C)C", "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O"]
        res = test_custom_expression(smiles, "Descriptors.MolWt(mol) + Descriptors.MolLogP(mol)")
        self.assertEqual(len(res), 3)
        for item in res:
            self.assertTrue(item["success"])
            self.assertIsInstance(item["value"], float)

    def test_legacy_features_to_selections_shim(self):
        legacy = ["morgan_2_2048", "descriptors_basic"]
        selections = _legacy_features_to_selections(legacy)
        self.assertEqual(len(selections), 2)
        self.assertEqual(selections[0]["id"], "morgan")
        self.assertEqual(selections[0]["params"]["radius"], 2)
        self.assertEqual(selections[0]["params"]["n_bits"], 2048)
        self.assertEqual(selections[1]["id"], "descriptors_2d")
        self.assertEqual(set(selections[1]["params"]["selected"]), LIPINSKI)

if __name__ == "__main__":
    unittest.main()
