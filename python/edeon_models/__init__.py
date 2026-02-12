# Edeon Models package
from typing import Optional
import numpy as np

from .backend import ModelBackend
from .endpoints import Endpoint, endpoint_metadata
from .types import (
    ADStatus,
    Tier,
    PredictionValue,
    Prediction,
    TrainingDataInfo,
    PerformanceMetrics,
    ADDefinition,
    ModelCard,
    ParityPoint,
    ParityPlotData,
    CalibrationPoint,
    CalibrationCurveData,
    HistogramBin,
    ResidualDistData,
    ROCPoint,
    ROCData,
    PRPoint,
    PRData,
    ReliabilityBin,
    ReliabilityData,
    ADHistogramData,
    CalibrationDiagnostics,
)
from .registry import BackendRegistry
from .ad import ADStrategy, TanimotoKNN_AD, ADWrapper
from .uq import UQStrategy, ConformalUQ, EnsembleVarianceUQ, UQWrapper
from .card import save_card, load_card, list_cards, delete_card, card_to_yaml, card_from_yaml
from .backends.studio import StudioBackend, deploy_studio_model, undeploy_studio_model
from .backends.external import OperaTier3Backend


def wrap_with_uq_and_ad(
    backend: ModelBackend,
    training_smiles: list[str],
    calibration_residuals: list[float] | np.ndarray
) -> ModelBackend:
    """Convenience function to wrap a backend with both UQ and AD in a one-line composition.

    Args:
        backend: The base ModelBackend point estimator to wrap.
        training_smiles: SMILES string representations of the model training set to calibrate the AD.
        calibration_residuals: List or array of residual values (|prediction - observation|) on a held-out calibration set.

    Returns:
        A composite ModelBackend that has both Applicability Domain (AD) scoring and Conformal Uncertainty Quantification (UQ).
    """
    # 1. Wrap with Tanimoto k-NN Applicability Domain
    ad_strategy = TanimotoKNN_AD(training_smiles=training_smiles)
    ad_wrapped = ADWrapper(backend, ad_strategy)

    # 2. Wrap with Conformal UQ
    uq_strategy = ConformalUQ(alpha=0.05)
    residuals = np.array(calibration_residuals)
    uq_strategy.calibrate(predictions=residuals, observations=np.zeros_like(residuals))
    composite_wrapped = UQWrapper(ad_wrapped, uq_strategy)

    return composite_wrapped

def build_default_registry(db_path: Optional[str] = None) -> BackendRegistry:
    """Constructs a BackendRegistry, registers all 12 Tier-2 legacy baseline backends,
    and registers available Tier-1 reference models if checkpoints exist.
    """
    from .registry import BackendRegistry
    from .backends.legacy import (
        BeeLD50_T2, FishLC50_T2, DaphniaEC50_T2,
        EarthwormLC50_T2, MallardLD50_T2, RatLD50_T2,
        SkinSensitization_T2, EyeIrritation_T2,
        SoilKoc_T2, SoilDT50_T2, GUSIndex_T2,
        Photostability_T2, BCF_T2,
    )
    from .card import save_card
    from .backends.trained import TrainedTier1Backend
    from pathlib import Path
    
    reg = BackendRegistry()
    
    # 1. Register Tier-2 baseline models
    for cls in [BeeLD50_T2, FishLC50_T2, DaphniaEC50_T2,
                EarthwormLC50_T2, MallardLD50_T2, RatLD50_T2,
                SkinSensitization_T2, EyeIrritation_T2,
                SoilKoc_T2, SoilDT50_T2, GUSIndex_T2,
                Photostability_T2, BCF_T2]:
        backend = cls()
        reg.register(backend)
        if db_path is not None:
            save_card(backend.metadata(), db_path=db_path)
        else:
            try:
                save_card(backend.metadata())
            except Exception:
                pass
                
    # 2. Register Tier-1 reference models if checkpoints are present
    checkpoint_root = Path("data/checkpoints")
    for endpoint in Endpoint:
        # Check for classification checkpoint first (v1.0_cls/)
        cls_dir = checkpoint_root / endpoint.value / "v1.0_cls"
        if cls_dir.exists() and (cls_dir / "model_card.yaml").exists():
            try:
                from edeon_models.backends.trained import TrainedClassificationTier1Backend
                backend = TrainedClassificationTier1Backend(endpoint, cls_dir)
                reg.register(backend)
                if db_path is not None:
                    save_card(backend.metadata(), db_path=db_path)
                else:
                    try:
                        save_card(backend.metadata())
                    except Exception:
                        pass
                # Classification takes priority, skip regression for this endpoint
                continue
            except Exception as e:
                import logging
                logging.getLogger("edeon_models").warning(
                    f"Failed to load T1 classification backend for {endpoint}: {e}"
                )
        
        # Fall back to regression checkpoint (v1.0/)
        ep_dir = checkpoint_root / endpoint.value / "v1.0"
        if ep_dir.exists() and (ep_dir / "model_card.yaml").exists():
            try:
                if endpoint == Endpoint.SOIL_DT50:
                    from edeon_models.backends.trained.heteroscedastic_backend import HeteroscedasticTier1Backend
                    backend = HeteroscedasticTier1Backend(endpoint, ep_dir)
                else:
                    backend = TrainedTier1Backend(endpoint, ep_dir)
                reg.register(backend)
                # Persist the Tier-1 model card
                if db_path is not None:
                    save_card(backend.metadata(), db_path=db_path)
                else:
                    try:
                        save_card(backend.metadata())
                    except Exception:
                        pass
            except Exception as e:
                import logging
                logging.getLogger("edeon_models").warning(f"Failed to load T1 backend for {endpoint}: {e}")
                
    # 3. Register GUS Composite Backend if both Soil Koc and Soil DT50 reference models are registered
    if Endpoint.SOIL_KOC in reg._backends and 1 in reg._backends[Endpoint.SOIL_KOC] and \
       Endpoint.SOIL_DT50 in reg._backends and 1 in reg._backends[Endpoint.SOIL_DT50]:
        koc_backend = reg._backends[Endpoint.SOIL_KOC][1]
        dt50_backend = reg._backends[Endpoint.SOIL_DT50][1]
        try:
            from edeon_models.backends.trained.gus_composite_backend import GUSCompositeBackend
            gus_backend = GUSCompositeBackend(koc_backend, dt50_backend)
            reg.register(gus_backend)
            # Persist the GUS Composite Model Card
            if db_path is not None:
                save_card(gus_backend.metadata(), db_path=db_path)
            else:
                try:
                    save_card(gus_backend.metadata())
                except Exception:
                    pass
        except Exception as e:
            import logging
            logging.getLogger("edeon_models").warning(f"Failed to load GUS composite backend: {e}")

    # 4. Register Tier-3 OPERA models for comparative analysis
    try:
        opera_endpoints = [
            Endpoint.SOIL_KOC,
            Endpoint.BCF,
            Endpoint.SOIL_DT50,
            Endpoint.RAT_ACUTE_ORAL_LD50,
            Endpoint.LOGP,
            Endpoint.PKA,
            Endpoint.SOLUBILITY,
            Endpoint.HENRYS_LAW,
        ]
        for ep in opera_endpoints:
            backend = OperaTier3Backend(ep)
            reg.register(backend)
            if db_path is not None:
                save_card(backend.metadata(), db_path=db_path)
            else:
                try:
                    save_card(backend.metadata())
                except Exception:
                    pass
    except Exception as e:
        import logging
        logging.getLogger("edeon_models").warning(f"Failed to load Tier-3 OPERA backends: {e}")
            
    return reg


__all__ = [
    "ModelBackend",
    "Endpoint",
    "endpoint_metadata",
    "ADStatus",
    "Tier",
    "PredictionValue",
    "Prediction",
    "TrainingDataInfo",
    "PerformanceMetrics",
    "ADDefinition",
    "ModelCard",
    "ParityPoint",
    "ParityPlotData",
    "CalibrationPoint",
    "CalibrationCurveData",
    "HistogramBin",
    "ResidualDistData",
    "ROCPoint",
    "ROCData",
    "PRPoint",
    "PRData",
    "ReliabilityBin",
    "ReliabilityData",
    "ADHistogramData",
    "CalibrationDiagnostics",
    "BackendRegistry",
    "ADStrategy",
    "TanimotoKNN_AD",
    "ADWrapper",
    "UQStrategy",
    "ConformalUQ",
    "EnsembleVarianceUQ",
    "UQWrapper",
    "wrap_with_uq_and_ad",
    "save_card",
    "load_card",
    "list_cards",
    "delete_card",
    "card_to_yaml",
    "card_from_yaml",
    "build_default_registry",
    "StudioBackend",
    "deploy_studio_model",
    "undeploy_studio_model",
    "OperaTier3Backend",
]
