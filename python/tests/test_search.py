import unittest
import numpy as np
from edeon_engine.models.search.grid import grid_search
from edeon_engine.models.search.bayesian import bayesian_search

class TestHyperparameterSearch(unittest.TestCase):
    def setUp(self):
        # Create a clean synthetic dataset for regression checks
        # y = 2 * x + noise
        np.random.seed(42)
        X_arr = np.random.randn(60, 2)
        y_arr = 2.5 * X_arr[:, 0] - 1.5 * X_arr[:, 1] + np.random.randn(60) * 0.05
        
        self.X = X_arr.tolist()
        self.y = y_arr.tolist()
        self.smiles = ["CC" for _ in range(60)]

    def test_grid_search_exact_combination_counts(self):
        """Grid search with 2x2 grid runs exactly 4 trials."""
        grid = {
            "alpha": [1.0, 10.0],
            "max_iter": [500, 1000]
        }
        base_params = {}
        
        res = grid_search(
            X=self.X,
            y=self.y,
            smiles=self.smiles,
            algorithm="ridge",
            model_type="regression",
            base_params=base_params,
            grid=grid,
            cv_k=3,
            split_mode="random",
            random_state=42,
            log_callback=None
        )
        
        # Verify exactly 4 combinations run
        self.assertEqual(len(res["trials"]), 4)
        
        # Verify the parameters of the 4 trials
        combos = [t["params"] for t in res["trials"]]
        self.assertIn({"alpha": 1.0, "max_iter": 500}, combos)
        self.assertIn({"alpha": 1.0, "max_iter": 1000}, combos)
        self.assertIn({"alpha": 10.0, "max_iter": 500}, combos)
        self.assertIn({"alpha": 10.0, "max_iter": 1000}, combos)

    def test_bayesian_search_ridge_alpha_convergence(self):
        """Bayesian search converges to optimal alpha for Ridge within 30 trials."""
        space = {
            "alpha": {"type": "float", "low": 0.01, "high": 100.0, "log": True}
        }
        base_params = {}
        
        res = bayesian_search(
            X=self.X,
            y=self.y,
            smiles=self.smiles,
            algorithm="ridge",
            model_type="regression",
            base_params=base_params,
            space=space,
            n_trials=30,
            timeout=None,
            cv_k=3,
            split_mode="random",
            random_state=42,
            log_callback=None
        )
        
        self.assertLessEqual(len(res["trials"]), 30)
        best_alpha = res["best_params"]["alpha"]
        
        # For a clean linear dataset with minimal noise, low regularization (alpha close to 0) 
        # is optimal because standard OLS/low ridge fits perfectly. Extremely high regularization
        # (e.g., alpha > 50) heavily shrinks coefficients, leading to poor CV score.
        # Thus, Bayesian search must converge to a low alpha value (e.g. < 10.0)
        self.assertLess(best_alpha, 10.0)
        self.assertGreater(best_alpha, 0.0)

    def test_search_modes_return_identical_schema(self):
        """Grid search and Bayesian search return identical dictionary schema."""
        grid = {
            "alpha": [1.0, 10.0]
        }
        space = {
            "alpha": {"type": "float", "low": 1.0, "high": 10.0}
        }
        base_params = {}
        
        grid_res = grid_search(
            X=self.X,
            y=self.y,
            smiles=self.smiles,
            algorithm="ridge",
            model_type="regression",
            base_params=base_params,
            grid=grid,
            cv_k=3,
            split_mode="random",
            random_state=42,
            log_callback=None
        )
        
        bayesian_res = bayesian_search(
            X=self.X,
            y=self.y,
            smiles=self.smiles,
            algorithm="ridge",
            model_type="regression",
            base_params=base_params,
            space=space,
            n_trials=2,
            timeout=None,
            cv_k=3,
            split_mode="random",
            random_state=42,
            log_callback=None
        )
        
        # Verify schema keys
        self.assertEqual(set(grid_res.keys()), set(bayesian_res.keys()))
        self.assertEqual(set(grid_res.keys()), {"trials", "best_trial_id", "best_params", "best_score", "primary_metric"})
        
        # Verify details of a trial
        grid_trial = grid_res["trials"][0]
        bayesian_trial = bayesian_res["trials"][0]
        self.assertEqual(set(grid_trial.keys()), set(bayesian_trial.keys()))
        self.assertEqual(set(grid_trial.keys()), {"trial_id", "params", "mean_cv_score", "std_cv_score", "fold_scores", "duration_s"})

if __name__ == "__main__":
    unittest.main()
