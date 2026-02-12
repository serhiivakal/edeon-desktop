"""
Edeon Engine — Imbalance
Provides strategies to address class imbalance for classification models.
"""

from collections import Counter
import numpy as np

def apply_imbalance_strategy(X_train, y_train, strategy: str, random_state: int):
    """
    strategy: 'none' | 'class_weight' | 'smote' | 'undersample'
    Returns (X_train_resampled, y_train_resampled, class_weight_dict_or_None)
    """
    if strategy == "none":
        return X_train, y_train, None
        
    if strategy == "class_weight":
        from sklearn.utils.class_weight import compute_class_weight
        classes = np.unique(y_train)
        weights = compute_class_weight("balanced", classes=classes, y=y_train)
        return X_train, y_train, dict(zip(classes.tolist(), weights.tolist()))
        
    if strategy == "smote":
        try:
            from imblearn.over_sampling import SMOTE
        except ImportError:
            raise ImportError("imbalanced-learn is required for SMOTE oversampling. Please run pip install imbalanced-learn.")
            
        counts = Counter(y_train)
        if len(counts) < 2:
            return X_train, y_train, None
            
        k = min(5, min(counts.values()) - 1)
        if k < 1:
            raise ValueError("Too few minority-class samples for SMOTE (need ≥2).")
            
        sm = SMOTE(random_state=random_state, k_neighbors=k)
        Xr, yr = sm.fit_resample(X_train, y_train)
        
        if hasattr(Xr, "tolist"):
            Xr = Xr.tolist()
        if hasattr(yr, "tolist"):
            yr = yr.tolist()
            
        return Xr, yr, None
        
    if strategy == "undersample":
        try:
            from imblearn.under_sampling import RandomUnderSampler
        except ImportError:
            raise ImportError("imbalanced-learn is required for random under-sampling. Please run pip install imbalanced-learn.")
            
        rus = RandomUnderSampler(random_state=random_state)
        Xr, yr = rus.fit_resample(X_train, y_train)
        
        if hasattr(Xr, "tolist"):
            Xr = Xr.tolist()
        if hasattr(yr, "tolist"):
            yr = yr.tolist()
            
        return Xr, yr, None
        
    raise ValueError(f"Unknown imbalance strategy: {strategy}")
