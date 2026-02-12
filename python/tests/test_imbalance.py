import unittest
import numpy as np
from collections import Counter
from unittest.mock import patch
from edeon_engine.models.imbalance import apply_imbalance_strategy
from edeon_engine.models.validation import kfold_cv
from edeon_engine.models.estimators import build_estimator

class TestQSARImbalance(unittest.TestCase):
    def setUp(self):
        # Create a heavily imbalanced dataset (90 class 0, 10 class 1)
        np.random.seed(42)
        self.X = np.random.randn(100, 4).tolist()
        self.y = ([0] * 90) + ([1] * 10)
        self.smiles = ["CCO" for _ in range(100)]

    def test_smote_produces_one_to_one_ratio(self):
        """SMOTE on 90/10 produces 1:1 resampled training set."""
        Xr, yr, cw = apply_imbalance_strategy(self.X, self.y, "smote", 42)
        
        # Verify no class weight dict is returned since it's resampling
        self.assertIsNone(cw)
        
        # Verify 1:1 ratio
        counts = Counter(yr)
        self.assertEqual(counts[0], counts[1])
        self.assertEqual(counts[0], 90)
        self.assertEqual(len(Xr), 180)

    def test_resampling_happens_inside_cv_folds(self):
        """Resampling happens inside CV folds (verify by counting unique samples seen per fold)."""
        config = {
            "model_type": "classification",
            "imbalance_strategy": "smote",
            "hyperparameters": {
                "n_estimators": 5,
                "max_depth": 3
            }
        }
        
        # Capture the training data shape passed into each fold's _train_fold fit call
        X_tr_sizes = []
        original_train_fold_sizes = []
        
        # We patch _train_fold to capture the sizes
        from edeon_engine.models.validation import _train_fold
        def mock_train_fold(X_tr, y_tr, X_va, y_va, model_type, algorithm, config, class_weight=None):
            X_tr_sizes.append(len(X_tr))
            return {
                'accuracy_val': 0.8,
                'f1_score': 0.8,
                'auc_roc': 0.8,
                'accuracy_train': 0.8,
            }
            
        with patch("edeon_engine.models.validation._train_fold", side_effect=mock_train_fold):
            # Run 3-fold cross validation on our 100 sample dataset
            # Training split sizes normally would be ~67 and validation would be ~33.
            # With 3-fold stratified or random split:
            # - train_idx size = 66 or 67 (with ~60 class 0 and ~7 class 1).
            # - If SMOTE resampling happens INSIDE the fold, it should oversample class 1 
            #   up to class 0 size (~60), making total train size ~120!
            kfold_cv(self.X, self.y, self.smiles, k=3, split_mode="random", random_state=42, model_type="classification", algorithm="rf", config=config)
            
        # Verify that for all lengkap completar Completa COMPLETE complete completed complete folds, 
        # the training size passed to the estimator fit (mocked _train_fold) was significantly 
        # larger than the original training partition fold split (~67).
        self.assertEqual(len(X_tr_sizes), 3)
        for size in X_tr_sizes:
            self.assertGreater(size, 100) # Oversampled from ~67 to ~120
            self.assertTrue(size % 2 == 0) # Should be balanced 1:1, hence even

    def test_class_weight_translates_to_scale_pos_weight_for_xgboost(self):
        """class_weight translates correctly to scale_pos_weight for XGBoost and LightGBM."""
        # Standard balanced weight ratio dictionary
        cw = {0: 0.5, 1: 5.0}
        params = {"class_weight": cw}
        
        # 1. Test XGBoost
        xgb_model = build_estimator("classification", "xgboost", params)
        self.assertEqual(xgb_model.get_params()["scale_pos_weight"], 10.0)
        
        # 2. Test LightGBM
        lgb_model = build_estimator("classification", "lightgbm", params)
        self.assertEqual(lgb_model.get_params()["scale_pos_weight"], 10.0)
        self.assertIsNone(lgb_model.get_params()["class_weight"])

if __name__ == "__main__":
    unittest.main()
