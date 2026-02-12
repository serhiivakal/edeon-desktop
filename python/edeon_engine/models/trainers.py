"""
Edeon Engine — Trainers
Core QSAR training pipelines supporting scikit-learn (Random Forest, SVM, Gradient Boosting, Ridge)
and zero-dependency fallback ridge solvers.
"""

import math
from .featurizers import extract_descriptors, compute_morgan_fingerprints
from .evaluators import evaluate_regression, evaluate_classification, compute_importances, generate_learning_curve
from .estimators import build_estimator

# Try to import scikit-learn and numpy
HAS_SKLEARN = False
try:
    import numpy as np
    from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier, GradientBoostingRegressor, GradientBoostingClassifier
    from sklearn.svm import SVR, SVC
    from sklearn.linear_model import Ridge, RidgeClassifier
    HAS_SKLEARN = True
except ImportError:
    try:
        import numpy as np
    except ImportError:
        np = None

def solve_linear_system(A, b):
    """Solves A * x = b using Gaussian elimination with partial pivoting."""
    n = len(A)
    # Copy A and b
    M = [row[:] for row in A]
    for i in range(n):
        M[i].append(b[i])
        
    for i in range(n):
        # Find pivot
        max_row = i
        for r in range(i + 1, n):
            if abs(M[r][i]) > abs(M[max_row][i]):
                max_row = r
        M[i], M[max_row] = M[max_row], M[i]
        
        # Pivot is M[i][i]
        pivot = M[i][i]
        if abs(pivot) < 1e-9:
            # Singular matrix or highly collinear, return zero coefs or regularized values
            continue
            
        for col in range(i, n + 1):
            M[i][col] /= pivot
            
        for r in range(n):
            if r != i:
                factor = M[r][i]
                for col in range(i, n + 1):
                    M[r][col] -= factor * M[i][col]
                    
    return [row[n] for row in M]

def custom_ridge_fit(X, y, alpha=1.0):
    """
    A simple, pure-Python/NumPy or pure-Python Ridge regression solver.
    Standardizes X, fits coefficients, returns predictions.
    """
    n_samples = len(X)
    n_features = len(X[0])
    
    # Standardize X
    X_mean = [sum(col) / n_samples for col in zip(*X)]
    X_std = []
    for j in range(n_features):
        variance = sum((row[j] - X_mean[j]) ** 2 for row in X) / n_samples
        X_std.append(math.sqrt(variance) if variance > 0 else 1.0)
        
    X_scaled = []
    for row in X:
        X_scaled.append([(row[j] - X_mean[j]) / X_std[j] for j in range(n_features)])
        
    # Fit y mean
    y_mean = sum(y) / n_samples
    y_centered = [yi - y_mean for yi in y]
    
    # Solve (Xt * X + alpha * I) * coef = Xt * y
    XtX = [[0.0 for _ in range(n_features)] for _ in range(n_features)]
    Xty = [0.0 for _ in range(n_features)]
    
    for row, yi in zip(X_scaled, y_centered):
        for i in range(n_features):
            Xty[i] += row[i] * yi
            for j in range(n_features):
                XtX[i][j] += row[i] * row[j]
                
    # Add regularization
    for i in range(n_features):
        XtX[i][i] += alpha
        
    # Gaussian elimination to solve XtX * coef = Xty
    coef = solve_linear_system(XtX, Xty)
    
    def predict(X_new):
        preds = []
        for row in X_new:
            val = y_mean
            for j in range(n_features):
                val += coef[j] * (row[j] - X_mean[j]) / X_std[j]
            preds.append(val)
        return preds
        
    return coef, predict

def apply_smote(X, y):
    """
    Applies standard SMOTE algorithm to balance classes 0 and 1.
    X: np.ndarray, y: np.ndarray
    Returns balanced X_resampled, y_resampled
    """
    if np is None:
        raise ImportError("numpy is required for SMOTE resampler.")
    classes, counts = np.unique(y, return_counts=True)
    if len(classes) < 2:
        return X, y
    
    minority_class = classes[np.argmin(counts)]
    majority_class = classes[np.argmax(counts)]
    
    n_majority = counts[np.argmax(counts)]
    n_minority = counts[np.argmin(counts)]
    
    if n_minority <= 1:
        # Not enough samples to interpolate, fall back to simple random oversampling
        idx_minority = np.where(y == minority_class)[0]
        extra_idx = np.random.choice(idx_minority, size=n_majority - n_minority, replace=True)
        X_extra = X[extra_idx]
        y_extra = y[extra_idx]
        return np.vstack([X, X_extra]), np.hstack([y, y_extra])
        
    idx_minority = np.where(y == minority_class)[0]
    minority_samples = X[idx_minority]
    
    # We need to generate (n_majority - n_minority) synthetic samples
    n_synthetic = n_majority - n_minority
    synthetic_samples = []
    
    for _ in range(n_synthetic):
        # Pick a random minority sample
        idx_a = np.random.randint(0, n_minority)
        sample_a = minority_samples[idx_a]
        
        # Find nearest neighbor among other minority samples
        # Compute distances from sample_a to all other minority samples
        dists = np.sum((minority_samples - sample_a) ** 2, axis=1)
        # Sort distances, exclude the sample itself (dist = 0)
        neighbors = np.argsort(dists)
        # Nearest neighbor (excluding self at index 0)
        idx_b = neighbors[1] if len(neighbors) > 1 else neighbors[0]
        sample_b = minority_samples[idx_b]
        
        # Interpolate
        lam = np.random.rand()
        synth = sample_a + lam * (sample_b - sample_a)
        synthetic_samples.append(synth)
        
    X_resampled = np.vstack([X, np.array(synthetic_samples)])
    y_resampled = np.hstack([y, np.full(n_synthetic, minority_class)])
    
    return X_resampled, y_resampled


def train_model_batch(smiles_list, activities, config):
    """
    Train a custom model on smiles + activities.
    config: {
      "model_type": "regression" | "classification",
      "algorithm": "Random Forest" | "SVM" | "Gradient Boosting" | "Ridge",
      "features": ["MW", "LogP", "TPSA", "HBD", "HBA", "RotBonds", "MorganFingerprints"],
      "hyperparameters": {"n_estimators": 100, ...}
    }
    """
    model_type = config.get("model_type", "regression")
    
    # Run Data Curation Pipeline
    from .curation import curate_dataset
    curation = curate_dataset(smiles_list, activities, model_type)
    if len(curation["smiles"]) < 10:
        raise ValueError(f"After curation only {len(curation['smiles'])} compounds remain. Minimum 10 required.")
        
    curated_smiles = curation["smiles"]
    curated_activities = curation["activities"]
    
    algorithm = config.get("algorithm", "Random Forest")
    
    # Get selections or fallback to legacy features
    from .featurizers import run_featurizers, _legacy_features_to_selections
    import sys
    
    selections = config.get("featurizer_selections")
    if selections is None:
        legacy_features = config.get("features")
        if legacy_features is not None:
            # Emit deprecation warning into the training log (represented as sys.stderr output)
            sys.stderr.write("[WARNING] Legacy config features detected. Translated to featurizer_selections via shim.\n")
            selections = _legacy_features_to_selections(legacy_features)
        else:
            # Default selections (Lipinski preset)
            from .featurizers.descriptors_2d import LIPINSKI
            selections = [{"id": "descriptors_2d", "params": {"selected": list(LIPINSKI)}}]
            
    # Now run the new featurization pipeline!
    X_matrix, feature_names = run_featurizers(curated_smiles, selections)
    y_valid = list(curated_activities)
    valid_indices = list(range(len(curated_smiles)))
    X_rows = X_matrix.tolist()
    
    if len(X_rows) < 5:
        raise ValueError("Too few valid compounds parsed successfully. Minimum 5 compounds required.")
        
    # 3. Train & Validation Split
    n_samples = len(X_rows)

    # Read validation strategy from config
    split_mode   = config.get('split_mode', 'random')
    test_size    = float(config.get('test_size', 0.2))
    random_state = int(config.get('random_seed', 42))
    cv_folds     = int(config.get('cv_folds', 5))

    from .splitters import split_dataset
    train_idx, val_idx = split_dataset(
        X_rows, y_valid, curated_smiles, split_mode, test_size, random_state, model_type
    )

    # Build actual sub-arrays from index lists
    X_train = [X_rows[i] for i in train_idx]
    X_val   = [X_rows[i] for i in val_idx]
    y_train = [y_valid[i] for i in train_idx]
    y_val   = [y_valid[i] for i in val_idx]

    # Synthetic split_idx used by evaluators for learning-curve labelling
    split_idx = len(train_idx)
    
    # Dual path execution
    if HAS_SKLEARN:
        # standard sklearn training
        np_X_train = np.array(X_train)
        np_y_train = np.array(y_train)
        np_X_val = np.array(X_val)
        np_y_val = np.array(y_val)
        
        def _get_algo_key(algo):
            algo_lower = algo.lower().strip()
            if algo_lower in ('random forest', 'rf'):
                return 'rf'
            elif algo_lower in ('gradient boosting', 'gbm'):
                return 'gbm'
            elif algo_lower in ('xgboost', 'xgb'):
                return 'xgboost'
            elif algo_lower in ('lightgbm', 'lgbm'):
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

        # Hyperparameter search execution
        search_config = config.get("search", {"mode": "manual"})
        search_mode = search_config.get("mode", "manual")
        search_results = None
        best_params = {}
        
        # Static parameters
        base_params = config.get("hyperparameters", {}).copy()
        mitigation = base_params.pop("mitigation", None) or config.get("mitigation") or "none"
        
        if search_mode in ("grid", "bayesian"):
            import sys
            import time
            import json
            from .estimators import DEFAULT_PARAM_SPACE
            
            search_start_time = time.perf_counter()
            algo_key = _get_algo_key(algorithm)
            
            def log_callback(trial_id, params_trial, mean, std, duration):
                payload = {
                    "kind": "trial",
                    "trial_id": trial_id,
                    "params": params_trial,
                    "mean_score": mean,
                    "std_score": std,
                    "duration_s": duration,
                }
                sys.stdout.write(f"[TRIAL_RESULT] {json.dumps(payload)}\n")
                sys.stdout.flush()
                
            smiles_train = [curated_smiles[i] for i in train_idx]
            
            if search_mode == "grid":
                grid_spec = search_config.get("grid")
                if not grid_spec:
                    grid_spec = {}
                    default_space = DEFAULT_PARAM_SPACE.get(algo_key, {})
                    for param_name, spec in default_space.items():
                        if spec["type"] == "categorical":
                            grid_spec[param_name] = spec["choices"][:2]
                        elif spec["type"] == "int":
                            low, high = spec["low"], spec["high"]
                            grid_spec[param_name] = [low, high]
                        elif spec["type"] == "float":
                            low, high = spec["low"], spec["high"]
                            grid_spec[param_name] = [low, high]
                
                from .search.grid import grid_search
                search_res = grid_search(
                    X=X_train,
                    y=np.array(y_train),
                    smiles=smiles_train,
                    algorithm=algorithm,
                    model_type=model_type,
                    base_params=base_params,
                    grid=grid_spec,
                    cv_k=cv_folds,
                    split_mode=split_mode,
                    random_state=random_state,
                    log_callback=log_callback
                )
            else: # bayesian
                bayesian_spec = search_config.get("bayesian", {})
                n_trials = bayesian_spec.get("n_trials", 30)
                timeout = bayesian_spec.get("timeout_seconds")
                space_spec = bayesian_spec.get("param_space")
                
                if not space_spec:
                    space_spec = DEFAULT_PARAM_SPACE.get(algo_key, {})
                    
                from .search.bayesian import bayesian_search
                search_res = bayesian_search(
                    X=X_train,
                    y=np.array(y_train),
                    smiles=smiles_train,
                    algorithm=algorithm,
                    model_type=model_type,
                    base_params=base_params,
                    space=space_spec,
                    n_trials=n_trials,
                    timeout=timeout,
                    cv_k=cv_folds,
                    split_mode=split_mode,
                    random_state=random_state,
                    log_callback=log_callback
                )
                
            best_params = search_res["best_params"]
            search_duration = time.perf_counter() - search_start_time
            
            search_results = {
                "mode": search_mode,
                "n_trials": len(search_res["trials"]),
                "trials": search_res["trials"],
                "best_params": best_params,
                "best_score": search_res["best_score"],
                "search_duration_s": search_duration
            }
        
        # Merge best params with base params
        final_params = {**base_params, **best_params}
        
        strategy = config.get("imbalance_strategy", "none")
        original_class_counts = None
        resampled_class_counts = None
        class_weights = None

        if model_type == "classification":
            from collections import Counter
            np_y_train = np_y_train.astype(int)
            np_y_val = np_y_val.astype(int)
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
                    final_params["class_weight"] = class_weights
            else:
                if mitigation == "smote":
                    np_X_train, np_y_train = apply_smote(np_X_train, np_y_train)
                    resampled_class_counts = dict(Counter(np_y_train.tolist()))
                elif mitigation == "class_weight":
                    from sklearn.utils.class_weight import compute_class_weight
                    classes = np.unique(np_y_train)
                    weights = compute_class_weight("balanced", classes=classes, y=np_y_train)
                    class_weights = dict(zip(classes.tolist(), weights.tolist()))
                    final_params["class_weight"] = class_weights
        
        # Build the estimator using the unified factory
        model = build_estimator(model_type, algorithm, final_params)
        
        if model_type == "regression":
            model.fit(np_X_train, np_y_train)
            train_preds = model.predict(np_X_train)
            val_preds = model.predict(np_X_val)
            
            # Evaluate using evaluator submodule
            metrics, plot_data = evaluate_regression(
                y_train, train_preds, y_val, val_preds, curated_smiles, valid_indices, split_idx
            )
            
        else: # Classification
            # Special sample weight fit for Gradient Boosting / other models if needed
            algo_lower = algorithm.lower().strip()
            if (algo_lower in ('gradient boosting', 'gbm')) and class_weights is not None:
                sample_weights = np.array([class_weights[yi] for yi in np_y_train])
                model.fit(np_X_train, np_y_train, sample_weight=sample_weights)
            elif (algo_lower in ('gradient boosting', 'gbm')) and (mitigation == "class_weight" or strategy == "class_weight"):
                from sklearn.utils.class_weight import compute_sample_weight
                sample_weights = compute_sample_weight("balanced", np_y_train)
                model.fit(np_X_train, np_y_train, sample_weight=sample_weights)
            else:
                model.fit(np_X_train, np_y_train)
                
            train_preds = model.predict(np_X_train)
            val_preds = model.predict(np_X_val)
            
            if hasattr(model, "predict_proba"):
                probas = model.predict_proba(np_X_val)
                if probas.shape[1] > 1:
                    val_proba = probas[:, 1]
                else:
                    val_proba = probas[:, 0]
            elif hasattr(model, "decision_function"):
                df = model.decision_function(np_X_val)
                val_proba = 1.0 / (1.0 + np.exp(-df))
            else:
                val_proba = val_preds.astype(float)
                
            # Evaluate using evaluator submodule
            metrics, plot_data = evaluate_classification(
                y_train, train_preds, y_val, val_preds, model=model, X_val=np_X_val
            )
            
        # Feature importances using evaluator submodule
        ui_importances = compute_importances(model, feature_names, model_type)
        
    else:
        # Zero-dependency Pure Python standard solver path
        search_results = None
        final_params = config.get("hyperparameters", {}).copy()
        mitigation = final_params.pop("mitigation", None) or config.get("mitigation") or "none"
        strategy = config.get("imbalance_strategy", "none")
        
        original_class_counts = None
        resampled_class_counts = None
        class_weights = None
        
        if model_type == "classification":
            from collections import Counter
            original_class_counts = dict(Counter(y_train))
            
            if strategy != "none":
                try:
                    from .imbalance import apply_imbalance_strategy
                    X_tr_resamp, y_tr_resamp, cw = apply_imbalance_strategy(
                        X_train, y_train, strategy, random_state
                    )
                    X_train = X_tr_resamp
                    y_train = y_tr_resamp
                    class_weights = cw
                    resampled_class_counts = dict(Counter(y_train))
                    if class_weights is not None:
                        final_params["class_weight"] = class_weights
                except Exception:
                    pass
            else:
                if mitigation == "smote":
                    try:
                        if np is None:
                            raise ImportError("numpy is not available")
                        np_X_train = np.array(X_train)
                        np_y_train = np.array(y_train)
                        np_X_train, np_y_train = apply_smote(np_X_train, np_y_train)
                        X_train = np_X_train.tolist()
                        y_train = np_y_train.tolist()
                        resampled_class_counts = dict(Counter(y_train))
                    except ImportError:
                        pass
                elif mitigation == "class_weight":
                    try:
                        from sklearn.utils.class_weight import compute_class_weight
                        classes = np.unique(y_train)
                        weights = compute_class_weight("balanced", classes=classes, y=y_train)
                        class_weights = dict(zip(classes.tolist(), weights.tolist()))
                        final_params["class_weight"] = class_weights
                    except Exception:
                        pass

        coefs, predict_fn = custom_ridge_fit(X_train, y_train, alpha=1.0)
        train_preds = predict_fn(X_train)
        val_preds = predict_fn(X_val)
        
        if model_type == "regression":
            # Evaluate using evaluator submodule
            metrics, plot_data = evaluate_regression(
                y_train, train_preds, y_val, val_preds, curated_smiles, valid_indices, split_idx
            )
        else: # Classification
            # Evaluate using evaluator submodule
            metrics, plot_data = evaluate_classification(
                y_train, train_preds, y_val, val_preds
            )
            if np is None:
                raise ImportError("numpy is required for classification evaluation")
            val_proba = np.array(val_preds, dtype=float)
            
        # Calculate custom feature importances using evaluator submodule
        ui_importances = compute_importances(None, feature_names, model_type, coefs=coefs)
        
    # Calculate learning curve details using evaluator submodule
    learning_curve = generate_learning_curve(metrics, model_type, n_samples, split_idx)

    # Cross-validation stability analysis
    cv_results = []
    cv_fold_predictions = []
    if cv_folds >= 2 and n_samples >= cv_folds * 3:
        try:
            from .validation import kfold_cv_with_predictions
            smiles_for_cv = [curated_smiles[i] for i in valid_indices]
            cv_results, cv_fold_predictions = kfold_cv_with_predictions(
                X_rows, y_valid, smiles_for_cv,
                k=cv_folds,
                split_mode=split_mode,
                random_state=random_state,
                model_type=model_type,
                algorithm=algorithm,
                config=config,
            )
        except Exception as cv_err:
            cv_results = [{'error': str(cv_err)}]
            cv_fold_predictions = []

    # Y-Scrambling sanity check
    y_scramble_result = None
    n_scramble = int(config.get('n_scramble', 10))
    if n_scramble > 0 and HAS_SKLEARN and n_samples >= 10:
        try:
            from .validation import y_scramble_test, _compute_scramble_verdict

            def scramble_factory():
                return build_estimator(model_type, algorithm, final_params)

            primary_key = 'r2_val' if model_type == 'regression' else 'accuracy_val'
            true_score  = float(metrics.get(primary_key, 0.0))

            y_scramble_result = y_scramble_test(
                np.array(X_rows), np.array(y_valid),
                model_factory=scramble_factory,
                n_iterations=n_scramble,
                test_size=test_size,
                random_state=random_state,
                model_type=model_type,
            )
            # Finalize with the real model's score
            verdict_info = _compute_scramble_verdict(
                true_score,
                y_scramble_result['scrambled_mean'],
                y_scramble_result['scrambled_std'],
                y_scramble_result['scrambled_scores'],
            )
            y_scramble_result.update(verdict_info)
            y_scramble_result['true_score'] = true_score
            y_scramble_result['primary_metric'] = primary_key
        except Exception as scramble_err:
            y_scramble_result = {'error': str(scramble_err)}

    from .provenance import collect_provenance
    provenance_data = collect_provenance(config, smiles_list, activities)

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
    
    train_smiles_split = [curated_smiles[i] for i in train_idx]
    val_smiles_split = [curated_smiles[i] for i in val_idx]
    
    ad = build_ad_reference(
        train_smiles=train_smiles_split,
        X_train=np.array(X_train),
        y_train=np.array(y_train),
        y_train_pred=np.array(train_preds),
    )
    
    test_ad = score_query(
        ad=ad,
        query_smiles=val_smiles_split,
        X_query=np.array(X_val),
        y_query=np.array(y_val) if model_type == "regression" else None,
        y_query_pred=np.array(val_preds) if model_type == "regression" else None,
    )
    
    ad_reference_bytes = list(pickle.dumps(ad))

    # --- SHAP Interpretability calculation ---
    from edeon_engine.interpret import explain_model
    
    np_X_train = np.array(X_train)
    rng_bg = np.random.default_rng(random_state)
    bg_indices = rng_bg.choice(np_X_train.shape[0], size=min(100, np_X_train.shape[0]), replace=False)
    X_train_bg = np_X_train[bg_indices]
    
    shap_dict = explain_model(
        estimator=model if HAS_SKLEARN else None,
        algorithm=algorithm,
        model_type=model_type,
        X_train=np_X_train,
        X_eval=np.array(X_val),
        feature_names=feature_names,
        random_state=random_state
    )
    
    shap_values_bytes = list(pickle.dumps(shap_dict))
    x_train_bg_bytes = list(pickle.dumps(X_train_bg))
    estimator_bytes = list(pickle.dumps(model)) if HAS_SKLEARN else []

    # --- Scientific Diagnostics calculation ---
    diagnostics = None
    try:
        if model_type == "regression":
            from edeon_engine.diagnostics import regression_diagnostics
            diagnostics = regression_diagnostics(
                y_true=np.array(y_val),
                y_pred=np.array(val_preds),
                y_train=np.array(y_train),
                y_train_pred=np.array(train_preds),
                ad_status=test_ad["overall_status"] if test_ad else ["in"] * len(y_val),
                scramble_distribution=y_scramble_result if y_scramble_result and "error" not in y_scramble_result else None,
                estimator=model if HAS_SKLEARN else None,
                X_train=np.array(X_train),
                y_train_arr=np.array(y_train),
                cv_k=cv_folds,
                random_state=random_state
            )
        else:
            from edeon_engine.diagnostics import classification_diagnostics
            diagnostics = classification_diagnostics(
                y_true=np.array(y_val),
                y_pred=np.array(val_preds),
                y_proba=np.array(val_proba),
                cv_fold_predictions=cv_fold_predictions,
                estimator=model if HAS_SKLEARN else None,
                X_train=np.array(X_train),
                y_train_arr=np.array(y_train),
                cv_k=cv_folds,
                random_state=random_state
            )
    except Exception as diag_err:
        import sys
        sys.stderr.write(f"[WARNING] Failed to generate diagnostics: {str(diag_err)}\n")
        diagnostics = None

    # --- Activity Cliffs calculation ---
    cliffs = []
    try:
        from edeon_engine.cliffs import detect_cliffs, render_thumbnail
        if np is None:
            raise ImportError("numpy is required for activity cliffs detection")
        
        raw_cliffs = detect_cliffs(
            smiles=curated_smiles,
            y=np.array(y_valid),
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
        sys.stderr.write(f"[WARNING] Failed to generate activity cliffs: {str(cliff_err)}\n")
        cliffs = []

    return {
        "metrics": metrics,
        "importances": ui_importances,
        "plot_data": plot_data,
        "learning_curve": learning_curve,
        "cv_results": cv_results,
        "y_scramble": y_scramble_result,
        "total_compounds": n_samples,
        "validation_samples": len(val_idx),
        "curation_report": curation["report"],
        "provenance": provenance_data,
        "search_results": search_results,
        "params": final_params,
        "imbalance": imbalance_data,
        "ad_reference": ad_reference_bytes,
        "test_ad": test_ad,
        "shap_values": shap_values_bytes,
        "x_train_bg": x_train_bg_bytes,
        "estimator": estimator_bytes,
        "feature_names": feature_names,
        "diagnostics": diagnostics,
        "cliffs": cliffs,
        "curated_smiles": list(curated_smiles),
        "curated_activities": list(curated_activities)
    }

