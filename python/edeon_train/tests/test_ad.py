import unittest
import numpy as np
import tempfile
import os
import shutil
from edeon_train.shared.ad import TrainedTanimotoAD
from edeon_models.types import ADStatus

class TestAD(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        
        # Training smiles (all closely related structurally - alkanes)
        self.train_smiles = [
            "CC", "CCC", "CCCC", "CCCCC", "CCCCCC", 
            "CCCCCCC", "CCCCCCCC", "CCCCCCCCC", "CCCCCCCCCC"
        ]
        # Query smiles:
        # 1. Close to training (pentane) -> should be IN
        # 2. Borderline / further (branched or slightly larger) -> BORDERLINE
        # 3. Very far from training (caffeine) -> should be OUT
        # 4. Invalid -> UNKNOWN
        self.queries = [
            "CCCCC",
            "CC(C)CC(C)C",
            "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
            "INVALID_SMILES"
        ]

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_ad_fit_and_score(self):
        ad = TrainedTanimotoAD.from_training_smiles(
            self.train_smiles, k=3, radius=2, nbits=512
        )
        
        self.assertEqual(ad.k, 3)
        self.assertEqual(ad.radius, 2)
        self.assertEqual(ad.nbits, 512)
        self.assertTrue(ad.in_threshold > 0)
        self.assertTrue(ad.out_threshold >= ad.in_threshold)
        
        results = ad.score(self.queries)
        self.assertEqual(len(results), 4)
        
        # pentane should be IN
        self.assertEqual(results[0][0], ADStatus.IN)
        self.assertTrue(results[0][1] >= 0.0)
        
        # caffeine should be OUT
        self.assertEqual(results[2][0], ADStatus.OUT)
        
        # invalid smiles should be UNKNOWN
        self.assertEqual(results[3][0], ADStatus.UNKNOWN)
        self.assertIsNone(results[3][1])

    def test_ad_save_and_load(self):
        ad = TrainedTanimotoAD.from_training_smiles(
            self.train_smiles, k=3, radius=2, nbits=512
        )
        
        path = os.path.join(self.temp_dir, "ad_fingerprints.npz")
        ad.save(path)
        
        self.assertTrue(os.path.exists(path))
        
        loaded_ad = TrainedTanimotoAD.load(path)
        
        self.assertEqual(loaded_ad.k, ad.k)
        self.assertEqual(loaded_ad.radius, ad.radius)
        self.assertEqual(loaded_ad.nbits, ad.nbits)
        self.assertAlmostEqual(loaded_ad.in_threshold, ad.in_threshold)
        self.assertAlmostEqual(loaded_ad.out_threshold, ad.out_threshold)
        
        # Assert same score outputs
        orig_scores = ad.score(self.queries)
        loaded_scores = loaded_ad.score(self.queries)
        
        for orig, loaded in zip(orig_scores, loaded_scores):
            self.assertEqual(orig[0], loaded[0])
            if orig[1] is not None:
                self.assertAlmostEqual(orig[1], loaded[1])
            else:
                self.assertIsNone(loaded[1])

if __name__ == "__main__":
    unittest.main()
