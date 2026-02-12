import unittest
import numpy as np
import tempfile
import os
import shutil
from edeon_train.shared.baselines import (
    ScaffoldKFold,
    train_baseline_with_hpo,
    save_baseline_checkpoint,
    load_baseline_checkpoint
)

class TestBaselines(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        # Create a small dataset with repeated scaffolds
        # Ethanols, Ibuprofens, Benzene
        self.smiles = [
            "CCO", "CCO", "CCO",  # Scaffold: empty
            "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O", "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O",  # Scaffold: benzene
            "C1CCCCC1", "C1CCCCC1",  # Scaffold: cyclohexane
            "c1ncncn1", "c1ncncn1", "c1ncncn1"  # Scaffold: triazine
        ]
        # 10 compounds, 8 features, target regression
        np.random.seed(42)
        self.X = np.random.randn(10, 8)
        self.y = np.random.randn(10)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_scaffold_k_fold(self):
        kf = ScaffoldKFold(n_splits=3, random_state=42)
        splits = list(kf.split(self.X, self.y, self.smiles))
        
        self.assertEqual(len(splits), 3)
        for train_idx, val_idx in splits:
            self.assertTrue(len(train_idx) > 0)
            self.assertTrue(len(val_idx) > 0)
            # Ensure no scaffold overlap
            train_smiles = [self.smiles[i] for i in train_idx]
            val_smiles = [self.smiles[i] for i in val_idx]
            
            # Simple check: the exact same SMILES (since they share scaffolds) shouldn't be in both
            # except if it is empty/invalid.
            train_scaffolds = {s for s in train_smiles}
            val_scaffolds = {s for s in val_smiles}
            overlap = train_scaffolds.intersection(val_scaffolds)
            
            # Since our mock uses identical smiles strings to represent shared scaffolds,
            # this overlap should be empty.
            self.assertEqual(len(overlap), 0, f"Overlapping SMILES found: {overlap}")

    def test_train_baseline_hpo_rf(self):
        # Run HPO with a small number of trials (e.g., 3) to keep the test extremely fast
        model, metadata = train_baseline_with_hpo(
            self.X, self.y, self.smiles, model_type="rf", n_trials=3, cv_folds=2, random_state=42
        )
        self.assertIsNotNone(model)
        self.assertEqual(metadata["model_type"], "rf")
        self.assertEqual(metadata["n_trials"], 3)
        self.assertEqual(len(metadata["trials_history"]), 3)
        
        # Test predictions
        preds = model.predict(self.X)
        self.assertEqual(preds.shape, (10,))

    def test_train_baseline_hpo_xgb(self):
        # Run HPO with a small number of trials (e.g., 3) to keep the test extremely fast
        model, metadata = train_baseline_with_hpo(
            self.X, self.y, self.smiles, model_type="xgb", n_trials=3, cv_folds=2, random_state=42
        )
        self.assertIsNotNone(model)
        self.assertEqual(metadata["model_type"], "xgb")
        self.assertEqual(metadata["n_trials"], 3)
        self.assertEqual(len(metadata["trials_history"]), 3)
        
        # Test predictions
        preds = model.predict(self.X)
        self.assertEqual(preds.shape, (10,))

    def test_save_load_checkpoint(self):
        # Train a quick RF model
        model, metadata = train_baseline_with_hpo(
            self.X, self.y, self.smiles, model_type="rf", n_trials=2, cv_folds=2, random_state=42
        )
        
        save_baseline_checkpoint(model, metadata, self.temp_dir)
        
        # Verify files exist
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "rf.pkl")))
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "rf_hpo_results.json")))
        
        # Load and verify prediction consistency
        loaded_model, loaded_meta = load_baseline_checkpoint(self.temp_dir, "rf")
        self.assertEqual(loaded_meta["model_type"], "rf")
        
        orig_preds = model.predict(self.X)
        loaded_preds = loaded_model.predict(self.X)
        np.testing.assert_allclose(orig_preds, loaded_preds, rtol=1e-5)

if __name__ == "__main__":
    unittest.main()
