import unittest
import numpy as np
import tempfile
import os
import shutil
from edeon_train.shared.chemprop_wrapper import (
    train_chemprop_ensemble,
    predict_chemprop_ensemble,
    chemprop_hpo
)

class TestChempropWrapper(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        
        # 10 compounds, regression task
        self.smiles = [
            "CCO", "CCO", "CCO",
            "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O", "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O",
            "C1CCCCC1", "C1CCCCC1",
            "c1ncncn1", "c1ncncn1", "INVALID_SMILES"
        ]
        self.y = np.array([
            -0.1, -0.05, -0.01,
            1.5, 1.6,
            0.8, 0.9,
            1.2, 1.3,
            np.nan  # Match bad smiles
        ])
        
        # Test config (keep it tiny for fast unit testing)
        self.tiny_config = {
            "depth": 2,
            "hidden_size": 16,
            "ffn_num_layers": 1,
            "ffn_hidden_size": 16,
            "dropout": 0.0,
            "epochs": 3,
            "batch_size": 4,
            "warmup_epochs": 1,
            "init_lr": 1e-4,
            "max_lr": 1e-3,
            "final_lr": 1e-4
        }

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_train_and_predict_ensemble(self):
        # We only train 2 seeds (e.g. 0 and 1) for fast unit test
        seeds = [0, 1]
        
        # Split train/cal (7 train, 3 cal)
        train_s = self.smiles[:6]
        train_y = self.y[:6]
        cal_s = self.smiles[6:9]
        cal_y = self.y[6:9]
        
        meta = train_chemprop_ensemble(
            train_smiles=train_s,
            train_y=train_y,
            cal_smiles=cal_s,
            cal_y=cal_y,
            config=self.tiny_config,
            output_dir=self.temp_dir,
            seeds=seeds
        )
        
        self.assertEqual(meta["seeds"], seeds)
        self.assertIn(0, meta["seed_val_losses"])
        self.assertIn(1, meta["seed_val_losses"])
        
        # Verify checkpoint files exist
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "seed_0.pt")))
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "seed_1.pt")))
        
        # Predict on same Smiles (including invalid one)
        mean_preds, std_preds = predict_chemprop_ensemble(
            smiles=self.smiles,
            checkpoint_dir=self.temp_dir,
            seeds=seeds
        )
        
        self.assertEqual(mean_preds.shape, (10,))
        self.assertEqual(std_preds.shape, (10,))
        
        # Valid ones should have float values
        self.assertFalse(np.isnan(mean_preds[0]))
        self.assertFalse(np.isnan(std_preds[0]))
        
        # Invalid smiles at index 9 should be NaN
        self.assertTrue(np.isnan(mean_preds[9]))
        self.assertTrue(np.isnan(std_preds[9]))

    def test_chemprop_hpo(self):
        # Run extremely brief HPO: 2 trials, 2 folds
        best_params = chemprop_hpo(
            train_smiles=self.smiles[:8],
            train_y=self.y[:8],
            smiles_scaffolds=self.smiles[:8],
            n_trials=2,
            cv_folds=2,
            random_state=42
        )
        
        self.assertIsInstance(best_params, dict)
        self.assertIn("depth", best_params)
        self.assertIn("hidden_size", best_params)

if __name__ == "__main__":
    unittest.main()
