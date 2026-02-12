import unittest
import numpy as np
from edeon_models.uq.base import UQStrategy
from edeon_models.uq.conformal import ConformalUQ
from edeon_models.uq.ensemble import EnsembleVarianceUQ

class TestUQ(unittest.TestCase):
    
    def test_direct_instantiation_of_base_fails(self):
        """Assert that UQStrategy ABC raises TypeError on direct instantiation."""
        with self.assertRaises(TypeError):
            UQStrategy()
            
    def test_conformal_uq_calibration_and_empirical_coverage(self):
        """Assert that ConformalUQ satisfies the empirical coverage guarantee (>= 90% coverage for 95% CI)."""
        np.random.seed(42)
        
        # 1. Generate synthetic calibration dataset (n = 500)
        # Residuals follow normal distribution with sigma = 0.5
        n_cal = 500
        y_true_cal = np.random.uniform(1.0, 10.0, n_cal)
        residuals_cal = np.random.normal(0, 0.5, n_cal)
        y_pred_cal = y_true_cal + residuals_cal
        
        uq = ConformalUQ(alpha=0.05) # 95% CI
        uq.calibrate(y_pred_cal, y_true_cal)
        
        self.assertIsInstance(uq.quantile, float)
        self.assertTrue(uq.quantile > 0.0)
        
        # 2. Evaluate empirical coverage on a separate test set (n = 500)
        n_test = 500
        y_true_test = np.random.uniform(1.0, 10.0, n_test)
        residuals_test = np.random.normal(0, 0.5, n_test)
        y_pred_test = y_true_test + residuals_test
        
        inside_count = 0
        for yt, yp in zip(y_true_test, y_pred_test):
            lower, upper = uq.interval(yp)
            self.assertTrue(lower < yp < upper)
            if lower <= yt <= upper:
                inside_count += 1
                
        empirical_coverage = inside_count / n_test
        print(f"Empirical Coverage of ConformalUQ: {empirical_coverage * 100.0:.2f}%")
        
        # Split conformal prediction theoretically guarantees (1 - alpha) coverage in expectation,
        # so for alpha = 0.05, coverage should be >= 90% (ideally very close to 95%).
        self.assertTrue(empirical_coverage >= 0.90)

    def test_ensemble_variance_uq_default_std(self):
        """Verify that EnsembleVarianceUQ correctly calibrates default standard error scaling."""
        np.random.seed(42)
        
        # 100 compounds, 5 ensemble members
        n_samples = 100
        n_members = 5
        
        # Synthetic ensemble predictions centered around true values with variance
        preds_ensemble = np.random.normal(5.0, 0.6, size=(n_samples, n_members))
        y_true = np.random.normal(5.0, 0.1, size=n_samples)
        
        uq = EnsembleVarianceUQ(z=1.96) # 95% confidence bounds
        uq.calibrate(preds_ensemble, y_true)
        
        self.assertIsInstance(uq.default_std, float)
        self.assertTrue(uq.default_std > 0.0)
        
        # Verify interval calculation under default std
        lower, upper = uq.interval(5.0)
        self.assertAlmostEqual(lower, 5.0 - 1.96 * uq.default_std)
        self.assertAlmostEqual(upper, 5.0 + 1.96 * uq.default_std)

    def test_ensemble_variance_uq_local_smiles_std(self):
        """Verify that EnsembleVarianceUQ maps and executes localized standard deviations properly."""
        uq = EnsembleVarianceUQ(z=2.0)
        uq.default_std = 0.5
        
        smiles_key = "CCO"
        uq.set_ensemble_std(smiles_key, 0.2)
        
        # 1. Standard default interval (no smiles or smiles not found)
        lower_def, upper_def = uq.interval(10.0)
        self.assertEqual(lower_def, 9.0) # 10.0 - 2 * 0.5
        self.assertEqual(upper_def, 11.0) # 10.0 + 2 * 0.5
        
        # 2. Local smiles-mapped interval (smiles found in store)
        lower_local, upper_local = uq.interval(10.0, smiles=smiles_key)
        self.assertEqual(lower_local, 9.6) # 10.0 - 2 * 0.2
        self.assertEqual(upper_local, 10.4) # 10.0 + 2 * 0.2

if __name__ == "__main__":
    unittest.main()
