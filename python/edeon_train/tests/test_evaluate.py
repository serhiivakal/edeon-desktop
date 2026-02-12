import unittest
import numpy as np
import tempfile
import os
import shutil
import json
from edeon_train.shared.evaluate import (
    compute_regression_metrics,
    compute_ad_and_conformal_stats,
    compute_class_breakdowns,
    generate_validation_report
)
from edeon_models.types import ADStatus

class TestEvaluate(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        
        # Simulated test results for 5 compounds
        self.y_true = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        self.y_pred = np.array([1.1, 1.9, 3.2, 3.8, 5.1])
        
        # Conformal intervals
        self.y_low = self.y_pred - 0.5
        self.y_high = self.y_pred + 0.5
        
        # AD statuses
        self.ad_statuses = [
            ADStatus.IN, ADStatus.IN, 
            ADStatus.BORDERLINE, ADStatus.BORDERLINE,
            ADStatus.OUT
        ]
        self.ad_distances = [0.1, 0.15, 0.45, 0.48, 0.82]
        
        # Smiles (ethanol, caffeine, tebuconazole, carbaryl, glyphosate)
        self.smiles = [
            "CCO",
            "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
            "CC(C)(C)C(O)(CN1C=NC=N1)CC2=CC=C(C=C2)Cl",
            "CNC(=O)OC1=CC=CC2=CC=CC=C21",
            "C(C(=O)O)NCP(=O)(O)O"
        ]

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_compute_regression_metrics(self):
        metrics = compute_regression_metrics(self.y_true, self.y_pred)
        self.assertAlmostEqual(metrics["rmse"], np.sqrt(np.mean((self.y_true - self.y_pred)**2)), places=5)
        self.assertAlmostEqual(metrics["mae"], np.mean(np.abs(self.y_true - self.y_pred)), places=5)
        self.assertTrue(metrics["r2"] > 0.9)
        self.assertIsNotNone(metrics["pearson"])
        self.assertIsNotNone(metrics["spearman"])
        self.assertEqual(metrics["count"], 5)

    def test_compute_ad_and_conformal_stats(self):
        stats = compute_ad_and_conformal_stats(
            self.y_true, self.y_pred, self.y_low, self.y_high, self.ad_statuses, self.ad_distances
        )
        
        # 1.0, 2.0, 3.0, 4.0, 5.0 are all within [y_pred-0.5, y_pred+0.5] (residuals are 0.1, 0.1, 0.2, 0.2, 0.1)
        # So empirical coverage should be 1.0 (100%)
        self.assertEqual(stats["overall_coverage"], 1.0)
        self.assertAlmostEqual(stats["mean_width"], 1.0)
        
        # Check regions breakdown
        self.assertIn("in", stats["regions"])
        self.assertIn("borderline", stats["regions"])
        self.assertIn("out", stats["regions"])
        
        self.assertEqual(stats["regions"]["in"]["count"], 2)
        self.assertEqual(stats["regions"]["borderline"]["count"], 2)
        self.assertEqual(stats["regions"]["out"]["count"], 1)

    def test_compute_class_breakdowns(self):
        class_stats = compute_class_breakdowns(
            self.smiles, self.y_true, self.y_pred, self.y_low, self.y_high, self.ad_statuses
        )
        
        # Tebuconazole matches "triazole" (index 2)
        self.assertIn("triazole", class_stats)
        self.assertEqual(class_stats["triazole"]["count"], 1)
        self.assertAlmostEqual(class_stats["triazole"]["rmse"], 0.2, places=4) # True 3.0, Pred 3.2
        
        # Carbaryl matches "carbamate" (index 3)
        self.assertIn("carbamate", class_stats)
        self.assertEqual(class_stats["carbamate"]["count"], 1)
        self.assertAlmostEqual(class_stats["carbamate"]["rmse"], 0.2, places=4) # True 4.0, Pred 3.8

    def test_generate_validation_report(self):
        report = generate_validation_report(
            endpoint_id="bee_acute_oral_ld50",
            y_true_test=self.y_true,
            y_pred_test=self.y_pred,
            y_low_test=self.y_low,
            y_high_test=self.y_high,
            ad_statuses_test=self.ad_statuses,
            ad_distances_test=self.ad_distances,
            smiles_test=self.smiles,
            train_samples=100,
            cal_samples=25,
            cv_train_rmse=0.45,
            cal_rmse=0.48,
            cal_r2=0.65,
            output_dir=self.temp_dir
        )
        
        # Check return dict
        self.assertEqual(report["endpoint_id"], "bee_acute_oral_ld50")
        self.assertEqual(report["train_samples"], 100)
        self.assertEqual(report["test_samples"], 5)
        
        # Verify JSON exists and matches
        json_path = os.path.join(self.temp_dir, "validation_report.json")
        self.assertTrue(os.path.exists(json_path))
        with open(json_path, "r") as f:
            saved_json = json.load(f)
        self.assertEqual(saved_json["endpoint_id"], "bee_acute_oral_ld50")
        self.assertAlmostEqual(saved_json["overall"]["rmse"], report["overall"]["rmse"])
        
        # Verify HTML exists and is compiled
        html_path = os.path.join(self.temp_dir, "validation_report.html")
        self.assertTrue(os.path.exists(html_path))
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        self.assertIn("<title>Edeon Tier-1 Model Validation Report - bee_acute_oral_ld50</title>", html_content)
        self.assertIn("TRIAZOLE", html_content)
        self.assertIn("CARBAMATE", html_content)

if __name__ == "__main__":
    unittest.main()
