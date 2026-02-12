import unittest
import numpy as np
from edeon_engine.models.trainers import train_model_batch
from edeon_engine.models.search.grid import grid_search
from edeon_engine.models.search.bayesian import bayesian_search

class TestPhase2Search(unittest.TestCase):
    def setUp(self):
        # Delaney-like synthetic data
        self.smiles = [
            "CCO", "CCN", "CCC", "CC(=O)O", "CC(=O)N",
            "C1CCCCC1", "C1=CC=CC=C1", "CO", "CN", "CS",
            "CC(C)O", "CC(C)N", "CC(C)C", "CC(=O)C", "CCN(CC)CC"
        ]
        # Continuous values for regression
        self.activities = [-1.2, -0.8, -0.2, 0.4, 0.6, 1.2, 1.5, -0.9, -0.5, -0.3, -0.7, -0.4, -0.1, 0.2, 0.9]

    def test_grid_search_direct(self):
        X = np.random.randn(15, 6)
        y = np.array(self.activities)
        grid = {
            "n_estimators": [50, 100],
            "max_depth": [3, 5]
        }
        
        trials_logged = []
        def log_cb(trial_id, params, mean, std, duration):
            trials_logged.append((trial_id, params))
            
        res = grid_search(
            X=X.tolist(),
            y=y,
            smiles=self.smiles,
            algorithm="rf",
            model_type="regression",
            base_params={"random_state": 42},
            grid=grid,
            cv_k=3,
            split_mode="random",
            random_state=42,
            log_callback=log_cb
        )
        
        self.assertEqual(len(res["trials"]), 4)
        self.assertEqual(len(trials_logged), 4)
        self.assertIn("n_estimators", res["best_params"])
        self.assertIn("max_depth", res["best_params"])
        self.assertGreater(len(res["trials"]), 0)

    def test_bayesian_search_direct(self):
        X = np.random.randn(15, 6)
        y = np.array(self.activities)
        space = {
            "n_estimators": {"type": "int", "low": 50, "high": 100},
            "max_depth": {"type": "int", "low": 3, "high": 5}
        }
        
        trials_logged = []
        def log_cb(trial_id, params, mean, std, duration):
            trials_logged.append((trial_id, params))
            
        res = bayesian_search(
            X=X.tolist(),
            y=y,
            smiles=self.smiles,
            algorithm="rf",
            model_type="regression",
            base_params={"random_state": 42},
            space=space,
            n_trials=5,
            timeout=None,
            cv_k=3,
            split_mode="random",
            random_state=42,
            log_callback=log_cb
        )
        
        self.assertEqual(len(res["trials"]), 5)
        self.assertEqual(len(trials_logged), 5)
        self.assertIn("n_estimators", res["best_params"])
        self.assertIn("max_depth", res["best_params"])

    def test_train_model_batch_with_grid(self):
        config = {
            "model_type": "regression",
            "algorithm": "rf",
            "split_mode": "random",
            "test_size": 0.2,
            "random_seed": 42,
            "cv_folds": 3,
            "n_scramble": 0,
            "search": {
                "mode": "grid",
                "grid": {
                    "n_estimators": [50, 100],
                    "max_depth": [3, 5]
                }
            },
            "hyperparameters": {
                "max_features": "sqrt"
            }
        }
        
        result = train_model_batch(self.smiles, self.activities, config)
        self.assertIn("search_results", result)
        self.assertIsNotNone(result["search_results"])
        self.assertEqual(result["search_results"]["mode"], "grid")
        self.assertEqual(result["search_results"]["n_trials"], 4)
        self.assertIn("best_params", result["search_results"])
        self.assertIn("n_estimators", result["params"])
        self.assertIn("max_depth", result["params"])
        self.assertEqual(result["params"]["max_features"], "sqrt")

    def test_train_model_batch_with_bayesian(self):
        config = {
            "model_type": "regression",
            "algorithm": "rf",
            "split_mode": "random",
            "test_size": 0.2,
            "random_seed": 42,
            "cv_folds": 3,
            "n_scramble": 0,
            "search": {
                "mode": "bayesian",
                "bayesian": {
                    "n_trials": 4,
                    "param_space": {
                        "n_estimators": {"type": "int", "low": 50, "high": 100},
                        "max_depth": {"type": "int", "low": 3, "high": 5}
                    }
                }
            },
            "hyperparameters": {
                "max_features": "sqrt"
            }
        }
        
        result = train_model_batch(self.smiles, self.activities, config)
        self.assertIn("search_results", result)
        self.assertIsNotNone(result["search_results"])
        self.assertEqual(result["search_results"]["mode"], "bayesian")
        self.assertEqual(result["search_results"]["n_trials"], 4)
        self.assertIn("best_params", result["search_results"])
        self.assertIn("n_estimators", result["params"])
        self.assertIn("max_depth", result["params"])
        self.assertEqual(result["params"]["max_features"], "sqrt")

    def test_run_arena_default(self):
        from edeon_engine.models.arena import run_arena
        config = {
            "model_type": "regression",
            "split_mode": "random",
            "test_size": 0.2,
            "random_seed": 42,
            "cv_folds": 3,
            "n_scramble": 2,
            "featurizer_selections": [
                {"id": "descriptors_2d", "params": {"selected": ["MW", "LogP"]}}
            ],
            "arena": {
                "algorithms": ["rf", "svm"],
                "per_algo_search": "default"
            }
        }
        res = run_arena(self.smiles, self.activities, config)
        self.assertIn("shared", res)
        self.assertIn("models", res)
        self.assertIn("ranking", res)
        self.assertEqual(len(res["models"]), 2)

if __name__ == "__main__":
    unittest.main()
