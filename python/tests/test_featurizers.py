import unittest
import numpy as np
from rdkit import Chem
from edeon_engine.models.featurizers import FEATURIZER_REGISTRY, run_featurizers
from edeon_engine.models.featurizers.custom import _safe_eval

class TestFeaturizers(unittest.TestCase):
    def setUp(self):
        # 5-molecule smoke set
        self.smiles = [
            "CCO",
            "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
            "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O",
            "C1CCCCC1",
            "CC(=O)OC1=CC=CC=C1C(=O)O"
        ]

    def test_all_registered_featurizers_dimensionality(self):
        """Each registered featurizer produces a vector of declared dimensionality."""
        for feat_id, spec in FEATURIZER_REGISTRY.items():
            if feat_id == "custom":
                params = {"expression": "Descriptors.MolWt(mol)"}
            elif feat_id == "descriptors_2d":
                params = {"selected": ["MolWt", "MolLogP", "TPSA"]}
            elif feat_id in ("morgan", "fcfp"):
                params = {"radius": 2, "n_bits": 1024}
            elif feat_id in ("maccs", "avalon", "rdkit_topological", "atom_pair", "topological_torsion", "pharm2d_gobbi", "pharm2d_basic"):
                params = {"n_bits": 512}
            else:
                params = {}

            # Check compute runs without crash
            matrix = spec.compute(self.smiles, params)
            self.assertIsInstance(matrix, np.ndarray)
            self.assertEqual(matrix.shape[0], 5)
            self.assertGreater(matrix.shape[1], 0)

            # Check that computed columns match declared or calculated dimensions
            declared_dim = spec.dimensionality(params)
            # Declared dimension for custom and descriptors_2d can be dynamic or length of selection
            if feat_id == "descriptors_2d":
                self.assertEqual(matrix.shape[1], 3)
            elif feat_id == "custom":
                self.assertEqual(matrix.shape[1], 1)
            else:
                self.assertEqual(matrix.shape[1], declared_dim)

    def test_concatenation_order_matches_selection(self):
        """run_featurizers horizontal concatenation matches selection order."""
        selections = [
            {"id": "morgan", "params": {"radius": 2, "n_bits": 128}},
            {"id": "descriptors_2d", "params": {"selected": ["MolWt", "MolLogP"]}},
            {"id": "avalon", "params": {"n_bits": 256}}
        ]
        
        # Run individual featurizers to get their shapes
        m_matrix = FEATURIZER_REGISTRY["morgan"].compute(self.smiles, {"radius": 2, "n_bits": 128})
        d_matrix = FEATURIZER_REGISTRY["descriptors_2d"].compute(self.smiles, {"selected": ["MolWt", "MolLogP"]})
        a_matrix = FEATURIZER_REGISTRY["avalon"].compute(self.smiles, {"n_bits": 256})

        # Run concatenated pipeline
        X, names = run_featurizers(self.smiles, selections)
        
        self.assertEqual(X.shape[1], 128 + 2 + 256)
        self.assertEqual(len(names), X.shape[1])

        # Assert individual matrices are correct slice bounds of concatenated matrix
        np.testing.assert_array_equal(X[:, :128], m_matrix)
        np.testing.assert_array_equal(X[:, 128:130], d_matrix)
        np.testing.assert_array_equal(X[:, 130:], a_matrix)

        # Assert name prefixes match select orders
        self.assertTrue(all(name.startswith("morgan_") for name in names[:128]))
        self.assertEqual(names[128:130], ["MolWt", "MolLogP"])
        self.assertTrue(all(name.startswith("avalon:") for name in names[130:]))

    def test_custom_expression_restricted_keywords(self):
        """Custom expression sandbox blocks access to unsafe names or keywords."""
        mol = Chem.MolFromSmiles("CCO")
        
        # Rejects double underscore
        with self.assertRaises(ValueError):
            _safe_eval("mol.__class__", mol)
            
        # Rejects unsafe Python builtins / libraries
        unsafe_exprs = [
            "__import__('os').system('echo 1')",
            "eval('1+1')",
            "open('test.txt', 'w')",
            "exec('x=1')",
            "getattr(mol, '__class__')",
            "globals()",
            "locals()"
        ]
        
        for expr in unsafe_exprs:
            with self.assertRaises((ValueError, NameError, Exception)):
                _safe_eval(expr, mol)

if __name__ == "__main__":
    unittest.main()
