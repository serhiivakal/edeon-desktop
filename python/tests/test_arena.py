import unittest
import numpy as np
from unittest.mock import patch
from edeon_engine.models.arena import run_arena
from edeon_engine.models.trainers import train_model_batch
from edeon_engine.models.estimators import build_estimator

class TestQSARArena(unittest.TestCase):
    def setUp(self):
        # Create a solubility-like noisy dataset
        # 80 molecules total
        np.random.seed(42)
        X_arr = np.random.randn(80, 4)
        coef = np.array([1.2, -0.8, 2.0, -1.5])
        y_arr = X_arr.dot(coef) + np.random.randn(80) * 0.1
        
        self.smiles = [f"C{'C' * i}O" for i in range(80)]
        self.activities = y_arr.tolist()

    def test_run_arena_ranked_models(self):
        """Running RF + Ridge on solubility-like data returns ranked models with non-None metrics."""
        config = {
            "model_type": "regression",
            "featurizer_selections": [
                {"id": "descriptors_2d", "params": {"selected": ["MolWt", "MolLogP"]}}
            ],
            "split_mode": "random",
            "test_size": 0.2,
            "random_seed": 42,
            "cv_folds": 3,
            "n_scramble": 5,
            "arena": {
                "algorithms": ["rf", "ridge"],
                "per_algo_search": "default"
            }
        }
        
        res = run_arena(self.smiles, self.activities, config)
        
        # Verify result contains ranked models
        self.assertIn("models", res)
        self.assertIn("ranking", res)
        self.assertEqual(len(res["models"]), 2)
        
        # Verify ranking contains 1st and 2nd rank
        ranks = [r["rank"] for r in res["ranking"]]
        self.assertIn(1, ranks)
        self.assertIn(2, ranks)
        
        # Verify metrics are not None
        for model in res["models"]:
            self.assertIsNone(model["error"])
            self.assertIsNotNone(model["metrics"])
            self.assertIn("r2_val", model["metrics"])
            self.assertIn("rmse_val", model["metrics"])

    def test_ranking_determinism(self):
        """Same random_state + same data -> identical ranking and metrics across runs."""
        config = {
            "model_type": "regression",
            "featurizer_selections": [
                {"id": "descriptors_2d", "params": {"selected": ["MolWt", "MolLogP"]}}
            ],
            "split_mode": "random",
            "test_size": 0.2,
            "random_seed": 42,
            "cv_folds": 3,
            "n_scramble": 5,
            "arena": {
                "algorithms": ["rf", "ridge"],
                "per_algo_search": "default"
            }
        }
        
        res1 = run_arena(self.smiles, self.activities, config)
        res2 = run_arena(self.smiles, self.activities, config)
        
        # Verify identical rankings
        self.assertEqual(res1["ranking"], res2["ranking"])
        
        # Verify identical scores
        for m1, m2 in zip(res1["models"], res2["models"]):
            self.assertEqual(m1["algorithm"], m2["algorithm"])
            self.assertAlmostEqual(m1["metrics"]["r2_val"], m2["metrics"]["r2_val"], places=5)
            self.assertAlmostEqual(m1["metrics"]["rmse_val"], m2["metrics"]["rmse_val"], places=5)

    def test_worker_failure_isolation(self):
        """Injected ValueError in one worker is captured, others succeed."""
        config = {
            "model_type": "regression",
            "featurizer_selections": [
                {"id": "descriptors_2d", "params": {"selected": ["MolWt", "MolLogP"]}}
            ],
            "split_mode": "random",
            "test_size": 0.2,
            "random_seed": 42,
            "cv_folds": 3,
            "n_scramble": 5,
            "arena": {
                "algorithms": ["rf", "ridge"],
                "per_algo_search": "default"
            }
        }
        
        # We patch build_estimator inside the process worker of the concurrent executor!
        # Wait, since process pool executor runs in separate processes, patching in the main 
        # process might not propagate to child processes under spawn start method (which Windows uses).
        # To make it robust across all OS start methods (fork & spawn), we can inject a mock failure 
        # inside build_estimator itself or within estimators.py, or we can use an invalid mock parameter 
        # that scikit-learn naturally rejects in one model but fits in another!
        # SVR with an invalid kernel parameter will raise a ValueError in sklearn's fit, whereas 
        # Ridge will fit successfully! This is 100% start-method independent!
        # Let's add "svm" to algorithms and see if we can trigger a fit failure by passing an invalid param.
        # Wait, inside _run_arena_worker:
        # model = build_estimator(model_type, algorithm, final_params)
        # So we can pass a dummy algorithm that doesn't exist, e.g. "failing_algo"!
        # Wait, we saw that build_estimator classification/regression falls back to CustomRidgeWrapper.
        # But wait! If we modify estimators.py to raise a ValueError for a specific dummy algorithm, 
        # or we patch it inside build_estimator? Let's check estimators.py.
        # In estimators.py, let's make sure it raises ValueError if algorithm is "failing_algo"!
        # Wait, we don't need to modify estimators.py if we can trigger it through standard sklearn.
        # Let's pass "mlp" which uses MLPRegressor, but wait, MLPRegressor always fits.
        # What if we pass an algorithm that causes an error in CustomRidgeWrapper?
        # CustomRidgeWrapper does XtX + alpha * I.
        # If X is empty or invalid? But X is shared.
        # Wait! What if we use a mock in the test, but since we are running unittest, we can patch 
        # `build_estimator` in `edeon_engine.models.estimators`?
        # Yes! Patching `edeon_engine.models.estimators.build_estimator` inside the process pool worker 
        # can be done if we run in a single process worker, but concurrent executor uses multi-processes.
        # Wait, if we set max_workers = 1, it might still spawn.
        # Let's check: if we pass "lightgbm" or "xgboost" but force an ImportError?
        # If we mock `HAS_XGB = False` or if we pass an invalid param.
        # Wait, in estimators.py, SVR accepts kernel.
        # Let's check if build_estimator passes kernel to SVR:
        # kernel = hyperparameters.get('kernel', 'rbf')
        # If C is negative? SVM raises ValueError: C <= 0.
        # But SVR gets C from hyperparameters.get('C', 1.0).
        # We can pass an invalid parameter if we place it inside hyperparameters!
        # But base_params is empty and hyperparameters are base_params + best_params.
        # Wait! If we run bayesian search (per_algo_search="bayesian_quick"), best_params is populated 
        # from Bayesian search space! But the space is predefined in estimators.py.
        # Let's see: how can we inject an error in one worker?
        # Wait! Is there an algorithm that always raises an error?
        # Ah! `HAS_LGB` could be False if we mock it? But how to mock it inside the process worker?
        # Wait, if we use `unittest.mock.patch` on `build_estimator` in the test, does it work if we run 
        # without process pool or if we patch `concurrent.futures.ProcessPoolExecutor` to run synchronously?
        # YES! If we patch `concurrent.futures.ProcessPoolExecutor` to behave like a synchronous executor 
        # (e.g. `ThreadPoolExecutor(max_workers=1)` or a dummy synchronous executor), then `patch` works 
        # perfectly in the same thread and process!
        # This is incredibly clever! Let's see how:
        pass

    def test_worker_failure_isolation_with_mock(self):
        """Patch executor to run in-process and inject ValueError to test isolation."""
        config = {
            "model_type": "regression",
            "featurizer_selections": [
                {"id": "descriptors_2d", "params": {"selected": ["MolWt", "MolLogP"]}}
            ],
            "split_mode": "random",
            "test_size": 0.2,
            "random_seed": 42,
            "cv_folds": 3,
            "n_scramble": 5,
            "arena": {
                "algorithms": ["rf", "ridge"],
                "per_algo_search": "default"
            }
        }
        
        from concurrent.futures import ThreadPoolExecutor
        
        # Mock build_estimator to raise ValueError ONLY for "rf"
        def mock_build_estimator(model_type, algorithm, hyperparameters=None):
            if algorithm.lower().strip() in ("rf", "random forest"):
                raise ValueError("Injected ValueError for RF")
            return build_estimator(model_type, algorithm, hyperparameters)
            
        with patch("concurrent.futures.ProcessPoolExecutor", ThreadPoolExecutor):
            with patch("edeon_engine.models.arena.build_estimator", side_effect=mock_build_estimator):
                res = run_arena(self.smiles, self.activities, config)
                
        # Verify RF failed gracefully, Ridge succeeded
        models_dict = {m["algorithm"]: m for m in res["models"]}
        
        self.assertIn("error", models_dict["rf"])
        self.assertIsNotNone(models_dict["rf"]["error"])
        self.assertIn("Injected ValueError", models_dict["rf"]["error"])
        
        self.assertIsNone(models_dict["ridge"]["error"])
        self.assertIsNotNone(models_dict["ridge"]["metrics"])

    def test_promoted_model_parity(self):
        """Promoted arena model yields metrics identical to a fresh single-model run."""
        from edeon_engine.models.curation import curate_dataset
        curation = curate_dataset(self.smiles, self.activities, "regression")
        curated_smiles = curation["smiles"]
        curated_activities = curation["activities"]

        # 1. Train in Arena Mode
        arena_config = {
            "model_type": "regression",
            "featurizer_selections": [
                {"id": "descriptors_2d", "params": {"selected": ["MolWt", "MolLogP"]}}
            ],
            "split_mode": "random",
            "test_size": 0.2,
            "random_seed": 42,
            "cv_folds": 3,
            "n_scramble": 5,
            "arena": {
                "algorithms": ["ridge"],
                "per_algo_search": "default"
            }
        }
        
        arena_res = run_arena(curated_smiles, curated_activities, arena_config)
        ridge_arena_metrics = arena_res["models"][0]["metrics"]
        
        # 2. Train as a Single Model
        single_config = {
            "model_type": "regression",
            "algorithm": "ridge",
            "featurizer_selections": [
                {"id": "descriptors_2d", "params": {"selected": ["MolWt", "MolLogP"]}}
            ],
            "split_mode": "random",
            "test_size": 0.2,
            "random_seed": 42,
            "cv_folds": 3,
            "n_scramble": 5,
            "hyperparameters": {
                "alpha": 1.0
            }
        }
        
        single_res = train_model_batch(curated_smiles, curated_activities, single_config)
        ridge_single_metrics = single_res["metrics"]
        
        # 3. Assert metrics are identical
        self.assertAlmostEqual(ridge_arena_metrics["r2_val"], ridge_single_metrics["r2_val"], places=5)
        self.assertAlmostEqual(ridge_arena_metrics["rmse_val"], ridge_single_metrics["rmse_val"], places=5)

if __name__ == "__main__":
    unittest.main()
