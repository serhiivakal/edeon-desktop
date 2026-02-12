"""
Edeon Engine — Unified Estimators
Unified QSAR estimators factory with Scikit-learn, XGBoost, and LightGBM models.
Includes graceful fallback structures for platform-specific import failures.
"""

import math
import numpy as np

# Try to import scikit-learn
HAS_SKLEARN = False
try:
    from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier, GradientBoostingRegressor, GradientBoostingClassifier
    from sklearn.svm import SVR, SVC
    from sklearn.linear_model import Ridge, RidgeClassifier, ElasticNet, LogisticRegression
    from sklearn.neighbors import KNeighborsRegressor, KNeighborsClassifier
    from sklearn.neural_network import MLPRegressor, MLPClassifier
    HAS_SKLEARN = True
except ImportError:
    pass

# Try to import XGBoost
HAS_XGB = False
try:
    from xgboost import XGBRegressor, XGBClassifier
    HAS_XGB = True
except ImportError:
    pass

# Try to import LightGBM
HAS_LGB = False
LGB_IMPORT_ERROR = None
try:
    from lightgbm import LGBMRegressor, LGBMClassifier
    HAS_LGB = True
except Exception as e:
    LGB_IMPORT_ERROR = str(e)

# Sensible default parameter spaces for hyperparameter sweeps (Grid/Bayesian)
DEFAULT_PARAM_SPACE = {
    "rf": {
        "n_estimators": {"type": "int", "low": 50, "high": 500},
        "max_depth": {"type": "int", "low": 3, "high": 30},
        "min_samples_split": {"type": "int", "low": 2, "high": 20},
        "max_features": {"type": "categorical", "choices": ["sqrt", "log2", 0.5, 1.0]}
    },
    "gbm": {
        "n_estimators": {"type": "int", "low": 50, "high": 500},
        "max_depth": {"type": "int", "low": 3, "high": 15},
        "learning_rate": {"type": "float", "low": 1e-3, "high": 1.0, "log": True}
    },
    "xgboost": {
        "n_estimators": {"type": "int", "low": 50, "high": 500},
        "max_depth": {"type": "int", "low": 3, "high": 15},
        "learning_rate": {"type": "float", "low": 1e-3, "high": 1.0, "log": True}
    },
    "lightgbm": {
        "n_estimators": {"type": "int", "low": 50, "high": 500},
        "max_depth": {"type": "int", "low": 3, "high": 15},
        "learning_rate": {"type": "float", "low": 1e-3, "high": 1.0, "log": True}
    },
    "svm": {
        "C": {"type": "float", "low": 1e-3, "high": 1e3, "log": True},
        "gamma": {"type": "categorical", "choices": ["scale", "auto"]}
    },
    "ridge": {
        "alpha": {"type": "float", "low": 1e-3, "high": 1e3, "log": True}
    },
    "elasticnet": {
        "alpha": {"type": "float", "low": 1e-3, "high": 1e3, "log": True},
        "l1_ratio": {"type": "float", "low": 0.0, "high": 1.0}
    },
    "knn": {
        "n_neighbors": {"type": "int", "low": 2, "high": 30},
        "weights": {"type": "categorical", "choices": ["uniform", "distance"]}
    },
    "mlp": {
        "max_iter": {"type": "int", "low": 100, "high": 1000}
    }
}

class CustomRidgeWrapper:
    """
    Scikit-learn compliant wrapper for the Edeon zero-dependency pure-Python Ridge solver.
    """
    def __init__(self, alpha=1.0):
        self.alpha = alpha
        self.coef_ = None
        self.predict_fn = None
        self.feature_importances_ = None
        
    def fit(self, X, y):
        from .trainers import custom_ridge_fit
        # Fit custom ridge model
        self.coef_, self.predict_fn = custom_ridge_fit(X, y, self.alpha)
        # Store absolute coefficients as feature importances
        self.feature_importances_ = np.abs(np.array(self.coef_))
        if self.feature_importances_.sum() > 0:
            self.feature_importances_ /= self.feature_importances_.sum()
        return self
        
    def predict(self, X):
        if self.predict_fn is None:
            raise RuntimeError("Model is not fitted yet.")
        # Ensure we return a numpy array
        return np.array(self.predict_fn(X))

    def predict_proba(self, X):
        preds = self.predict(X)
        probs = []
        for p in preds:
            # Apply Sigmoid logic for proba fallbacks
            try:
                sig = 1.0 / (1.0 + math.exp(-max(-20.0, min(20.0, p))))
            except Exception:
                sig = 0.5
            probs.append([1.0 - sig, sig])
        return np.array(probs)


def build_estimator(model_type, algorithm, hyperparameters=None):
    """
    Unified estimator factory for regression and classification QSAR models.
    Supports standard sklearn estimators, XGBoost, LightGBM, and pure-Python fallbacks.
    """
    if hyperparameters is None:
        hyperparameters = {}
        
    algo_lower = algorithm.lower().strip()
    
    # 1. Regression Models
    if model_type == 'regression':
        if algo_lower in ('random forest', 'rf'):
            if not HAS_SKLEARN:
                raise ImportError("scikit-learn is required for Random Forest.")
            return RandomForestRegressor(
                n_estimators=hyperparameters.get('n_estimators', 100),
                max_depth=hyperparameters.get('max_depth', 6),
                min_samples_split=hyperparameters.get('min_samples_split', 2),
                max_features=hyperparameters.get('max_features', 'sqrt'),
                random_state=hyperparameters.get('random_state', 42)
            )
        elif algo_lower in ('gradient boosting', 'gbm'):
            if not HAS_SKLEARN:
                raise ImportError("scikit-learn is required for Gradient Boosting.")
            return GradientBoostingRegressor(
                n_estimators=hyperparameters.get('n_estimators', 100),
                max_depth=hyperparameters.get('max_depth', 3),
                learning_rate=hyperparameters.get('learning_rate', 0.1),
                random_state=hyperparameters.get('random_state', 42)
            )
        elif algo_lower in ('xgboost', 'xgb'):
            if not HAS_XGB:
                raise ImportError("xgboost is required for XGBoost models.")
            return XGBRegressor(
                n_estimators=hyperparameters.get('n_estimators', 100),
                max_depth=hyperparameters.get('max_depth', 6),
                learning_rate=hyperparameters.get('learning_rate', 0.1),
                random_state=hyperparameters.get('random_state', 42)
            )
        elif algo_lower in ('lightgbm', 'lgbm'):
            if not HAS_LGB:
                err_msg = f"lightgbm is unavailable. {LGB_IMPORT_ERROR or 'Import failed.'}"
                raise ImportError(err_msg)
            return LGBMRegressor(
                n_estimators=hyperparameters.get('n_estimators', 100),
                max_depth=hyperparameters.get('max_depth', 6),
                learning_rate=hyperparameters.get('learning_rate', 0.1),
                random_state=hyperparameters.get('random_state', 42),
                verbosity=-1
            )
        elif algo_lower in ('svm', 'svr'):
            if not HAS_SKLEARN:
                raise ImportError("scikit-learn is required for SVM.")
            return SVR(
                C=hyperparameters.get('C', 1.0),
                gamma=hyperparameters.get('gamma', 'scale'),
                epsilon=hyperparameters.get('epsilon', 0.1),
                kernel=hyperparameters.get('kernel', 'rbf')
            )
        elif algo_lower == 'ridge':
            if not HAS_SKLEARN:
                raise ImportError("scikit-learn is required for Ridge.")
            return Ridge(
                alpha=hyperparameters.get('alpha', 1.0)
            )
        elif algo_lower in ('elasticnet', 'elastic net'):
            if not HAS_SKLEARN:
                raise ImportError("scikit-learn is required for ElasticNet.")
            return ElasticNet(
                alpha=hyperparameters.get('alpha', 1.0),
                l1_ratio=hyperparameters.get('l1_ratio', 0.5),
                random_state=hyperparameters.get('random_state', 42)
            )
        elif algo_lower == 'knn':
            if not HAS_SKLEARN:
                raise ImportError("scikit-learn is required for KNN.")
            return KNeighborsRegressor(
                n_neighbors=hyperparameters.get('n_neighbors', 5),
                weights=hyperparameters.get('weights', 'uniform')
            )
        elif algo_lower == 'mlp':
            if not HAS_SKLEARN:
                raise ImportError("scikit-learn is required for MLP.")
            return MLPRegressor(
                hidden_layer_sizes=hyperparameters.get('hidden_layer_sizes', (64, 32)),
                max_iter=hyperparameters.get('max_iter', 500),
                random_state=hyperparameters.get('random_state', 42)
            )
        else:
            # Fallback to Custom Ridge
            return CustomRidgeWrapper(alpha=hyperparameters.get('alpha', 1.0))
            
    # 2. Classification Models
    elif model_type == 'classification':
        class_weight = hyperparameters.get('class_weight')
        
        # Translate class_weight for xgboost and lightgbm before instantiating them
        params = dict(hyperparameters)
        scale_pos_weight = None
        if algo_lower in ('xgboost', 'xgb', 'lightgbm', 'lgbm') and 'class_weight' in params:
            cw = params.pop('class_weight')
            if cw and isinstance(cw, dict) and set(cw.keys()) == {0, 1}:
                scale_pos_weight = cw[1] / cw[0]
        
        if algo_lower in ('random forest', 'rf'):
            if not HAS_SKLEARN:
                raise ImportError("scikit-learn is required for Random Forest.")
            return RandomForestClassifier(
                n_estimators=hyperparameters.get('n_estimators', 100),
                max_depth=hyperparameters.get('max_depth', 6),
                min_samples_split=hyperparameters.get('min_samples_split', 2),
                max_features=hyperparameters.get('max_features', 'sqrt'),
                class_weight=class_weight,
                random_state=hyperparameters.get('random_state', 42)
            )
        elif algo_lower in ('gradient boosting', 'gbm'):
            if not HAS_SKLEARN:
                raise ImportError("scikit-learn is required for Gradient Boosting.")
            return GradientBoostingClassifier(
                n_estimators=hyperparameters.get('n_estimators', 100),
                max_depth=hyperparameters.get('max_depth', 3),
                learning_rate=hyperparameters.get('learning_rate', 0.1),
                random_state=hyperparameters.get('random_state', 42)
            )
        elif algo_lower in ('xgboost', 'xgb'):
            if not HAS_XGB:
                raise ImportError("xgboost is required for XGBoost models.")
            return XGBClassifier(
                n_estimators=hyperparameters.get('n_estimators', 100),
                max_depth=hyperparameters.get('max_depth', 6),
                learning_rate=hyperparameters.get('learning_rate', 0.1),
                scale_pos_weight=scale_pos_weight,
                random_state=hyperparameters.get('random_state', 42)
            )
        elif algo_lower in ('lightgbm', 'lgbm'):
            if not HAS_LGB:
                err_msg = f"lightgbm is unavailable. {LGB_IMPORT_ERROR or 'Import failed.'}"
                raise ImportError(err_msg)
            return LGBMClassifier(
                n_estimators=hyperparameters.get('n_estimators', 100),
                max_depth=hyperparameters.get('max_depth', 6),
                learning_rate=hyperparameters.get('learning_rate', 0.1),
                class_weight=class_weight if scale_pos_weight is None else None,
                scale_pos_weight=scale_pos_weight,
                random_state=hyperparameters.get('random_state', 42),
                verbosity=-1
            )
        elif algo_lower in ('svm', 'svc'):
            if not HAS_SKLEARN:
                raise ImportError("scikit-learn is required for SVM.")
            return SVC(
                C=hyperparameters.get('C', 1.0),
                gamma=hyperparameters.get('gamma', 'scale'),
                kernel=hyperparameters.get('kernel', 'rbf'),
                probability=True,
                class_weight=class_weight,
                random_state=hyperparameters.get('random_state', 42)
            )
        elif algo_lower == 'ridge':
            if not HAS_SKLEARN:
                raise ImportError("scikit-learn is required for Ridge.")
            return RidgeClassifier(
                alpha=hyperparameters.get('alpha', 1.0),
                class_weight=class_weight
            )
        elif algo_lower in ('elasticnet', 'elastic net'):
            if not HAS_SKLEARN:
                raise ImportError("scikit-learn is required for ElasticNet.")
            # For classification, LogisticRegression with elasticnet penalty
            return LogisticRegression(
                penalty='elasticnet',
                solver='saga',
                C=1.0 / max(1e-9, hyperparameters.get('alpha', 1.0)),
                l1_ratio=hyperparameters.get('l1_ratio', 0.5),
                class_weight=class_weight,
                random_state=hyperparameters.get('random_state', 42),
                max_iter=hyperparameters.get('max_iter', 1000)
            )
        elif algo_lower == 'knn':
            if not HAS_SKLEARN:
                raise ImportError("scikit-learn is required for KNN.")
            return KNeighborsClassifier(
                n_neighbors=hyperparameters.get('n_neighbors', 5),
                weights=hyperparameters.get('weights', 'uniform')
            )
        elif algo_lower == 'mlp':
            if not HAS_SKLEARN:
                raise ImportError("scikit-learn is required for MLP.")
            return MLPClassifier(
                hidden_layer_sizes=hyperparameters.get('hidden_layer_sizes', (64, 32)),
                max_iter=hyperparameters.get('max_iter', 500),
                random_state=hyperparameters.get('random_state', 42)
            )
        else:
            # Fallback to Custom Ridge wrapper (adapted for classification predictions)
            return CustomRidgeWrapper(alpha=hyperparameters.get('alpha', 1.0))
            
    raise ValueError(f"Unknown model_type: {model_type}")
