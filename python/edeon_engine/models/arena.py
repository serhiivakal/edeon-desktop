"""
Edeon Engine — Arena
Multi-model orchestrator for concurrent QSAR training and evaluation.
"""

import os
import sys
import time
import json
import traceback
import math
import numpy as np

# We can import base helpers from other submodules
from .estimators import build_estimator, DEFAULT_PARAM_SPACE
from .evaluators import evaluate_regression, evaluate_classification, compute_importances, generate_learning_curve
from .validation import kfold_cv, y_scramble_test, _compute_scramble_verdict
from .search.bayesian import bayesian_search

def _get_algo_key(algo):
    algo_lower = algo.lower().strip()
    if algo_lower in ('random forest', 'rf'):
        return 'rf'
    elif algo_lower in ('gradient boosting', 'gbm'):
        return 'gbm'
    elif algo_lower in ('xgboost', 'xgboost', 'xgb'):
        return 'xgboost'
    elif algo_lower in ('lightgbm', 'lightgbm', 'lgbm'):
        return 'lightgbm'
    elif algo_lower in ('svm', 'svr', 'svc'):
        return 'svm'
    elif algo_lower == 'ridge':
        return 'ridge'
    elif algo_lower in ('elasticnet', 'elastic net'):
        return 'elasticnet'
    elif algo_lower == 'knn':
        return 'knn'
    elif algo_lower == 'mlp':
        return 'mlp'
    return 'rf'

def _run_arena_worker(X_train, X_test, y_train, y_test, smiles_train, smiles_val, valid_indices, split_idx,
                      algorithm, search_mode, config, feature_names):
    """
    Worker function executed in the concurrent process pool.
    """
    import sys
    import json
    
    def emit_arena_progress(stage, pct):
        payload = {
            "kind": "arena_progress",
            "algorithm": _get_algo_key(algorithm),
            "stage": stage,
            "pct": pct
        }
        sys.stdout.write(f"[ARENA_PROGRESS] {json.dumps(payload)}\n")
        sys.stdout.flush()
        
    emit_arena_progress("init", 10)
    
    try:
        model_type = config.get("model_type", "regression")
        cv_folds = int(config.get("cv_folds", 5))
        random_state = int(config.get("random_seed", 42))
        n_scramble = int(config.get("n_scramble", 10))
        
        base_params = {}
        best_params = {}
        search_results = None
        
        # Setup class weight/SMOTE mitigation if classification target
        mitigation = config.get("mitigation") or "none"
        if model_type == "classification" and mitigation == "class_weight":
            base_params["class_weight"] = "balanced"
            
        # Standardize arrays
        np_X_train = np.array(X_train)
        np_y_train = np.array(y_train)
        np_X_test = np.array(X_test)
        np_y_test = np.array(y_test)
        
        # Apply resampling strategy
        strategy = config.get("imbalance_strategy", "none")
        original_class_counts = None
        resampled_class_counts = None
        class_weights = None
        
        if model_type == "classification":
            from collections import Counter
            np_y_train = np_y_train.astype(int)
            np_y_test = np_y_test.astype(int)
            original_class_counts = dict(Counter(np_y_train.tolist()))
            
            if strategy != "none":
                from .imbalance import apply_imbalance_strategy
                X_tr_resamp, y_tr_resamp, cw = apply_imbalance_strategy(
                    np_X_train.tolist(), np_y_train.tolist(), strategy, random_state
                )
                np_X_train = np.array(X_tr_resamp)
                np_y_train = np.array(y_tr_resamp)
                class_weights = cw
                resampled_class_counts = dict(Counter(np_y_train.tolist()))
                if class_weights is not None:
                    base_params["class_weight"] = class_weights
            else:
                if mitigation == "smote":
                    from .trainers import apply_smote
                    np_X_train, np_y_train = apply_smote(np_X_train, np_y_train)
                    resampled_class_counts = dict(Counter(np_y_train.tolist()))
                elif mitigation == "class_weight":
                    base_params["class_weight"] = "balanced"
            
        # 1. Hyperparameter Search Phase
        if search_mode == "bayesian_quick":
            emit_arena_progress("search", 20)
            
            # Run quick Bayesian optimization (n_trials=20, cv_k=3)
            algo_key = _get_algo_key(algorithm)
            space_spec = DEFAULT_PARAM_SPACE.get(algo_key, {})
            
            search_start = time.perf_counter()
            search_res = bayesian_search(
                X=np_X_train.tolist(),
                y=np_y_train,
                smiles=smiles_train,
                algorithm=algorithm,
                model_type=model_type,
                base_params=base_params,
                space=space_spec,
                n_trials=20,
                timeout=None,
                cv_k=3,
                split_mode=config.get("split_mode", "random"),
                random_state=random_state,
                log_callback=None
            )
            best_params = search_res["best_params"]
            search_duration = time.perf_counter() - search_start
            
            search_results = {
                "mode": "bayesian",
                "n_trials": len(search_res["trials"]),
                "trials": search_res["trials"],
                "best_params": best_params,
                "best_score": search_res["best_score"],
                "search_duration_s": search_duration
            }
            
        final_params = {**base_params, **best_params}
        
        # 2. Main CV Phase
        emit_arena_progress("cv", 40)
        
        cv_config = {
            "model_type": model_type,
            "algorithm": algorithm,
            "split_mode": config.get("split_mode", "random"),
            "random_seed": random_state,
            "cv_folds": cv_folds,
            "hyperparameters": final_params
        }
        
        from .validation import kfold_cv_with_predictions
        cv_results, cv_fold_predictions = kfold_cv_with_predictions(
            X=X_train,
            y=y_train,
            smiles=smiles_train,
            k=cv_folds,
            split_mode=config.get("split_mode", "random"),
            random_state=random_state,
            model_type=model_type,
            algorithm=algorithm,
            config=cv_config
        )
        
        # 3. Main Fit & Test Phase
        emit_arena_progress("train", 60)
        
        model = build_estimator(model_type, algorithm, final_params)
        
        start_fit = time.perf_counter()
        if model_type == "regression":
            model.fit(np_X_train, np_y_train)
            train_preds = model.predict(np_X_train)
            test_preds = model.predict(np_X_test)
            
            metrics, plot_data = evaluate_regression(
                np_y_train.tolist(), train_preds.tolist(),
                np_y_test.tolist(), test_preds.tolist(),
                smiles_val, list(range(len(smiles_val))), split_idx
            )
        else:
            algo_lower = algorithm.lower().strip()
            if (algo_lower in ('gradient boosting', 'gbm')) and class_weights is not None:
                sample_weights = np.array([class_weights[yi] for yi in np_y_train.astype(int)])
                model.fit(np_X_train, np_y_train.astype(int), sample_weight=sample_weights)
            elif (algo_lower in ('gradient boosting', 'gbm')) and (mitigation == "class_weight" or strategy == "class_weight"):
                from sklearn.utils.class_weight import compute_sample_weight
                sample_weights = compute_sample_weight("balanced", np_y_train.astype(int))
                model.fit(np_X_train, np_y_train.astype(int), sample_weight=sample_weights)
            else:
                model.fit(np_X_train, np_y_train.astype(int))
                
            train_preds = model.predict(np_X_train)
            test_preds = model.predict(np_X_test)
            
            if hasattr(model, "predict_proba"):
                probas = model.predict_proba(np_X_test)
                if probas.shape[1] > 1:
                    test_proba = probas[:, 1]
                else:
                    test_proba = probas[:, 0]
            elif hasattr(model, "decision_function"):
                df = model.decision_function(np_X_test)
                test_proba = 1.0 / (1.0 + np.exp(-df))
            else:
                test_proba = test_preds.astype(float)
            
            metrics, plot_data = evaluate_classification(
                np_y_train.tolist(), train_preds.tolist(),
                np_y_test.tolist(), test_preds.tolist(),
                model=model, X_val=np_X_test
            )
            
        fit_duration = time.perf_counter() - start_fit
        
        # 4. Y-Scrambling Phase
        emit_arena_progress("scramble", 80)
        
        y_scramble_result = None
        if n_scramble > 0 and len(X_train) >= 10:
            def scramble_factory():
                return build_estimator(model_type, algorithm, final_params)
                
            primary_key = 'r2_val' if model_type == 'regression' else 'accuracy_val'
            true_score  = float(metrics.get(primary_key, 0.0))
            
            y_scramble_result = y_scramble_test(
                np.array(X_train), np.array(y_train),
                model_factory=scramble_factory,
                n_iterations=n_scramble,
                test_size=config.get("test_size", 0.2),
                random_state=random_state,
                model_type=model_type,
            )
            verdict_info = _compute_scramble_verdict(
                true_score,
                y_scramble_result['scrambled_mean'],
                y_scramble_result['scrambled_std'],
                y_scramble_result['scrambled_scores'],
            )
            y_scramble_result.update(verdict_info)
            y_scramble_result['true_score'] = true_score
            y_scramble_result['primary_metric'] = primary_key
            
        # 5. Importances
        ui_importances = compute_importances(model, feature_names, model_type)
        
        emit_arena_progress("done", 100)
        
        imbalance_data = {
            "strategy": strategy,
            "original_class_counts": original_class_counts,
            "resampled_class_counts": resampled_class_counts,
            "class_weights": class_weights
        }
        
        if metrics is not None:
            metrics["imbalance"] = imbalance_data
            
        # --- Applicability Domain calculation ---
        import pickle
        from edeon_engine.applicability import build_ad_reference, score_query
        
        ad = build_ad_reference(
            train_smiles=smiles_train,
            X_train=np.array(X_train),
            y_train=np.array(y_train),
            y_train_pred=np.array(train_preds),
        )
        
        test_ad = score_query(
            ad=ad,
            query_smiles=smiles_val,
            X_query=np.array(X_test),
            y_query=np.array(y_test) if model_type == "regression" else None,
            y_query_pred=np.array(test_preds) if model_type == "regression" else None,
        )
        
        ad_reference_bytes = list(pickle.dumps(ad))

        # --- SHAP Interpretability calculation ---
        from edeon_engine.interpret import explain_model
        
        np_X_train = np.array(X_train)
        rng_bg = np.random.default_rng(random_state)
        bg_indices = rng_bg.choice(np_X_train.shape[0], size=min(100, np_X_train.shape[0]), replace=False)
        X_train_bg = np_X_train[bg_indices]
        
        shap_dict = explain_model(
            estimator=model,
            algorithm=algorithm,
            model_type=model_type,
            X_train=np_X_train,
            X_eval=np.array(X_test),
            feature_names=feature_names,
            random_state=random_state
        )
        
        shap_values_bytes = list(pickle.dumps(shap_dict))
        x_train_bg_bytes = list(pickle.dumps(X_train_bg))
        estimator_bytes = list(pickle.dumps(model))
            
        # --- Scientific Diagnostics calculation ---
        diagnostics = None
        try:
            if model_type == "regression":
                from edeon_engine.diagnostics import regression_diagnostics
                diagnostics = regression_diagnostics(
                    y_true=np_y_test,
                    y_pred=test_preds,
                    y_train=np_y_train,
                    y_train_pred=train_preds,
                    ad_status=test_ad["overall_status"] if test_ad else ["in"] * len(y_test),
                    scramble_distribution=y_scramble_result if y_scramble_result and "error" not in y_scramble_result else None,
                    estimator=model,
                    X_train=np_X_train,
                    y_train_arr=np_y_train,
                    cv_k=cv_folds,
                    random_state=random_state
                )
            else:
                from edeon_engine.diagnostics import classification_diagnostics
                diagnostics = classification_diagnostics(
                    y_true=np_y_test,
                    y_pred=test_preds,
                    y_proba=test_proba,
                    cv_fold_predictions=cv_fold_predictions,
                    estimator=model,
                    X_train=np_X_train,
                    y_train_arr=np_y_train,
                    cv_k=cv_folds,
                    random_state=random_state
                )
        except Exception as diag_err:
            import sys
            sys.stderr.write(f"[WARNING] Failed to generate diagnostics in arena: {str(diag_err)}\n")
            diagnostics = None

        # --- Activity Cliffs calculation ---
        cliffs = []
        try:
            from edeon_engine.cliffs import detect_cliffs, render_thumbnail
            smiles_all = smiles_train + smiles_val
            y_all = np.concatenate([np_y_train, np_y_test])
            
            raw_cliffs = detect_cliffs(
                smiles=smiles_all,
                y=y_all,
                model_type=model_type,
                similarity_threshold=0.85,
                activity_gap=1.0,
                max_pairs=50
            )
            for c in raw_cliffs:
                c["thumb_i"] = render_thumbnail(c["smiles_i"])
                c["thumb_j"] = render_thumbnail(c["smiles_j"])
                cliffs.append(c)
        except Exception as cliff_err:
            import sys
            sys.stderr.write(f"[WARNING] Failed to generate activity cliffs in arena: {str(cliff_err)}\n")
            cliffs = []

        return {
            "algorithm": _get_algo_key(algorithm),
            "metrics": metrics,
            "cv_results": cv_results,
            "y_scramble": y_scramble_result,
            "search_results": search_results,
            "importances": ui_importances,
            "plot_data": plot_data,
            "duration_s": fit_duration,
            "error": None,
            "imbalance": imbalance_data,
            "ad_reference": ad_reference_bytes,
            "test_ad": test_ad,
            "shap_values": shap_values_bytes,
            "x_train_bg": x_train_bg_bytes,
            "estimator": estimator_bytes,
            "diagnostics": diagnostics,
            "cliffs": cliffs,
            "curated_smiles": smiles_all,
            "curated_activities": y_all.tolist()
        }
        
    except Exception as e:
        emit_arena_progress("failed", 100)
        return {
            "algorithm": _get_algo_key(algorithm),
            "metrics": {},
            "cv_results": [],
            "y_scramble": None,
            "search_results": None,
            "importances": {},
            "plot_data": {},
            "duration_s": 0.0,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

def run_arena(curated_smiles, curated_activities, config) -> dict:
    """
    Runs multi-model arena portfolio training.
    """
    import os
    import concurrent.futures
    from .curation import curate_dataset
    from .featurizers import run_featurizers
    from .splitters import split_dataset
    from .provenance import collect_provenance
    
    # 1. Featurize once
    selections = config.get("featurizer_selections")
    X_matrix, feature_names = run_featurizers(curated_smiles, selections)
    X_rows = X_matrix.tolist()
    y_valid = list(curated_activities)
    
    # 2. Split once
    split_mode = config.get("split_mode", "random")
    test_size = float(config.get("test_size", 0.2))
    random_state = int(config.get("random_seed", 42))
    cv_k = int(config.get("cv_folds", 5))
    model_type = config.get("model_type", "regression")
    
    train_idx, test_idx = split_dataset(
        X_rows, y_valid, curated_smiles, split_mode, test_size, random_state, model_type
    )
    
    X_train = [X_rows[i] for i in train_idx]
    X_test = [X_rows[i] for i in test_idx]
    y_train = [y_valid[i] for i in train_idx]
    y_test = [y_valid[i] for i in test_idx]
    
    smiles_train = [curated_smiles[i] for i in train_idx]
    smiles_val = [curated_smiles[i] for i in test_idx]
    
    # Run curation pipeline again to get the report
    curation = curate_dataset(curated_smiles, curated_activities, model_type)
    
    arena_config = config.get("arena", {})
    algos = arena_config.get("algorithms", ["rf", "gbm", "svm"])
    per_algo_search = arena_config.get("per_algo_search", "default")
    
    # 3. Parallelize execution using ProcessPoolExecutor
    models_res = []
    max_workers = min(len(algos), os.cpu_count() or 4)
    if max_workers < 1:
        max_workers = 1
        
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for algo in algos:
            f = executor.submit(
                _run_arena_worker,
                X_train=X_train,
                X_test=X_test,
                y_train=y_train,
                y_test=y_test,
                smiles_train=smiles_train,
                smiles_val=smiles_val,
                valid_indices=list(range(len(curated_smiles))),
                split_idx=len(train_idx),
                algorithm=algo,
                search_mode=per_algo_search,
                config=config,
                feature_names=feature_names
            )
            futures.append(f)
            
        for f in concurrent.futures.as_completed(futures):
            try:
                models_res.append(f.result())
            except Exception as e:
                models_res.append({
                    "algorithm": "unknown",
                    "error": str(e),
                    "traceback": traceback.format_exc()
                })
                
    # Sort and rank models by primary metric descending
    primary_metric_key = 'r2_val' if model_type == 'regression' else 'accuracy_val'
    
    # Help sorting by primary score. Non-errored models sort first.
    def get_score_sort(m):
        if m.get("error"):
            return -float('inf')
        return m.get("metrics", {}).get(primary_metric_key, -float('inf'))
        
    sorted_models = sorted(models_res, key=get_score_sort, reverse=True)
    
    ranking = []
    rank_counter = 1
    for m in sorted_models:
        algo = m.get("algorithm")
        if m.get("error"):
            ranking.append({
                "algorithm": algo,
                "primary_score": 0.0,
                "rank": None
            })
        else:
            score = m.get("metrics", {}).get(primary_metric_key, 0.0)
            ranking.append({
                "algorithm": algo,
                "primary_score": score,
                "rank": rank_counter
            })
            rank_counter += 1
            
    provenance = collect_provenance(config, curated_smiles, curated_activities)
    
    return {
        "shared": {
            "curation_report": curation["report"],
            "feature_names": feature_names,
            "split_mode": split_mode,
            "cv_k": cv_k,
            "test_indices": test_idx
        },
        "models": sorted_models,
        "ranking": ranking,
        "provenance": provenance,
        "curation_report": curation["report"]
    }
