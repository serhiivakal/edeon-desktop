import unittest
import numpy as np
import tempfile
import os
import shutil
from unittest.mock import MagicMock, patch
from edeon_train.shared.ensemble import WeightedEnsemble

class TestEnsemble(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        
        # Simulated CV RMSEs
        self.cv_rmses_normal = {"rf": 0.5, "xgb": 0.4, "chemprop": 0.6}
        self.cv_rmses_drop = {"rf": 0.5, "xgb": 0.4, "chemprop": 1.2}  # 1.2 > 2 * 0.4 (0.8) -> Should drop chemprop
        
        self.smiles = ["CCO", "CCC", "INVALID_SMILES"]
        self.features = np.array([
            [1.0, 2.0],
            [1.5, 2.5],
            [np.nan, np.nan]
        ])

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_from_cv_metrics(self):
        # 1. Normal case
        ensemble = WeightedEnsemble.from_cv_metrics(self.cv_rmses_normal)
        self.assertIn("rf", ensemble.weights)
        self.assertIn("xgb", ensemble.weights)
        self.assertIn("chemprop", ensemble.weights)
        
        # Check normalization
        self.assertAlmostEqual(sum(ensemble.weights.values()), 1.0)
        
        # Inverse weight relationship: xgb should have highest weight
        self.assertTrue(ensemble.weights["xgb"] > ensemble.weights["rf"])
        self.assertTrue(ensemble.weights["rf"] > ensemble.weights["chemprop"])
        
        # 2. Drop chemprop case
        ensemble_drop = WeightedEnsemble.from_cv_metrics(self.cv_rmses_drop)
        self.assertIn("rf", ensemble_drop.weights)
        self.assertIn("xgb", ensemble_drop.weights)
        self.assertNotIn("chemprop", ensemble_drop.weights)
        self.assertAlmostEqual(sum(ensemble_drop.weights.values()), 1.0)

    @patch("edeon_train.shared.ensemble.predict_chemprop_ensemble")
    def test_predict_weighted_combination(self, mock_predict_chemprop):
        # Mock RF and XGBoost models
        rf_mock = MagicMock()
        rf_mock.predict.return_value = np.array([10.0, 20.0])
        
        xgb_mock = MagicMock()
        xgb_mock.predict.return_value = np.array([12.0, 18.0])
        
        # Mock Chemprop predict
        mock_predict_chemprop.return_value = (np.array([8.0, 22.0, np.nan]), np.array([0.1, 0.2, np.nan]))
        
        # Build ensemble with equal weights (1/3 each)
        weights = {"rf": 0.33333333, "xgb": 0.33333333, "chemprop": 0.33333334}
        ensemble = WeightedEnsemble(
            weights=weights,
            rf_model=rf_mock,
            xgb_model=xgb_mock,
            chemprop_dir="mock_dir"
        )
        
        preds = ensemble.predict(self.smiles, self.features)
        
        # Check length
        self.assertEqual(len(preds), 3)
        
        # Expected values:
        # Index 0: 1/3 * 10 + 1/3 * 12 + 1/3 * 8 = 10.0
        # Index 1: 1/3 * 20 + 1/3 * 18 + 1/3 * 22 = 20.0
        # Index 2: invalid feature row -> NaN
        self.assertAlmostEqual(preds[0], 10.0, places=4)
        self.assertAlmostEqual(preds[1], 20.0, places=4)
        self.assertTrue(np.isnan(preds[2]))
        
        # Confirm mocks were called
        # Only valid indices should have been passed to rf and xgb predict
        rf_mock.predict.assert_called_once()
        xgb_mock.predict.assert_called_once()

    def test_save_and_load_roundtrip(self):
        weights = {"rf": 0.4, "xgb": 0.6}
        ensemble = WeightedEnsemble(weights=weights)
        
        weights_path = os.path.join(self.temp_dir, "ensemble_weights.yaml")
        ensemble.save(weights_path)
        
        self.assertTrue(os.path.exists(weights_path))
        
        # Mock sub-checkpoints for load
        os.makedirs(os.path.join(self.temp_dir, "baselines"))
        
        # Mock load_baseline_checkpoint
        with patch("edeon_train.shared.ensemble.load_baseline_checkpoint") as mock_load_baseline:
            mock_load_baseline.return_value = (MagicMock(), {})
            
            loaded_ensemble = WeightedEnsemble.load(self.temp_dir)
            self.assertEqual(loaded_ensemble.weights["rf"], 0.4)
            self.assertEqual(loaded_ensemble.weights["xgb"], 0.6)
            self.assertIsNotNone(loaded_ensemble.rf_model)
            self.assertIsNotNone(loaded_ensemble.xgb_model)

if __name__ == "__main__":
    unittest.main()
