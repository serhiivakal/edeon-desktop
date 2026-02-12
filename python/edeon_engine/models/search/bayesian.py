"""
Edeon Engine — Bayesian Search
Optuna-based Bayesian optimization hyperparameter search.
"""

import time
import optuna
from ..validation import kfold_cv
from . import primary_metric_name

def bayesian_search(X, y, smiles, algorithm, model_type, base_params, space,
                    n_trials, timeout, cv_k, split_mode, random_state,
                    log_callback) -> dict:
    """
    Runs Optuna-based Bayesian hyperparameter sweeps to maximize the validation score.
    """
    # Silence Optuna verbose output to keep JSON-RPC channel clean
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    
    # Create Study
    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=random_state)
    )
    
    def objective(trial):
        params = {}
        for name, spec in space.items():
            if spec["type"] == "int":
                params[name] = trial.suggest_int(name, spec["low"], spec["high"], log=spec.get("log", False))
            elif spec["type"] == "float":
                params[name] = trial.suggest_float(name, spec["low"], spec["high"], log=spec.get("log", False))
            elif spec["type"] == "categorical":
                params[name] = trial.suggest_categorical(name, spec["choices"])
                
        start_time = time.perf_counter()
        
        # Build training config for this iteration
        config = {
            "model_type": model_type,
            "algorithm": algorithm,
            "split_mode": split_mode,
            "random_seed": random_state,
            "cv_folds": cv_k,
            "hyperparameters": {**base_params, **params}
        }
        
        try:
            cv_results = kfold_cv(X, y, smiles, cv_k, split_mode, random_state, model_type, algorithm, config)
            
            mean_score = 0.0
            std_score = 0.0
            
            if cv_results and cv_results[-1].get("fold") == "summary":
                mean_score = cv_results[-1].get("mean", 0.0)
                std_score = cv_results[-1].get("std", 0.0)
                
        except Exception:
            mean_score = 0.0
            std_score = 0.0
            
        duration_s = time.perf_counter() - start_time
        
        # Save attributes on the trial object
        trial.set_user_attr("mean_score", mean_score)
        trial.set_user_attr("std_score", std_score)
        trial.set_user_attr("duration_s", duration_s)
        
        # Stream trial progress to the frontend
        if log_callback:
            log_callback(trial.number, params, mean_score, std_score, duration_s)
            
        return mean_score

    study.optimize(objective, n_trials=n_trials, timeout=timeout)
    
    # Reconstruct trials results list
    trials = []
    for t in study.trials:
        if t.state == optuna.trial.TrialState.COMPLETE:
            trials.append({
                "trial_id": t.number,
                "params": t.params,
                "mean_cv_score": t.user_attrs.get("mean_score", 0.0),
                "std_cv_score": t.user_attrs.get("std_score", 0.0),
                "fold_scores": [],
                "duration_s": t.user_attrs.get("duration_s", 0.0)
            })
            
    best_trial_id = study.best_trial.number if study.trials else 0
    best_params = study.best_params
    best_score = study.best_value if study.trials else 0.0
    metric_name = "r2" if model_type == "regression" else "accuracy"
    
    return {
        "trials": trials,
        "best_trial_id": best_trial_id,
        "best_params": best_params,
        "best_score": best_score,
        "primary_metric": metric_name
    }
