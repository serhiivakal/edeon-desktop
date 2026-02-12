from __future__ import annotations
try:
    from enum import StrEnum
except ImportError:
    from enum import Enum
    class StrEnum(str, Enum):
        pass
from enum import IntEnum
from typing import Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class ADStatus(StrEnum):
    IN = "in"
    BORDERLINE = "borderline"
    OUT = "out"
    UNKNOWN = "unknown"

class Tier(IntEnum):
    REFERENCE = 1  # Edeon-trained, validated, UQ-calibrated
    BASELINE = 2   # Simple LogP-based fallback
    EXTERNAL = 3   # External API (EPA T.E.S.T., OPERA, etc.)
    USER = 4       # User-deployed from QSAR Studio

class PredictionValue(BaseModel):
    """Discriminated union of possible prediction value types."""
    model_config = ConfigDict(frozen=True)
    kind: str  # "numeric" | "categorical" | "binary"
    numeric: Optional[float] = None
    categorical: Optional[str] = None
    binary: Optional[bool] = None

class Prediction(BaseModel):
    model_config = ConfigDict(frozen=True)
    smiles: str
    endpoint: str
    value: PredictionValue
    ci_lower: Optional[float] = None
    ci_upper: Optional[float] = None
    ci_level: float = 0.95
    ad_status: ADStatus
    ad_score: Optional[float] = None  # e.g., Tanimoto distance to nearest neighbour
    units: str
    model_id: str
    model_version: str
    tier: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    provenance: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)

class TrainingDataInfo(BaseModel):
    n_compounds: int
    sources: list[str]
    sha256: Optional[str] = None
    split_strategy: Optional[str] = None  # "scaffold" | "random" | "time"
    license: Optional[str] = None

class PerformanceMetrics(BaseModel):
    metrics: dict[str, float]  # e.g., {"rmse": 0.65, "r2": 0.72}
    test_set_n: Optional[int] = None
    cv_folds: Optional[int] = None
    calibration_coverage_95: Optional[float] = None
    subset_metrics: Optional[dict[str, Any]] = None

class ADDefinition(BaseModel):
    method: str  # "tanimoto_knn" | "leverage" | "ensemble_variance" | "none"
    threshold: Optional[float] = None
    k: Optional[int] = None
    training_set_size: Optional[int] = None
    notes: Optional[str] = None

class ModelCard(BaseModel):
    model_id: str
    name: str
    version: str
    tier: int
    endpoint: str
    description: str
    intended_use: str
    not_intended_for: list[str] = Field(default_factory=list)
    training_data: Optional[TrainingDataInfo] = None
    performance: Optional[PerformanceMetrics] = None
    applicability_domain: Optional[ADDefinition] = None
    uncertainty_method: Optional[str] = None
    known_failure_modes: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    license: str = "Proprietary"
    created: datetime = Field(default_factory=datetime.utcnow)
    authors: list[str] = Field(default_factory=list)

class ParityPoint(BaseModel):
    observed: float
    predicted: float
    smiles: str
    ad_status: str
    ci_lower: Optional[float] = None
    ci_upper: Optional[float] = None

class ParityPlotData(BaseModel):
    points: list[ParityPoint]

class CalibrationPoint(BaseModel):
    expected: float
    actual: float

class CalibrationCurveData(BaseModel):
    points: list[CalibrationPoint]

class HistogramBin(BaseModel):
    bin_start: float
    bin_end: float
    bin_center: float
    count: int

class ResidualDistData(BaseModel):
    bins: list[HistogramBin]
    mean: float
    std: float

class ROCPoint(BaseModel):
    fpr: float
    tpr: float

class ROCData(BaseModel):
    points: list[ROCPoint]
    auc: float

class PRPoint(BaseModel):
    precision: float
    recall: float

class PRData(BaseModel):
    points: list[PRPoint]
    auc: float

class ReliabilityBin(BaseModel):
    bin_start: float
    bin_end: float
    count: int
    avg_predicted: float
    avg_actual: float

class ReliabilityData(BaseModel):
    bins: list[ReliabilityBin]

class ADHistogramData(BaseModel):
    train_distances: list[float]
    test_distances: list[float]
    in_threshold: float
    out_threshold: float

class CalibrationDiagnostics(BaseModel):
    endpoint: str
    model_id: str
    test_set_size: int
    task_kind: str  # "regression" | "classification"
    
    # Regression specific
    parity_data: Optional[ParityPlotData] = None
    calibration_curve: Optional[CalibrationCurveData] = None
    residual_distribution: Optional[ResidualDistData] = None
    
    # Classification specific
    roc_curve: Optional[ROCData] = None
    pr_curve: Optional[PRData] = None
    reliability_diagram: Optional[ReliabilityData] = None
    confusion_matrix: Optional[list[list[int]]] = None
    
    # All models
    ad_distance_histogram: ADHistogramData
    per_chemical_class_metrics: dict[str, dict[str, float]]

__all__ = [
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
]
