import os
import pickle
import json
import sqlite3
import numpy as np
from typing import Optional, Any
from datetime import datetime

from edeon_models.backend import ModelBackend
from edeon_models.types import (
    Prediction,
    PredictionValue,
    ADStatus,
    ModelCard,
    ADDefinition,
    PerformanceMetrics,
    TrainingDataInfo
)
from edeon_models.endpoints import Endpoint, endpoint_metadata
from edeon_models.uq.conformal import ConformalUQ

# Import from edeon_engine for featurization and applicability domain scoring
from edeon_engine.models.featurizers import run_featurizers, _legacy_features_to_selections
from edeon_engine.applicability import score_query


class StudioBackend(ModelBackend):
    """Wraps a custom model trained in QSAR Studio for use as a T4 backend."""

    def __init__(self, saved_model_id: str, db_path: str, deploy_target: Endpoint):
        self._saved_model_id = saved_model_id
        self._db_path = db_path
        self._deploy_target = Endpoint(deploy_target)
        self._units = endpoint_metadata(self._deploy_target).get("units", "unknown")

        # 1. Load model metadata and artifacts from SQLite database
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT name, type, algorithm, features, metrics, importances, "
            "provenance, curation_report, cv_results, y_scramble, search_results, "
            "created_at, ad_reference, diagnostics, cliffs FROM saved_models WHERE id = ?",
            (saved_model_id,)
        )
        row = cur.fetchone()
        conn.close()

        if not row:
            raise ValueError(f"Saved model '{saved_model_id}' not found in database.")

        (
            self._name,
            self._model_type,
            self._algorithm,
            features_json,
            metrics_json,
            importances_json,
            provenance_json,
            curation_report_json,
            cv_results_json,
            y_scramble_json,
            search_results_json,
            self._created_at,
            ad_ref_blob,
            diagnostics_json,
            cliffs_json
        ) = row

        # Parse JSON structures
        self._metrics = json.loads(metrics_json) if metrics_json else {}
        self._provenance = json.loads(provenance_json) if provenance_json else {}
        self._curation_report = json.loads(curation_report_json) if curation_report_json else {}
        self._diagnostics = json.loads(diagnostics_json) if diagnostics_json else {}
        self._cliffs = json.loads(cliffs_json) if cliffs_json else []

        # Resolve featurizer selections
        self._selections = self._provenance.get("config", {}).get("featurizer_selections")
        if not self._selections and features_json:
            try:
                features_list = json.loads(features_json)
                if isinstance(features_list, list):
                    self._selections = _legacy_features_to_selections(features_list)
            except Exception:
                pass
        if not self._selections:
            # Fallback to Lipinski descriptors preset
            from edeon_engine.models.featurizers.descriptors_2d import LIPINSKI
            self._selections = [{"id": "descriptors_2d", "params": {"selected": list(LIPINSKI)}}]

        # 2. Load the pickled scikit-learn model from storage
        models_dir = os.path.join(os.path.dirname(db_path), "models")
        estimator_path = os.path.join(models_dir, f"{saved_model_id}.pkl")
        if not os.path.exists(estimator_path):
            raise FileNotFoundError(f"Model estimator pickle file not found at {estimator_path}")

        with open(estimator_path, "rb") as f:
            self._estimator = pickle.load(f)

        # 3. Load the pre-built applicability domain reference if available
        self._ad_reference = None
        if ad_ref_blob:
            try:
                self._ad_reference = pickle.loads(ad_ref_blob)
            except Exception:
                pass

        # 4. Load calibration residuals and calibrate the UQ strategy
        self._uq = None
        if self._model_type == "regression":
            residuals = []
            res_fitted = self._diagnostics.get("residuals_vs_fitted", [])
            if res_fitted:
                residuals = [abs(item["residual"]) for item in res_fitted if "residual" in item]

            if not residuals:
                # Fallback default residuals for calibration
                residuals = [0.1] * 10

            uq = ConformalUQ(alpha=0.05)
            residuals_arr = np.array(residuals)
            uq.calibrate(predictions=residuals_arr, observations=np.zeros_like(residuals_arr))
            self._uq = uq
        else:
            # Classification: Load calibration probabilities and labels for Venn-Abers
            cal_data = self._diagnostics.get("calibration_data", {})
            if cal_data:
                y_true = cal_data.get("y_true", [])
                y_proba = cal_data.get("y_proba", [])
                if y_true and y_proba:
                    from edeon_engine.uq import VennAbersCalibrator
                    uq = VennAbersCalibrator()
                    uq.fit(y_proba, y_true)
                    self._uq = uq

    def endpoint(self) -> Endpoint:
        return self._deploy_target

    def tier(self) -> int:
        return 4

    def version(self) -> str:
        return f"studio-{self._saved_model_id}"

    def predict(self, smiles: list[str], conditions: Optional[dict] = None) -> list[Prediction]:
        from rdkit import Chem
        out = []
        for s in smiles:
            try:
                # Validate SMILES structure first
                mol = Chem.MolFromSmiles(s)
                if mol is None:
                    raise ValueError("Invalid SMILES structure.")

                # Featurize
                X, _ = run_featurizers([s], self._selections)
                if X.shape[1] == 0:
                    raise ValueError("Featurization produced empty feature vector.")

                if np.isnan(X).any():
                    X = np.nan_to_num(X, nan=0.0)

                # Predict point value or probability
                pred_val = self._estimator.predict(X)[0]

                ci_lower = None
                ci_upper = None
                ci_level = 0.95

                if self._model_type == "regression":
                    # Apply UQ wrapper (Conformal Interval) if regression
                    if self._uq is not None:
                        ci_level = getattr(self._uq, "alpha", 0.05)
                        ci_lower, ci_upper = self._uq.interval(float(pred_val), s)
                    val_obj = PredictionValue(kind="numeric", numeric=float(pred_val))
                else:
                    # Classification probability calibration
                    if hasattr(self._estimator, "predict_proba"):
                        proba_arr = self._estimator.predict_proba(X)
                        if proba_arr.shape[1] > 1:
                            raw_prob = float(proba_arr[0, 1])
                        else:
                            raw_prob = float(proba_arr[0, 0])
                    elif hasattr(self._estimator, "decision_function"):
                        df_val = float(self._estimator.decision_function(X)[0])
                        raw_prob = float(1.0 / (1.0 + np.exp(-df_val)))
                    else:
                        try:
                            raw_prob = float(pred_val)
                        except Exception:
                            raw_prob = 0.5

                    calibrated_prob = raw_prob
                    if self._uq is not None:
                        # self._uq is VennAbersCalibrator
                        probs, bounds = self._uq.predict_calibrated([raw_prob])
                        calibrated_prob = probs[0]
                        ci_lower, ci_upper = bounds[0]
                        ci_level = 0.95

                    final_class = 1 if calibrated_prob >= 0.5 else 0
                    val_obj = PredictionValue(kind="categorical", categorical=str(final_class))

                # Apply AD check
                ad_status = ADStatus.UNKNOWN
                ad_score = None
                if self._ad_reference is not None:
                    res = score_query(self._ad_reference, [s], X)
                    stat_str = res.get("overall_status", ["invalid"])[0]
                    if stat_str == "in":
                        ad_status = ADStatus.IN
                    elif stat_str == "borderline":
                        ad_status = ADStatus.BORDERLINE
                    elif stat_str == "out":
                        ad_status = ADStatus.OUT

                    # Extract Tanimoto distance
                    t_scores = res.get("tanimoto", {})
                    mean_knn_dists = t_scores.get("mean_knn_distance", [None])
                    if mean_knn_dists and mean_knn_dists[0] is not None:
                        ad_score = float(mean_knn_dists[0])

                out.append(Prediction(
                    smiles=s,
                    endpoint=self._deploy_target.value,
                    value=val_obj,
                    ci_lower=ci_lower,
                    ci_upper=ci_upper,
                    ci_level=ci_level,
                    ad_status=ad_status,
                    ad_score=ad_score,
                    units=self._units,
                    model_id=self.model_id(),
                    model_version=self.version(),
                    tier=4,
                    warnings=[]
                ))
            except Exception as e:
                # Handle per-compound failure gracefully
                if self._model_type == "regression":
                    val_obj = PredictionValue(kind="numeric", numeric=float("nan"))
                else:
                    val_obj = PredictionValue(kind="categorical", categorical="Prediction Failed")

                out.append(Prediction(
                    smiles=s,
                    endpoint=self._deploy_target.value,
                    value=val_obj,
                    ad_status=ADStatus.UNKNOWN,
                    units=self._units,
                    model_id=self.model_id(),
                    model_version=self.version(),
                    tier=4,
                    warnings=[f"Prediction failed: {str(e)}"]
                ))
        return out


    def applicability_domain(self, smiles: list[str]) -> list[ADStatus]:
        if not self._ad_reference:
            return [ADStatus.UNKNOWN] * len(smiles)
        try:
            X, _ = run_featurizers(smiles, self._selections)
            res = score_query(self._ad_reference, smiles, X)
            statuses = []
            for status in res.get("overall_status", []):
                if status == "in":
                    statuses.append(ADStatus.IN)
                elif status == "borderline":
                    statuses.append(ADStatus.BORDERLINE)
                elif status == "out":
                    statuses.append(ADStatus.OUT)
                else:
                    statuses.append(ADStatus.UNKNOWN)
            return statuses
        except Exception:
            return [ADStatus.UNKNOWN] * len(smiles)

    def metadata(self) -> ModelCard:
        # Construct Description listing featurizer configurations
        feat_desc = ", ".join([sel.get("id", "unknown") for sel in self._selections])
        description = (
            f"Custom Model '{self._name}' ({self._algorithm}) trained in QSAR Studio "
            f"and deployed as a Tier-4 model backend. Features: [{feat_desc}]."
        )

        # Build TrainingDataInfo
        n_compounds = self._provenance.get("n_compounds_input", 0)
        sources = ["QSAR Studio Training Dataset"]
        sha256 = self._provenance.get("dataset_hash")
        split_strategy = self._provenance.get("split_mode")

        training_data = TrainingDataInfo(
            n_compounds=n_compounds,
            sources=sources,
            sha256=sha256,
            split_strategy=split_strategy
        )

        # Build PerformanceMetrics
        cv_folds = self._provenance.get("cv_k")
        performance = PerformanceMetrics(
            metrics=self._metrics,
            cv_folds=cv_folds
        )

        # Build ADDefinition
        ad_def = None
        if self._ad_reference and hasattr(self._ad_reference, "tanimoto"):
            t_ref = self._ad_reference.tanimoto
            ad_def = ADDefinition(
                method="tanimoto_knn",
                threshold=t_ref.threshold,
                k=t_ref.k,
                training_set_size=len(t_ref.fingerprints)
            )

        # Build ModelCard
        return ModelCard(
            model_id=self.model_id(),
            name=self._name,
            version=self.version(),
            tier=4,
            endpoint=self._deploy_target.value,
            description=description,
            intended_use="Custom predictive screening within the Edeon platform.",
            training_data=training_data,
            performance=performance,
            applicability_domain=ad_def,
            uncertainty_method="ConformalUQ" if self._uq is not None else None,
            references=[],
            license="Proprietary",
            authors=["QSAR Studio User"]
        )
