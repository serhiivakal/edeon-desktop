import unittest
import numpy as np
import pickle

from sklearn.linear_model import Ridge

from edeon_engine.applicability.tanimoto import build_tanimoto_reference, score_tanimoto
from edeon_engine.applicability.leverage import build_leverage_reference, score_leverage
from edeon_engine.applicability.williams import williams_plot_data
from edeon_engine.applicability import build_ad_reference, score_query, ApplicabilityDomain
from edeon_engine.scoring import predict, QSARModelHandle


class MockEstimator:
    def __init__(self):
        pass
    def predict(self, X):
        return np.array([1.5] * len(X))


class TestApplicabilityDomain(unittest.TestCase):
    def setUp(self):
        # Create a set of highly similar training smiles
        self.train_smiles = [
            "CCO", "CCC", "CCCC", "CCCCC", "CCCCCC", "CCCCCCC", "CCCCCCCC"
        ]
        # X_train with 2 features (low sparsity < 70%)
        self.X_train = np.array([
            [1.0, 2.0],
            [1.1, 2.1],
            [1.2, 2.2],
            [1.3, 2.3],
            [1.4, 2.4],
            [1.5, 2.5],
            [1.6, 2.6]
        ])
        self.y_train = np.array([1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.2])
        self.y_train_pred = np.array([0.9, 1.3, 1.3, 1.7, 1.7, 2.1, 2.1])

    def test_tanimoto_ad_reference(self):
        ref = build_tanimoto_reference(self.train_smiles, k=3, percentile=95)
        self.assertEqual(ref.k, 3)
        self.assertEqual(len(ref.fingerprints), len(self.train_smiles))
        
        # Manually compute intra-distances and assert it matches threshold exactly
        from rdkit import Chem
        from rdkit.Chem import AllChem
        from rdkit import DataStructs
        fps = [AllChem.GetMorganFingerprintAsBitVect(Chem.MolFromSmiles(s), 2, 2048) for s in self.train_smiles]
        n = len(fps)
        intra = []
        for i in range(n):
            other_fps = fps[:i] + fps[i+1:]
            sims = DataStructs.BulkTanimotoSimilarity(fps[i], other_fps)
            dists = sorted(1.0 - np.asarray(sims))[:3]
            intra.append(float(np.mean(dists)))
        expected_threshold = float(np.percentile(intra, 95))
        self.assertAlmostEqual(ref.threshold, expected_threshold, places=6)

        # Test score query
        queries = ["CCO", "c1ccccc1", "INVALID_SMILES"]
        scores = score_tanimoto(ref, queries)
        
        self.assertEqual(scores["status"][0], "in")  # CCO is in training set
        self.assertEqual(scores["status"][1], "out")  # Benzene is dissimilar
        self.assertEqual(scores["status"][2], "invalid")  # Invalid smiles

        # Score for an out-of-domain SMILES (ferrocene)
        ferrocene = "[Fe].c1ccc[cH-]1.c1ccc[cH-]1"
        scores_out = score_tanimoto(ref, [ferrocene])
        self.assertEqual(scores_out["status"][0], "out")

    def test_leverage_ad_reference_dense(self):
        ref = build_leverage_reference(self.X_train, self.y_train, self.y_train_pred)
        self.assertTrue(ref.available)
        self.assertIsNotNone(ref.h_star)
        
        # Score query
        X_query = np.array([
            [1.0, 2.0],     # similar
            [10.0, 20.0]    # extreme outlier (out of leverage)
        ])
        scores = score_leverage(ref, X_query)
        self.assertTrue(scores["available"])
        self.assertEqual(scores["status"][0], "in")
        self.assertEqual(scores["status"][1], "out")

    def test_leverage_ad_reference_sparse(self):
        # Create highly sparse X_train (fingerprint-like, >70% zeros)
        X_sparse = np.zeros((10, 100))
        X_sparse[0, 0] = 1.0
        X_sparse[1, 1] = 1.0
        
        y = np.ones(10)
        ref = build_leverage_reference(X_sparse, y, y)
        self.assertFalse(ref.available)
        
        scores = score_leverage(ref, X_sparse)
        self.assertFalse(scores["available"])

    def test_combined_ad_reference_worst_case(self):
        # Build combined AD
        ad = build_ad_reference(self.train_smiles, self.X_train, self.y_train, self.y_train_pred)
        self.assertIsInstance(ad, ApplicabilityDomain)
        self.assertTrue(ad.leverage.available)
        
        # Query where Tanimoto says "out" but leverage says "in"
        # query_smiles: dissimilar (benzene), query_X: similar to mean
        scores = score_query(ad, ["c1ccccc1"], np.array([[1.3, 2.3]]))
        self.assertEqual(scores["overall_status"][0], "out")
        
        # Query where both say "in"
        scores2 = score_query(ad, ["CCO"], np.array([[1.0, 2.0]]))
        self.assertEqual(scores2["overall_status"][0], "in")

    def test_combined_ad_reference_worst_case_unavailable(self):
        # Build combined AD where leverage is unavailable (sparse matrix)
        X_sparse = np.zeros((7, 100))
        ad = build_ad_reference(self.train_smiles, X_sparse, self.y_train, self.y_train_pred)
        self.assertFalse(ad.leverage.available)
        
        # Tanimoto status is "out" for benzene, leverage is None/unavailable. Combined should be "out"
        scores = score_query(ad, ["c1ccccc1"], np.zeros((1, 100)))
        self.assertEqual(scores["overall_status"][0], "out")
        
        # Tanimoto status is "in" for CCO, leverage is None/unavailable. Combined should be "in"
        scores2 = score_query(ad, ["CCO"], np.zeros((1, 100)))
        self.assertEqual(scores2["overall_status"][0], "in")

    def test_pickle_and_load_ad(self):
        ad = build_ad_reference(self.train_smiles, self.X_train, self.y_train, self.y_train_pred)
        
        # Pickle
        pickled_ad = pickle.dumps(ad)
        self.assertIsInstance(pickled_ad, bytes)
        
        # Load
        loaded_ad = pickle.loads(pickled_ad)
        self.assertIsInstance(loaded_ad, ApplicabilityDomain)
        self.assertEqual(loaded_ad.tanimoto.k, ad.tanimoto.k)
        self.assertEqual(loaded_ad.leverage.h_star, ad.leverage.h_star)
        
        # Validate functioning on loaded ad
        scores = score_query(loaded_ad, ["CCO"], np.array([[1.0, 2.0]]))
        self.assertEqual(scores["overall_status"][0], "in")

    def test_predict_endpoint_mpo(self):
        from edeon_engine.models.featurizers import run_featurizers
        selections = [{"id": "descriptors_2d", "params": {"selected": ["MW", "LogP"]}}]
        X_real, _ = run_featurizers(self.train_smiles, selections)
        
        ad = build_ad_reference(self.train_smiles, X_real, self.y_train, self.y_train_pred)
        mock_est = MockEstimator()
        
        handle = QSARModelHandle(
            estimator=mock_est,
            featurizer_selections=selections,
            ad=ad
        )
        
        # CC is ethane, c1ccccc1 is benzene, organometallic dissimilar
        smiles_queries = ["CCO", "c1ccccc1", "[U]"]
        preds = predict(handle, smiles_queries)
        
        self.assertEqual(len(preds), 3)
        for row in preds:
            self.assertIn("smiles", row)
            self.assertIn("prediction", row)
            self.assertIn("ad_status", row)
            self.assertIn("ad_confidence", row)
            self.assertIn("tanimoto_distance", row)
            self.assertIn("leverage", row)
            
            # Check confidence ranges
            self.assertIn(row["ad_status"], ["in", "borderline", "out", "invalid"])
            self.assertIn(row["ad_confidence"], [1.0, 0.6, 0.2, 0.0])
            
        # Check specific status
        self.assertEqual(preds[0]["ad_status"], "in")
        self.assertEqual(preds[0]["ad_confidence"], 1.0)
        self.assertEqual(preds[2]["ad_status"], "out")
        self.assertEqual(preds[2]["ad_confidence"], 0.2)

    def test_williams_plot_coordinates(self):
        ad = build_ad_reference(self.train_smiles, self.X_train, self.y_train, self.y_train_pred)
        
        # Evaluate similar validation set with targets
        scores = score_query(ad, ["CCO", "CCC"], np.array([[1.0, 2.0], [1.1, 2.1]]), y_query=[1.0, 1.2], y_query_pred=[0.9, 1.3])
        williams = williams_plot_data(ad, scores["leverage"])
        
        self.assertTrue(williams["available"])
        self.assertEqual(len(williams["points"]), 2)
        self.assertEqual(williams["h_star"], scores["leverage"]["h_star"])
        self.assertEqual(williams["residual_threshold"], 3.0)
        
        for pt in williams["points"]:
            self.assertIn("leverage", pt)
            self.assertIn("std_residual", pt)
            self.assertIn("status", pt)


if __name__ == "__main__":
    unittest.main()
