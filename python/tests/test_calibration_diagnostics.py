"""Unit tests for Edeon model calibration diagnostics."""
import unittest
from edeon_models import build_default_registry, Endpoint
from edeon_models.diagnostics import get_calibration_diagnostics

class TestCalibrationDiagnostics(unittest.TestCase):
    def setUp(self):
        self.registry = build_default_registry()

    def test_regression_diagnostics(self):
        # Find any Tier-1 regression model in the registry
        reg_model_id = None
        for endpoint in Endpoint:
            backends = self.registry.list_for_endpoint(endpoint)
            for b in backends:
                if b.tier() == 1 and getattr(b, "_conformal", None) is None:  # Regression (no classification conformal)
                    # Note: TrainedTier1Backend has no _conformal (it has UQ but classification has self._conformal)
                    # Let's check metadata or task kind if available, or just check the ID/model card
                    card = b.metadata()
                    # Check if algae_growth_ec50 is registered as Tier-1
                    if "algae_growth" in card.model_id or "soil_koc" in card.model_id:
                        reg_model_id = card.model_id
                        break
            if reg_model_id:
                break

        if not reg_model_id:
            # Fall back to checking any Tier-1 model that doesn't have "cls" in its path or card
            for endpoint in Endpoint:
                backends = self.registry.list_for_endpoint(endpoint)
                for b in backends:
                    if b.tier() == 1:
                        card = b.metadata()
                        if "cls" not in card.model_id and "sensitization" not in card.model_id and "irritation" not in card.model_id:
                            reg_model_id = card.model_id
                            break
                if reg_model_id:
                    break

        if reg_model_id:
            print(f"Testing regression diagnostics on: {reg_model_id}")
            diags = get_calibration_diagnostics(reg_model_id)
            self.assertEqual(diags["model_id"], reg_model_id)
            self.assertEqual(diags["task_kind"], "regression")
            
            # Check regression specific schemas
            self.assertIsNotNone(diags["parity_data"])
            self.assertIsNotNone(diags["calibration_curve"])
            self.assertIsNotNone(diags["residual_distribution"])
            
            # Check that points contain expected keys
            parity_points = diags["parity_data"]["points"]
            self.assertGreater(len(parity_points), 0)
            self.assertIn("observed", parity_points[0])
            self.assertIn("predicted", parity_points[0])
            self.assertIn("smiles", parity_points[0])
            self.assertIn("ad_status", parity_points[0])
            self.assertIn("ci_lower", parity_points[0])
            self.assertIn("ci_upper", parity_points[0])

            # Calibration curve expected vs actual
            cal_points = diags["calibration_curve"]["points"]
            self.assertGreater(len(cal_points), 0)
            self.assertIn("expected", cal_points[0])
            self.assertIn("actual", cal_points[0])

            # Residuals distribution bins
            res_bins = diags["residual_distribution"]["bins"]
            self.assertEqual(len(res_bins), 20)
            self.assertIn("bin_start", res_bins[0])
            self.assertIn("bin_center", res_bins[0])
            self.assertIn("count", res_bins[0])
            
            # Applicability Domain
            self.assertIn("ad_distance_histogram", diags)
            ad_hist = diags["ad_distance_histogram"]
            self.assertIn("train_distances", ad_hist)
            self.assertIn("in_threshold", ad_hist)
            self.assertIn("out_threshold", ad_hist)
            self.assertGreater(len(ad_hist["train_distances"]), 0)
        else:
            self.skipTest("No Tier-1 regression reference model checkpoints found.")

    def test_classification_diagnostics(self):
        # Find any Tier-1 classification model in the registry
        cls_model_id = None
        for endpoint in Endpoint:
            backends = self.registry.list_for_endpoint(endpoint)
            for b in backends:
                if b.tier() == 1:
                    card = b.metadata()
                    if "cls" in card.model_id or "sensitization" in card.model_id or "irritation" in card.model_id:
                        cls_model_id = card.model_id
                        break
            if cls_model_id:
                break

        if cls_model_id:
            print(f"Testing classification diagnostics on: {cls_model_id}")
            diags = get_calibration_diagnostics(cls_model_id)
            self.assertEqual(diags["model_id"], cls_model_id)
            self.assertEqual(diags["task_kind"], "classification")
            
            # Check classification specific schemas
            self.assertIsNotNone(diags["roc_curve"])
            self.assertIsNotNone(diags["pr_curve"])
            self.assertIsNotNone(diags["reliability_diagram"])
            self.assertIsNotNone(diags["confusion_matrix"])
            
            # Check ROC curve points
            roc_points = diags["roc_curve"]["points"]
            self.assertGreater(len(roc_points), 0)
            self.assertIn("fpr", roc_points[0])
            self.assertIn("tpr", roc_points[0])
            self.assertIn("auc", diags["roc_curve"])

            # Check PR curve points
            pr_points = diags["pr_curve"]["points"]
            self.assertGreater(len(pr_points), 0)
            self.assertIn("precision", pr_points[0])
            self.assertIn("recall", pr_points[0])
            self.assertIn("auc", diags["pr_curve"])

            # Check Reliability Diagram bins
            rel_bins = diags["reliability_diagram"]["bins"]
            self.assertGreater(len(rel_bins), 0)
            self.assertIn("bin_start", rel_bins[0])
            self.assertIn("avg_predicted", rel_bins[0])
            self.assertIn("avg_actual", rel_bins[0])

            # Confusion Matrix should be 2x2
            cm = diags["confusion_matrix"]
            self.assertEqual(len(cm), 2)
            self.assertEqual(len(cm[0]), 2)
            
            # Applicability Domain
            self.assertIn("ad_distance_histogram", diags)
            ad_hist = diags["ad_distance_histogram"]
            self.assertIn("train_distances", ad_hist)
            self.assertIn("in_threshold", ad_hist)
            self.assertIn("out_threshold", ad_hist)
            self.assertGreater(len(ad_hist["train_distances"]), 0)
        else:
            self.skipTest("No Tier-1 classification reference model checkpoints found.")

    def test_legacy_baseline_unsupported(self):
        # List baseline (Tier-2) models
        t2_model_id = None
        for endpoint in Endpoint:
            backends = self.registry.list_for_endpoint(endpoint)
            for b in backends:
                if b.tier() == 2:
                    t2_model_id = b.metadata().model_id
                    break
            if t2_model_id:
                break
        
        if t2_model_id:
            with self.assertRaises(ValueError) as context:
                get_calibration_diagnostics(t2_model_id)
            self.assertIn("Diagnostics are not supported for legacy baseline (Tier-2) models", str(context.exception))
        else:
            self.skipTest("No Tier-2 baseline models found in registry.")

    def test_nonexistent_model_id(self):
        with self.assertRaises(ValueError):
            get_calibration_diagnostics("invalid_model_id_123")

if __name__ == "__main__":
    unittest.main()
