import unittest
import numpy as np
import tempfile
import os
import shutil
from edeon_train.shared.conformal import (
    SplitConformalRegressor,
    EnsembleVarianceCalibrator,
    save_calibration,
    load_calibration
)

class TestConformal(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        
        # Simulate validation data (1000 samples)
        np.random.seed(42)
        self.n_samples = 1000
        
        self.y_true_cal = np.random.randn(self.n_samples)
        # Heteroscedastic noise: validation standard deviations are input-dependent
        self.y_std_cal = np.random.uniform(0.1, 2.0, self.n_samples)
        # Predictions with standard deviations scaled
        self.y_pred_cal = self.y_true_cal + np.random.normal(0, self.y_std_cal)
        
        # Test set (500 samples)
        self.y_true_test = np.random.randn(500)
        self.y_std_test = np.random.uniform(0.1, 2.0, 500)
        self.y_pred_test = self.y_true_test + np.random.normal(0, self.y_std_test)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_split_conformal_coverage(self):
        # We want 95% coverage (alpha = 0.05)
        cal = SplitConformalRegressor(alpha=0.05)
        cal.calibrate(self.y_pred_cal, self.y_true_cal)
        
        self.assertIsNotNone(cal.quantile_)
        self.assertTrue(cal.quantile_ > 0)
        
        coverage = cal.empirical_coverage(self.y_pred_test, self.y_true_test)
        # Should be approximately 95% (loosely between 90% and 98% given mock random data)
        self.assertTrue(0.90 <= coverage <= 0.98, f"Coverage was {coverage}")
        
        width = cal.mean_width(self.y_pred_test)
        self.assertTrue(width > 0)

    def test_variance_scaled_conformal_coverage(self):
        cal = EnsembleVarianceCalibrator(alpha=0.05)
        cal.calibrate(self.y_pred_cal, self.y_true_cal, self.y_std_cal)
        
        self.assertIsNotNone(cal.quantile_)
        self.assertTrue(cal.quantile_ > 0)
        
        coverage = cal.empirical_coverage(self.y_pred_test, self.y_true_test, self.y_std_test)
        # Should be approximately 95%
        self.assertTrue(0.90 <= coverage <= 0.98, f"Coverage was {coverage}")
        
        width = cal.mean_width(self.y_pred_test, self.y_std_test)
        self.assertTrue(width > 0)

    def test_save_load_roundtrip(self):
        split_cal = SplitConformalRegressor(alpha=0.05)
        split_cal.calibrate(self.y_pred_cal, self.y_true_cal)
        
        var_cal = EnsembleVarianceCalibrator(alpha=0.1)
        var_cal.calibrate(self.y_pred_cal, self.y_true_cal, self.y_std_cal)
        
        path = os.path.join(self.temp_dir, "calibration.npz")
        save_calibration(split_cal, var_cal, path)
        
        self.assertTrue(os.path.exists(path))
        
        loaded_split, loaded_var = load_calibration(path)
        
        self.assertEqual(loaded_split.alpha, split_cal.alpha)
        self.assertAlmostEqual(loaded_split.quantile_, split_cal.quantile_)
        
        self.assertEqual(loaded_var.alpha, var_cal.alpha)
        self.assertAlmostEqual(loaded_var.quantile_, var_cal.quantile_)
        
        # Test that intervals match exactly
        orig_lo, orig_hi = var_cal.interval(self.y_pred_test, self.y_std_test)
        loaded_lo, loaded_hi = loaded_var.interval(self.y_pred_test, self.y_std_test)
        
        np.testing.assert_allclose(orig_lo, loaded_lo)
        np.testing.assert_allclose(orig_hi, loaded_hi)

if __name__ == "__main__":
    unittest.main()
