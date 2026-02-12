"""Composite Tier-1 reference model backend for Gustafson Leaching Index (GUS).

Wraps Soil Koc and Soil DT50 reference backends and propagates joint uncertainty
via a 10,000-sample Monte Carlo simulation.
"""

import logging
import numpy as np
from typing import List, Optional, Tuple, Any

from edeon_models.backend import ModelBackend
from edeon_models.types import Prediction, PredictionValue, ADStatus, ModelCard, TrainingDataInfo, PerformanceMetrics, ADDefinition
from edeon_models.endpoints import Endpoint, endpoint_metadata
from edeon_engine.standardize import standardize_batch

logger = logging.getLogger("edeon_models.gus_composite_backend")

class GUSCompositeBackend(ModelBackend):
    """Composite Tier-1 reference backend propagating Koc and DT50 uncertainty to GUS."""
    
    _ENDPOINT = Endpoint.GUS_INDEX
    _VERSION = "v1.0"
    _UNITS = "unitless"
    
    def __init__(self, koc_backend: ModelBackend, dt50_backend: ModelBackend):
        self._koc_backend = koc_backend
        self._dt50_backend = dt50_backend
        self._load()

    def _load(self) -> None:
        """Constructs ModelCard metadata for the composite backend."""
        logger.info("Initializing GUS Composite Tier-1 reference backend...")
        
        # Build ModelCard dynamically
        self._card = ModelCard(
            model_id="t1_gus_index_v1.0_composite",
            name="Edeon Tier-1 Reference GUS Leaching Index (Composite)",
            version=self._VERSION,
            tier=1,
            endpoint=self._ENDPOINT.value,
            description=(
                "Tier-1 composite index predicting Gustafson Leaching Index (GUS) "
                "by propagating joint uncertainty from Soil Koc and Soil DT50 reference QSAR models "
                "using 10,000-sample Monte Carlo simulation."
            ),
            intended_use="Tier-1 hazard classification of agrochemical leaching risk to groundwater.",
            training_data=TrainingDataInfo(
                n_compounds=0,
                sources=[
                    f"Composite: Soil Koc ({self._koc_backend.model_id()}) and "
                    f"Soil DT50 ({self._dt50_backend.model_id()})"
                ],
                split_strategy="scaffold"
            ),
            performance=PerformanceMetrics(
                metrics={},
                notes="Performance is determined by Koc and DT50 component models. Uncertainty propagated via Monte Carlo."
            ),
            applicability_domain=ADDefinition(
                method="component_minimum",
                notes="Applicability domain is computed as the minimum (worst) of Soil Koc and Soil DT50 domains."
            ),
            uncertainty_method="monte_carlo_propagation",
            known_failure_modes=[
                "Assumes conditional independence of Soil Koc and Soil DT50 errors in log space.",
                "Compounds outside the applicability domain of either Koc or DT50 component models."
            ],
            references=[
                "Gustafson, D. I. (1989). Groundwater ubiquity score: a simple method for assessing pesticide leachability.",
                "Edeon Phase 3 Soil Koc and Soil DT50 reference models."
            ],
            authors=["Edeon AI Team"]
        )
        
        logger.info(f"Successfully loaded GUS Composite Tier-1 backend: {self.model_id()}")

    def endpoint(self) -> Endpoint:
        return self._ENDPOINT

    def tier(self) -> int:
        return 1

    def version(self) -> str:
        return self._VERSION

    def applicability_domain(self, smiles: List[str]) -> List[ADStatus]:
        """Returns combined applicability domain status as the minimum of components."""
        if not smiles:
            return []
            
        koc_ads = self._koc_backend.applicability_domain(smiles)
        dt50_ads = self._dt50_backend.applicability_domain(smiles)
        
        status_order = {
            ADStatus.UNKNOWN: 0,
            ADStatus.OUT: 1,
            ADStatus.BORDERLINE: 2,
            ADStatus.IN: 3
        }
        inv_status_order = {v: k for k, v in status_order.items()}
        
        combined_ads = []
        for k_ad, d_ad in zip(koc_ads, dt50_ads):
            min_val = min(status_order.get(k_ad, 0), status_order.get(d_ad, 0))
            combined_ads.append(inv_status_order[min_val])
            
        return combined_ads

    def predict(self, smiles: List[str], conditions: Optional[dict] = None) -> List[Prediction]:
        """Queries Koc and DT50 backends, and propagates joint uncertainty to GUS index."""
        if not smiles:
            return []
            
        n_compounds = len(smiles)
        predictions = []
        
        # 1. SMILES Standardization
        std_results = standardize_batch(smiles)
        clean_smiles = []
        valid_indices = []
        invalid_indices = []
        
        for idx, r in enumerate(std_results):
            if r["valid"] and r["canonical"] is not None:
                clean_smiles.append(r["canonical"])
                valid_indices.append(idx)
            else:
                clean_smiles.append("")
                invalid_indices.append(idx)
                
        # 2. Query component backends
        koc_preds = self._koc_backend.predict(smiles, conditions)
        dt50_preds = self._dt50_backend.predict(smiles, conditions)
        
        status_order = {
            ADStatus.UNKNOWN: 0,
            ADStatus.OUT: 1,
            ADStatus.BORDERLINE: 2,
            ADStatus.IN: 3
        }
        inv_status_order = {v: k for k, v in status_order.items()}
        
        for idx in range(n_compounds):
            smi_orig = smiles[idx]
            
            if idx in invalid_indices:
                predictions.append(Prediction(
                    smiles=smi_orig,
                    endpoint=self._ENDPOINT.value,
                    value=PredictionValue(kind="numeric", numeric=None),
                    ci_lower=None,
                    ci_upper=None,
                    ad_status=ADStatus.UNKNOWN,
                    ad_score=None,
                    units=self._UNITS,
                    model_id=self.model_id(),
                    model_version=self.version(),
                    tier=1,
                    warnings=["parse_failed"]
                ))
                continue
                
            pred_koc = koc_preds[idx]
            pred_dt50 = dt50_preds[idx]
            
            # Check if either component prediction failed
            if pred_koc.value.numeric is None or pred_dt50.value.numeric is None:
                predictions.append(Prediction(
                    smiles=clean_smiles[idx],
                    endpoint=self._ENDPOINT.value,
                    value=PredictionValue(kind="numeric", numeric=None),
                    ci_lower=None,
                    ci_upper=None,
                    ad_status=ADStatus.UNKNOWN,
                    ad_score=None,
                    units=self._UNITS,
                    model_id=self.model_id(),
                    model_version=self.version(),
                    tier=1,
                    warnings=list(set(pred_koc.warnings + pred_dt50.warnings + ["component_prediction_failed"]))
                ))
                continue
                
            # 3. Retrieve log-space mean and standard deviations
            mu_koc = float(pred_koc.provenance["prediction_log"])
            sigma_koc = float(pred_koc.provenance["ci_upper_log"] - mu_koc) / 1.9599639845400542
            sigma_koc = max(1e-6, sigma_koc)
            
            mu_dt50 = float(pred_dt50.provenance["prediction_log"])
            sigma_dt50 = float(pred_dt50.provenance["ci_upper_log"] - mu_dt50) / 1.9599639845400542
            sigma_dt50 = max(1e-6, sigma_dt50)
            
            # 4. Monte Carlo propagation (10,000 samples)
            np.random.seed(42 + idx)  # Local seed based on compound index for reproducibility
            koc_samples = np.random.normal(mu_koc, sigma_koc, 10000)
            dt50_samples = np.random.normal(mu_dt50, sigma_dt50, 10000)
            
            # GUS Index = log10(DT50) * (4 - log10(Koc))
            # Traditional Gustafson sets GUS to 0.0 if log10(Koc) >= 4.0
            gus_samples = np.where(koc_samples < 4.0, dt50_samples * (4.0 - koc_samples), 0.0)
            
            median_gus = float(np.median(gus_samples))
            ci_lower = float(np.percentile(gus_samples, 2.5))
            ci_upper = float(np.percentile(gus_samples, 97.5))
            
            # Compute leaching class probabilities
            prob_non_leacher = float(np.mean(gus_samples < 1.8))
            prob_transition = float(np.mean((gus_samples >= 1.8) & (gus_samples <= 2.8)))
            prob_leacher = float(np.mean(gus_samples > 2.8))
            
            # Determine minimum AD status
            koc_ad_val = status_order.get(pred_koc.ad_status, 0)
            dt50_ad_val = status_order.get(pred_dt50.ad_status, 0)
            min_ad_val = min(koc_ad_val, dt50_ad_val)
            combined_ad_status = inv_status_order[min_ad_val]
            
            # Set combined AD score (e.g. mean or max Tanimoto distance, let's use max distance for safety)
            combined_ad_score = max(pred_koc.ad_score or 0.0, pred_dt50.ad_score or 0.0)
            
            # Build detailed provenance dictionary
            provenance = {
                "model_id": self.model_id(),
                "model_version": self.version(),
                "koc_model_id": pred_koc.model_id,
                "dt50_model_id": pred_dt50.model_id,
                "koc_prediction_log": mu_koc,
                "koc_sigma_log": sigma_koc,
                "dt50_prediction_log": mu_dt50,
                "dt50_sigma_log": sigma_dt50,
                "gus_median": median_gus,
                "gus_mean": float(np.mean(gus_samples)),
                "gus_std": float(np.std(gus_samples)),
                "leaching_probabilities": {
                    "non_leacher": prob_non_leacher,
                    "transition": prob_transition,
                    "leacher": prob_leacher
                },
                "koc_provenance": pred_koc.provenance,
                "dt50_provenance": pred_dt50.provenance
            }
            
            predictions.append(Prediction(
                smiles=clean_smiles[idx],
                endpoint=self._ENDPOINT.value,
                value=PredictionValue(kind="numeric", numeric=median_gus),
                ci_lower=ci_lower,
                ci_upper=ci_upper,
                ci_level=0.95,
                ad_status=combined_ad_status,
                ad_score=combined_ad_score,
                units=self._UNITS,
                model_id=self.model_id(),
                model_version=self.version(),
                tier=1,
                provenance=provenance,
                warnings=list(set(pred_koc.warnings + pred_dt50.warnings))
            ))
            
        return predictions

    def metadata(self) -> ModelCard:
        return self._card
