import unittest
import numpy as np
from sklearn.linear_model import Ridge
from edeon_engine.uq import ConformalRegressor, VennAbersCalibrator, get_tanimoto_ad_envelope

class TestUqEngine(unittest.TestCase):

    def test_conformal_regressor_constant_width(self):
        """Verify constant-width conformal prediction intervals."""
        np.random.seed(42)
        X_train = np.random.uniform(0, 10, size=(100, 2))
        y_train = 2.0 * X_train[:, 0] + X_train[:, 1] + np.random.normal(0, 0.2, size=100)
        
        X_cal = np.random.uniform(0, 10, size=(50, 2))
        y_cal = 2.0 * X_cal[:, 0] + X_cal[:, 1] + np.random.normal(0, 0.2, size=50)

        base = Ridge()
        base.fit(X_train, y_train)

        reg = ConformalRegressor(coverage=0.90)
        reg.fit(X_train, y_train, X_cal, y_cal, base, use_adaptive=False)

        self.assertIsNotNone(reg.quantile)
        self.assertFalse(reg.use_adaptive)

        # Predict
        X_test = np.random.uniform(0, 10, size=(10, 2))
        y_pred = base.predict(X_test)
        intervals = reg.predict_intervals(X_test, y_pred)

        self.assertEqual(len(intervals), 10)
        for yp, (low, high) in zip(y_pred, intervals):
            self.assertAlmostEqual(high - yp, yp - low)
            self.assertTrue(low < yp < high)

    def test_conformal_regressor_adaptive(self):
        """Verify adaptive-width conformal prediction intervals."""
        np.random.seed(42)
        X_train = np.random.uniform(0, 10, size=(150, 2))
        # Heteroscedastic noise depending on X[:, 0]
        noise_train = np.random.normal(0, 0.1 * (1.0 + X_train[:, 0]), size=150)
        y_train = 1.5 * X_train[:, 0] + noise_train
        
        X_cal = np.random.uniform(0, 10, size=(80, 2))
        noise_cal = np.random.normal(0, 0.1 * (1.0 + X_cal[:, 0]), size=80)
        y_cal = 1.5 * X_cal[:, 0] + noise_cal

        base = Ridge()
        base.fit(X_train, y_train)

        reg = ConformalRegressor(coverage=0.90)
        reg.fit(X_train, y_train, X_cal, y_cal, base, use_adaptive=True)

        self.assertTrue(reg.use_adaptive)
        self.assertIsNotNone(reg.difficulty_model)

        # Predict on test points with small and large X[:, 0] values
        X_test = np.array([[0.5, 5.0], [9.5, 5.0]])
        y_pred = base.predict(X_test)
        intervals = reg.predict_intervals(X_test, y_pred)

        self.assertEqual(len(intervals), 2)
        width_small = intervals[0][1] - intervals[0][0]
        width_large = intervals[1][1] - intervals[1][0]

        # The interval for X[:, 0] = 9.5 should be wider than for X[:, 0] = 0.5
        self.assertTrue(width_large > width_small)

    def test_venn_abers_calibrator(self):
        """Verify Venn-Abers probability calibration and bounds."""
        np.random.seed(42)
        cal_scores = np.random.uniform(0, 1, size=100)
        # Probabilities match scores roughly
        cal_labels = np.random.binomial(1, cal_scores)

        vac = VennAbersCalibrator()
        vac.fit(cal_scores, cal_labels)

        test_scores = np.array([0.1, 0.5, 0.9])
        calibrated_probs, intervals = vac.predict_calibrated(test_scores)

        self.assertEqual(len(calibrated_probs), 3)
        self.assertEqual(len(intervals), 3)

        for p_cal, (p0, p1) in zip(calibrated_probs, intervals):
            self.assertTrue(0.0 <= p_cal <= 1.0)
            self.assertTrue(0.0 <= p0 <= 1.0)
            self.assertTrue(0.0 <= p1 <= 1.0)
            self.assertTrue(p0 <= p_cal <= p1 or p1 <= p_cal <= p0)

    def test_tanimoto_ad_envelope(self):
        """Verify Tanimoto AD check bounds function."""
        train_smiles = ["CCO", "CCC", "CC", "CCO", "CCCO", "CO"]
        query_smiles = ["CCO", "c1ccccc1"] # Identical, and completely different

        envelopes = get_tanimoto_ad_envelope(query_smiles, train_smiles, k=1, percentile=95)
        self.assertEqual(len(envelopes), 2)

        # First query should be in domain (similarity is 1.0)
        self.assertEqual(envelopes[0]["ad_status"], "in_domain")
        self.assertAlmostEqual(envelopes[0]["ad_score"], 1.0)

        # Second query should be out of domain (similarity is 0.0)
        self.assertEqual(envelopes[1]["ad_status"], "out_of_domain")
        self.assertAlmostEqual(envelopes[1]["ad_score"], 0.0)

if __name__ == "__main__":
    unittest.main()
