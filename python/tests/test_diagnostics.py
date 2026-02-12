import unittest
import numpy as np
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from edeon_engine.diagnostics.regression import regression_diagnostics
from edeon_engine.diagnostics.classification import classification_diagnostics

class TestDiagnosticsSuite(unittest.TestCase):
    def setUp(self):
        self.random_state = 42
        
    def test_regression_diagnostics(self):
        # Generate dummy data
        np.random.seed(self.random_state)
        X_train = np.random.randn(50, 4)
        y_train = X_train[:, 0] * 2.0 + np.random.randn(50) * 0.1
        
        # Fit a simple estimator
        estimator = RandomForestRegressor(n_estimators=5, random_state=self.random_state)
        estimator.fit(X_train, y_train)
        
        # Validation outputs
        y_true = y_train[:15]
        y_pred = estimator.predict(X_train[:15])
        y_train_pred = estimator.predict(X_train)
        
        # Build fake AD status and y-scramble
        ad_status = ["in"] * 12 + ["borderline"] * 2 + ["out"] * 1
        scramble_distribution = {
            "scrambled_scores": [0.1, 0.05, 0.12, -0.02, 0.01],
            "true_score": 0.85,
            "p_value": 0.0
        }
        
        # Compute diagnostics
        diags = regression_diagnostics(
            y_true=y_true,
            y_pred=y_pred,
            y_train=y_train,
            y_train_pred=y_train_pred,
            ad_status=ad_status,
            scramble_distribution=scramble_distribution,
            estimator=estimator,
            X_train=X_train,
            y_train_arr=y_train,
            cv_k=3,
            random_state=self.random_state
        )
        
        # Check presence of required regression keys
        self.assertIn("parity", diags)
        self.assertIn("residuals_vs_fitted", diags)
        self.assertIn("residual_histogram", diags)
        self.assertIn("qq", diags)
        self.assertIn("learning_curve", diags)
        self.assertIn("y_scramble", diags)
        
        # Validate parity plot
        self.assertEqual(len(diags["parity"]["points"]), 15)
        self.assertEqual(diags["parity"]["points"][14]["ad"], "out")
        
        # Validate Q-Q
        self.assertEqual(len(diags["qq"]), 15)
        self.assertTrue(all("theoretical" in p and "sample" in p for p in diags["qq"]))
        
        # Validate Residual Histogram
        self.assertEqual(len(diags["residual_histogram"]), 20)
        self.assertTrue(all("normal_fit" in b and "count" in b for b in diags["residual_histogram"]))
        
        # Validate scramble
        self.assertEqual(diags["y_scramble"]["p_value"], 0.0)

    def test_classification_diagnostics(self):
        np.random.seed(self.random_state)
        X_train = np.random.randn(60, 4)
        y_train = np.array([0, 1] * 30)
        X_train[:, 0] = y_train * 2.0 + np.random.randn(60) * 0.5
        
        estimator = RandomForestClassifier(n_estimators=5, random_state=self.random_state)
        estimator.fit(X_train, y_train)
        
        # Validation outputs
        y_true = y_train[:20]
        y_pred = estimator.predict(X_train[:20])
        probas = estimator.predict_proba(X_train[:20])
        y_proba = probas[:, 1]
        
        # Fake cv predictions (5 folds containing both classes, with slight distinct variances to guarantee non-zero band widths)
        cv_fold_predictions = [
            {"y_true": [0, 1, 0, 1, 0, 1, 0, 1, 0, 1], "y_proba": [0.1, 0.8, 0.4, 0.6, 0.2, 0.9, 0.7, 0.5, 0.3, 0.8]},
            {"y_true": [0, 1, 0, 1, 0, 1, 0, 1, 0, 1], "y_proba": [0.3, 0.6, 0.2, 0.8, 0.4, 0.7, 0.5, 0.9, 0.1, 0.6]},
            {"y_true": [0, 1, 0, 1, 0, 1, 0, 1, 0, 1], "y_proba": [0.2, 0.9, 0.1, 0.7, 0.5, 0.6, 0.3, 0.8, 0.4, 0.5]},
            {"y_true": [0, 1, 0, 1, 0, 1, 0, 1, 0, 1], "y_proba": [0.4, 0.5, 0.3, 0.9, 0.1, 0.8, 0.6, 0.7, 0.2, 0.6]},
            {"y_true": [0, 1, 0, 1, 0, 1, 0, 1, 0, 1], "y_proba": [0.1, 0.7, 0.5, 0.6, 0.3, 0.9, 0.2, 0.8, 0.4, 0.7]},
        ]
        
        # Compute diagnostics
        diags = classification_diagnostics(
            y_true=y_true,
            y_pred=y_pred,
            y_proba=y_proba,
            cv_fold_predictions=cv_fold_predictions,
            estimator=estimator,
            X_train=X_train,
            y_train_arr=y_train,
            cv_k=5,
            random_state=self.random_state
        )
        
        # Check presence of required classification keys
        self.assertIn("confusion_matrix", diags)
        self.assertIn("roc", diags)
        self.assertIn("pr", diags)
        self.assertIn("calibration", diags)
        self.assertIn("threshold_sweep", diags)
        self.assertIn("probability_histogram", diags)
        self.assertIn("learning_curve", diags)
        
        # Validate confusion matrix
        self.assertIn("tp", diags["confusion_matrix"])
        self.assertEqual(diags["confusion_matrix"]["total"], 20)
        
        # Validate interpolated ROC CI and assert band widths > 0
        self.assertEqual(len(diags["roc"]["points"]), 100)
        self.assertTrue(all("fpr" in p and "tpr_min" in p and "tpr_max" in p for p in diags["roc"]["points"]))
        self.assertTrue(any(p["tpr_max"] - p["tpr_min"] > 0.0 for p in diags["roc"]["points"]))
        
        # Validate Threshold Sweep and assert monotonic threshold values
        self.assertEqual(len(diags["threshold_sweep"]), 50)
        self.assertAlmostEqual(diags["threshold_sweep"][0]["threshold"], 0.01)
        self.assertAlmostEqual(diags["threshold_sweep"][-1]["threshold"], 0.99)
        self.assertTrue(all(diags["threshold_sweep"][idx]["threshold"] < diags["threshold_sweep"][idx+1]["threshold"] for idx in range(49)))
        self.assertTrue(all("f1" in s and "tp" in s for s in diags["threshold_sweep"]))
        
        # Validate Probability Histograms
        self.assertEqual(len(diags["probability_histogram"]["positive"]), 20)
        self.assertEqual(len(diags["probability_histogram"]["negative"]), 20)

if __name__ == "__main__":
    unittest.main()
