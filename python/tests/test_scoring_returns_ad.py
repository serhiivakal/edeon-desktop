import unittest
import numpy as np
from sklearn.linear_model import Ridge
from edeon_engine.scoring import predict, QSARModelHandle, _confidence_from_status
from edeon_engine.applicability import build_ad_reference

class MockEstimator:
    def predict(self, X):
        return np.ones(len(X))

class TestScoringReturnsAD(unittest.TestCase):
    def setUp(self):
        self.train_smiles = ["CCO", "CCC", "CCCC", "CCCCC", "CCCCCC"]
        self.X_train = np.array([
            [1.0, 2.0],
            [1.1, 2.1],
            [1.2, 2.2],
            [1.3, 2.3],
            [1.4, 2.4]
        ])
        self.y_train = np.array([1.0, 1.2, 1.4, 1.6, 1.8])
        self.y_train_pred = np.array([0.9, 1.3, 1.3, 1.7, 1.7])
        
        # Build valid AD reference
        self.ad = build_ad_reference(self.train_smiles, self.X_train, self.y_train, self.y_train_pred)
        
    def test_predict_returns_ad_keys(self):
        estimator = MockEstimator()
        selections = [{"id": "descriptors_2d", "params": {"selected": ["MW", "LogP"]}}]
        
        handle = QSARModelHandle(
            estimator=estimator,
            featurizer_selections=selections,
            ad=self.ad
        )
        
        # Test predict with a mix of in, out, and invalid SMILES
        queries = ["CCO", "c1ccccc1", "INVALID_SMILES"]
        results = predict(handle, queries)
        
        self.assertEqual(len(results), 3)
        for res in results:
            self.assertIn("ad_status", res)
            self.assertIn("ad_confidence", res)
            self.assertIn(res["ad_status"], ["in", "borderline", "out", "invalid"])
            self.assertIsInstance(res["ad_confidence"], float)

    def test_ad_confidence_ordering(self):
        # ad_confidence ordering check: "out" < "borderline" < "in"
        conf_in = _confidence_from_status("in")
        conf_borderline = _confidence_from_status("borderline")
        conf_out = _confidence_from_status("out")
        conf_invalid = _confidence_from_status("invalid")
        
        self.assertTrue(conf_out < conf_borderline < conf_in)
        self.assertEqual(conf_in, 1.0)
        self.assertEqual(conf_borderline, 0.6)
        self.assertEqual(conf_out, 0.2)
        self.assertEqual(conf_invalid, 0.0)

if __name__ == "__main__":
    unittest.main()
