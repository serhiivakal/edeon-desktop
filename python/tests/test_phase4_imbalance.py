import unittest
import numpy as np
from collections import Counter
from edeon_engine.models.imbalance import apply_imbalance_strategy
from edeon_engine.models.trainers import train_model_batch
from edeon_engine.models.validation import kfold_cv

class TestImbalanceMitigation(unittest.TestCase):
    def setUp(self):
        # High imbalance dataset: 90 of class 0, 10 of class 1
        self.X = np.random.randn(100, 10).tolist()
        self.y = ([0] * 90) + ([1] * 10)
        self.smiles = ["CC" for _ in range(100)]

    def test_apply_strategy_none(self):
        Xr, yr, cw = apply_imbalance_strategy(self.X, self.y, "none", 42)
        self.assertEqual(len(Xr), 100)
        self.assertEqual(len(yr), 100)
        self.assertIsNone(cw)

    def test_apply_strategy_class_weight(self):
        Xr, yr, cw = apply_imbalance_strategy(self.X, self.y, "class_weight", 42)
        self.assertEqual(len(Xr), 100)
        self.assertEqual(len(yr), 100)
        self.assertIsNotNone(cw)
        self.assertIn(0, cw)
        self.assertIn(1, cw)
        # Class 1 should have higher weight since it is minority
        self.assertGreater(cw[1], cw[0])

    def test_apply_strategy_smote(self):
        Xr, yr, cw = apply_imbalance_strategy(self.X, self.y, "smote", 42)
        counts = Counter(yr)
        self.assertEqual(counts[0], counts[1])  # Should be perfectly balanced
        self.assertEqual(counts[0], 90)
        self.assertEqual(len(Xr), 180)
        self.assertIsNone(cw)

    def test_apply_strategy_undersample(self):
        Xr, yr, cw = apply_imbalance_strategy(self.X, self.y, "undersample", 42)
        counts = Counter(yr)
        self.assertEqual(counts[0], counts[1])  # Should be perfectly balanced
        self.assertEqual(counts[0], 10)
        self.assertEqual(len(Xr), 20)
        self.assertIsNone(cw)

    def test_apply_strategy_invalid(self):
        with self.assertRaises(ValueError):
            apply_imbalance_strategy(self.X, self.y, "invalid_strategy", 42)

    def test_kfold_cv_with_imbalance(self):
        config = {
            "model_type": "classification",
            "imbalance_strategy": "smote",
            "hyperparameters": {
                "n_estimators": 10,
                "max_depth": 3
            }
        }
        # Run 3-fold cross validation
        cv_res = kfold_cv(self.X, self.y, self.smiles, k=3, split_mode="random", random_state=42, model_type="classification", algorithm="rf", config=config)
        self.assertIsNotNone(cv_res)
        self.assertGreater(len(cv_res), 0)
        # Verify that summary dictionary is present
        self.assertEqual(cv_res[-1]["fold"], "summary")
        self.assertGreater(cv_res[-1]["mean"], 0.0)

if __name__ == "__main__":
    unittest.main()
