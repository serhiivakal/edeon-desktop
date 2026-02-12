"""
Edeon Engine — Grid Search
Grid Search hyperparameter optimizer implementation.
"""

import time
from sklearn.model_selection import ParameterGrid
from ..validation import kfold_cv
from . import primary_metric_name

def grid_search(X, y, smiles, algorithm, model_type, base_params, grid,
                cv_k, split_mode, random_state, log_callback) -> dict:
    """
    Iterates over ParameterGrid(grid) to find optimal parameters.
    """
    trials = []
    best_trial_id = 0
    best_params = {}
    best_score = -float('inf')
    
    # Initialize basic grid search combinations
    param_grid = ParameterGrid(grid)
    metric_name = "r2" if model_type == "regression" else "accuracy"
    
    for trial_id, combo in enumerate(param_grid):
        start_time = time.perf_counter()
        
        # Build training config for this iteration
        config = {
            "model_type": model_type,
            "algorithm": algorithm,
            "split_mode": split_mode,
            "random_seed": random_state,
            "cv_folds": cv_k,
            "hyperparameters": {**base_params, **combo}
        }
        
        try:
            cv_results = kfold_cv(X, y, smiles, cv_k, split_mode, random_state, model_type, algorithm, config)
            
            mean_score = 0.0
            std_score = 0.0
            fold_scores = []
            
            if cv_results:
                for fold in cv_results:
                    if fold.get("fold") != "summary":
                        # Regression is 'r2_val', Classification is 'accuracy_val'
                        score_key = "r2_val" if model_type == "regression" else "accuracy_val"
                        fold_scores.append(fold.get(score_key, 0.0))
                
                if cv_results[-1].get("fold") == "summary":
                    mean_score = cv_results[-1].get("mean", 0.0)
                    std_score = cv_results[-1].get("std", 0.0)
            
        except Exception as e:
            mean_score = 0.0
            std_score = 0.0
            fold_scores = []
            
        duration_s = time.perf_counter() - start_time
        
        trial_data = {
            "trial_id": trial_id,
            "params": combo,
            "mean_cv_score": mean_score,
            "std_cv_score": std_score,
            "fold_scores": fold_scores,
            "duration_s": duration_s
        }
        
        trials.append(trial_data)
        
        if mean_score > best_score:
            best_score = mean_score
            best_params = combo
            best_trial_id = trial_id
            
        # Stream trial progress to the frontend
        if log_callback:
            log_callback(trial_id, combo, mean_score, std_score, duration_s)
            
    return {
        "trials": trials,
        "best_trial_id": best_trial_id,
        "best_params": best_params,
        "best_score": best_score,
        "primary_metric": metric_name
    }
