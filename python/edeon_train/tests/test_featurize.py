import unittest
import numpy as np
from edeon_train.shared.featurize import (
    compute_morgan_fps,
    compute_maccs_fps,
    compute_rdkit_descriptors,
    select_uncorrelated_descriptors,
    featurize_for_baseline,
    FeatureRegistry
)

class TestFeaturize(unittest.TestCase):
    def setUp(self):
        # A mix of typical molecules
        self.smiles_list = [
            "CCO",  # Ethanol
            "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O",  # Ibuprofen
            "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",  # Caffeine
            "C1=CC=CC=C1",  # Benzene
            "INVALID_SMILES"  # Bad SMILES
        ]
        self.valid_smiles = self.smiles_list[:-1]

    def test_compute_morgan_fps(self):
        fps = compute_morgan_fps(self.smiles_list, radius=2, n_bits=1024)
        self.assertEqual(fps.shape, (5, 1024))
        # Valid ones should not be all NaN, invalid should be NaN
        self.assertFalse(np.isnan(fps[0]).any())
        self.assertTrue(np.isnan(fps[-1]).all())

    def test_compute_maccs_fps(self):
        fps = compute_maccs_fps(self.smiles_list)
        self.assertEqual(fps.shape, (5, 167))
        self.assertFalse(np.isnan(fps[0]).any())
        self.assertTrue(np.isnan(fps[-1]).all())

    def test_compute_rdkit_descriptors(self):
        descs = ["MolWt", "MolLogP", "NumHDonors", "Ipc"]
        matrix = compute_rdkit_descriptors(self.smiles_list, descs)
        self.assertEqual(matrix.shape, (5, 4))
        self.assertFalse(np.isnan(matrix[0]).any())
        self.assertTrue(np.isnan(matrix[-1]).all())
        
        # Test individual values
        # Ethanol (CCO) MW is around 46
        self.assertAlmostEqual(matrix[0, 0], 46.07, places=1)
        # Ethanol LogP is around -0.0014 in RDKit
        self.assertAlmostEqual(matrix[0, 1], -0.0014, places=3)

    def test_select_uncorrelated_descriptors(self):
        # Select from valid list to avoid division by zero or NaN issues
        selected = select_uncorrelated_descriptors(self.valid_smiles, threshold=0.9)
        self.assertIsInstance(selected, list)
        self.assertTrue(len(selected) > 0)
        # Ensure selected descriptors are a subset of RDKit descriptors
        for name in selected:
            self.assertIn(name, ALL_DESCRIPTORS_DICT := select_uncorrelated_descriptors.__globals__["ALL_DESCRIPTORS_DICT"])

    def test_featurize_for_baseline(self):
        descs = ["MolWt", "MolLogP", "NumHDonors"]
        X = featurize_for_baseline(self.smiles_list, descs, morgan_radius=2, morgan_nbits=512)
        expected_features = 3 + 512 + 167
        self.assertEqual(X.shape, (5, expected_features))
        self.assertFalse(np.isnan(X[0]).any())
        self.assertTrue(np.isnan(X[-1]).all())

    def test_feature_registry(self):
        descs = ["MolWt", "MolLogP", "NumHDonors"]
        registry = FeatureRegistry(descs, morgan_radius=2, morgan_nbits=512)
        
        dict_rep = registry.to_dict()
        self.assertEqual(dict_rep["descriptors_selected"], sorted(descs))
        self.assertEqual(dict_rep["morgan_nbits"], 512)
        
        loaded = FeatureRegistry.from_dict(dict_rep)
        self.assertEqual(loaded.descriptors_selected, sorted(descs))
        self.assertEqual(loaded.morgan_nbits, 512)
        
        names = registry.get_feature_names()
        expected_len = 3 + 512 + 167
        self.assertEqual(len(names), expected_len)
        self.assertEqual(names[0], "MolLogP")  # Sorted order!
        self.assertEqual(names[3], "morgan_2:0")
        self.assertEqual(names[-1], "maccs:166")

if __name__ == "__main__":
    unittest.main()
