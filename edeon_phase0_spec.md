# Edeon Phase 0 — Implementation Specification

**Audience:** coding agent.
**Goal:** unify all predictor backends in Edeon behind a single `ModelBackend` interface, with mandatory uncertainty quantification (UQ), applicability domain (AD) reporting, model cards, a deployment bridge from the QSAR Studio, and a continuous validation harness. After Phase 0 the existing LogP-based predictors continue to function but are repackaged as Tier-2 backends behind the new interface, with visible "screening estimate" labelling in the UI.

This spec is intentionally exhaustive. Execute tasks in dependency order. Do not invent additional features. Do not refactor unrelated code. When in doubt, prefer adding new modules over modifying existing ones.

---

## 0. Context

Edeon is a Tauri desktop application for agrochemical lead optimisation. It contains:

- A Rust core (`src-tauri/`) that owns the UI bridge and orchestration.
- A Python predictor process invoked via IPC, using RDKit for chemistry.
- A React frontend (`src/`).
- SQLite for persistence.
- A QSAR Studio (Models tab) that already trains scikit-learn models with scaffold splits, k-fold CV, Y-scrambling, multiple fingerprints, and Optuna HPO — but saved models are currently dead weights, unused by downstream predictors.

Predictor modules currently bake in LogP-based heuristics:
- Beneficial Organism Honeycomb (bee, fish, Daphnia, earthworm, mallard)
- Toxicity panel (rat LD50, skin sensitization, eye irritation, mammalian concern)
- Environmental Fate (Koc, DT50, GUS)
- UV photostability
- Pesticide-likeness (Tice rules — this is rule-based, keep as-is)
- Selectivity (placeholder — to be replaced in later phases)

Phase 0 does not improve the science of any predictor. It builds the architecture that allows later phases to swap in better models without touching the UI or the pipeline.

---

## 1. Tech Stack Assumptions

- **Rust**: edition 2021, Tokio for async, Serde for serialization, Tauri 1.x or 2.x (use whatever is already in `Cargo.toml`).
- **Python**: 3.10+, RDKit (rdkit-pypi), scikit-learn, numpy, pandas, pydantic v2 for data classes, typing-extensions.
- **Frontend**: React + TypeScript, shadcn/ui or whatever component library is already in use.
- **Persistence**: SQLite via existing connection in `src-tauri/`.
- **IPC**: existing Python subprocess mechanism. Extend rather than replace.

If any assumption is wrong, follow the existing project conventions and document the deviation in `docs/PHASE0_NOTES.md`.

---

## 2. Architectural Overview

```
┌─────────────────────────────────────────────────────────────┐
│  React Frontend                                              │
│  - ModelTierBadge, ADWarning, PredictionDisplay, ModelCardViewer │
└─────────────────────────────────────────────────────────────┘
                    ↕ (Tauri IPC commands)
┌─────────────────────────────────────────────────────────────┐
│  Rust Core (src-tauri/)                                      │
│  - BackendProxy (calls Python via subprocess IPC)            │
│  - ModelCard cache                                           │
│  - Tier preference store                                     │
└─────────────────────────────────────────────────────────────┘
                    ↕ (JSON over stdio)
┌─────────────────────────────────────────────────────────────┐
│  Python Predictor Process (python/edeon_models/)             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  BackendRegistry                                       │ │
│  │  endpoint → [T1?, T2, T3?, T4?]                        │ │
│  └────────────────────────────────────────────────────────┘ │
│                       │                                       │
│  ┌────────────────────┴───────────────────────────────────┐ │
│  │  ModelBackend (ABC)                                     │ │
│  │  - predict(smiles) → list[Prediction]                  │ │
│  │  - applicability_domain(smiles) → list[ADStatus]       │ │
│  │  - metadata() → ModelCard                              │ │
│  └────────────────────────────────────────────────────────┘ │
│                       △                                       │
│         ┌─────────────┼─────────────┐                        │
│  ┌──────┴──────┐ ┌────┴─────┐ ┌────┴─────┐                  │
│  │ T2 Legacy   │ │ T1 Train │ │ T4 User  │                  │
│  │ (LogP)      │ │ (Future) │ │ (Studio) │                  │
│  └─────────────┘ └──────────┘ └──────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

**Key invariants:**

1. Every prediction returns the same shape: value + CI + AD status + tier + provenance.
2. The registry is the only thing that knows which backend serves which endpoint at runtime.
3. The frontend never directly knows which backend ran; it displays `tier` + `ad_status` + `ci` from the response.
4. T2 backends always exist as fallback. T1 (trained reference), T3 (external API), T4 (user-deployed) are optional layers above.

---

## 3. Repository Layout

Create the following new directories and files. Preserve existing project structure.

```
edeon/
├── src-tauri/
│   └── src/
│       └── models/                  # NEW
│           ├── mod.rs
│           ├── types.rs             # Mirror of Python data structures
│           ├── proxy.rs             # Calls Python BackendRegistry
│           ├── card_cache.rs        # In-memory ModelCard cache
│           └── preferences.rs       # User tier preferences
├── python/
│   └── edeon_models/                # NEW
│       ├── __init__.py
│       ├── backend.py               # ModelBackend ABC
│       ├── types.py                 # Prediction, ADStatus, etc.
│       ├── endpoints.py             # Canonical endpoint enum
│       ├── card.py                  # ModelCard dataclass + IO
│       ├── registry.py              # BackendRegistry
│       ├── ad/
│       │   ├── __init__.py
│       │   ├── base.py              # ADStrategy ABC
│       │   ├── tanimoto_knn.py      # Default AD strategy
│       │   └── wrapper.py           # ADWrapper
│       ├── uq/
│       │   ├── __init__.py
│       │   ├── base.py              # UQStrategy ABC
│       │   ├── conformal.py         # Conformal prediction
│       │   ├── ensemble.py          # Ensemble variance
│       │   └── wrapper.py           # UQWrapper
│       ├── backends/
│       │   ├── __init__.py
│       │   ├── legacy/              # T2 wrappers around existing LogP predictors
│       │   │   ├── __init__.py
│       │   │   ├── bee_ld50.py
│       │   │   ├── fish_lc50.py
│       │   │   ├── daphnia_ec50.py
│       │   │   ├── earthworm_lc50.py
│       │   │   ├── mallard_ld50.py
│       │   │   ├── rat_ld50.py
│       │   │   ├── skin_sensitization.py
│       │   │   ├── eye_irritation.py
│       │   │   ├── soil_koc.py
│       │   │   ├── soil_dt50.py
│       │   │   ├── gus_index.py
│       │   │   └── photostability.py
│       │   └── studio/              # T4 wrapper for Studio-deployed models
│       │       ├── __init__.py
│       │       └── studio_backend.py
│       ├── validation/
│       │   ├── __init__.py
│       │   ├── harness.py           # Regression test runner
│       │   └── fixtures.py          # Fixture loading
│       └── ipc/
│           ├── __init__.py
│           ├── server.py            # JSON-over-stdio server
│           └── commands.py          # Command dispatch
├── src/
│   └── components/
│       └── models/                  # NEW
│           ├── ModelTierBadge.tsx
│           ├── ADWarning.tsx
│           ├── PredictionDisplay.tsx
│           ├── ModelCardViewer.tsx
│           └── TierPreferenceSelector.tsx
├── tests/
│   └── regression/                  # NEW
│       ├── fixtures/
│       │   ├── bee_ld50_v1.csv
│       │   ├── fish_lc50_v1.csv
│       │   └── ...
│       ├── tolerance.yaml
│       ├── conftest.py
│       └── test_regression.py
├── docs/
│   ├── PHASE0_NOTES.md              # NEW — agent's deviation log
│   └── MODEL_CARD_SCHEMA.md         # NEW
└── .github/
    └── workflows/
        └── regression.yml           # NEW — CI for validation harness
```

---

## 4. Canonical Endpoint Identifiers

These are fixed string identifiers. Use them verbatim. They are the contract between backends and the registry.

| Identifier | Description | Units | Direction |
|---|---|---|---|
| `bee_acute_oral_ld50` | Honeybee acute oral LD50 | µg/bee | Lower = more toxic |
| `bee_acute_contact_ld50` | Honeybee acute contact LD50 | µg/bee | Lower = more toxic |
| `fish_acute_lc50` | Fish acute LC50 (multispecies, default rainbow trout) | mg/L | Lower = more toxic |
| `daphnia_acute_ec50` | Daphnia magna 48h acute EC50 | mg/L | Lower = more toxic |
| `algae_growth_ec50` | Algae 72h growth EC50 (Raphidocelis) | mg/L | Lower = more toxic |
| `earthworm_acute_lc50` | Earthworm 14d LC50 (E. fetida) | mg/kg soil | Lower = more toxic |
| `bird_acute_oral_ld50` | Bird acute oral LD50 (default bobwhite quail) | mg/kg bw | Lower = more toxic |
| `rat_acute_oral_ld50` | Rat acute oral LD50 | mg/kg bw | Lower = more toxic |
| `skin_sensitization` | Skin sensitization (binary or 4-class GHS) | category | Higher = more concern |
| `eye_irritation` | Eye irritation (3-class GHS) | category | Higher = more concern |
| `soil_koc` | Soil organic carbon partition coefficient | L/kg | Higher = more sorbed |
| `soil_dt50` | Soil degradation half-life | days | Higher = more persistent |
| `gus_index` | Gustafson groundwater ubiquity score | unitless | Higher = more leaching risk |
| `bcf` | Bioconcentration factor | L/kg | Higher = more bioaccumulative |
| `photostability_class` | Qualitative photostability category | category | — |
| `pesticide_likeness_tice` | Tice rule violations count | integer | Lower = more pesticide-like |

Implement as a Python `StrEnum` in `python/edeon_models/endpoints.py` and a matching Rust enum in `src-tauri/src/models/types.rs`.

---

## 5. Core Data Structures

### 5.1 Python (`python/edeon_models/types.py`)

```python
from __future__ import annotations
from enum import StrEnum
from typing import Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class ADStatus(StrEnum):
    IN = "in"
    BORDERLINE = "borderline"
    OUT = "out"
    UNKNOWN = "unknown"


class Tier(int, StrEnum):
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
```

### 5.2 Rust (`src-tauri/src/models/types.rs`)

```rust
use serde::{Deserialize, Serialize};
use chrono::{DateTime, Utc};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum AdStatus {
    In,
    Borderline,
    Out,
    Unknown,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "lowercase")]
pub enum PredictionValue {
    Numeric { numeric: f64 },
    Categorical { categorical: String },
    Binary { binary: bool },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Prediction {
    pub smiles: String,
    pub endpoint: String,
    pub value: PredictionValue,
    pub ci_lower: Option<f64>,
    pub ci_upper: Option<f64>,
    #[serde(default = "default_ci_level")]
    pub ci_level: f64,
    pub ad_status: AdStatus,
    pub ad_score: Option<f64>,
    pub units: String,
    pub model_id: String,
    pub model_version: String,
    pub tier: u8,
    pub timestamp: DateTime<Utc>,
    #[serde(default)]
    pub provenance: serde_json::Value,
    #[serde(default)]
    pub warnings: Vec<String>,
}

fn default_ci_level() -> f64 { 0.95 }

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelCard {
    pub model_id: String,
    pub name: String,
    pub version: String,
    pub tier: u8,
    pub endpoint: String,
    pub description: String,
    pub intended_use: String,
    #[serde(default)]
    pub not_intended_for: Vec<String>,
    pub training_data: Option<TrainingDataInfo>,
    pub performance: Option<PerformanceMetrics>,
    pub applicability_domain: Option<AdDefinition>,
    pub uncertainty_method: Option<String>,
    #[serde(default)]
    pub known_failure_modes: Vec<String>,
    #[serde(default)]
    pub references: Vec<String>,
    pub license: String,
    pub created: DateTime<Utc>,
    #[serde(default)]
    pub authors: Vec<String>,
}

// TrainingDataInfo, PerformanceMetrics, AdDefinition: mirror Python definitions.
```

---

## 6. Task Manifest

Tasks are grouped by component. Within a group, execute in numeric order. Across groups, respect explicit dependencies. Tasks marked `[parallelizable]` can run alongside others.

---

### Group A — Core Python Interfaces

#### Task A1: Implement canonical endpoint enum
**Depends on:** none.
**File:** `python/edeon_models/endpoints.py`
**Goal:** Implement `Endpoint` as `StrEnum` with exact values from Section 4.

```python
from enum import StrEnum

class Endpoint(StrEnum):
    BEE_ACUTE_ORAL_LD50 = "bee_acute_oral_ld50"
    BEE_ACUTE_CONTACT_LD50 = "bee_acute_contact_ld50"
    # ... all 16 endpoints from Section 4
```

Add a function `endpoint_metadata(ep: Endpoint) -> dict` returning units and direction for each endpoint.

**Acceptance:** `Endpoint.BEE_ACUTE_ORAL_LD50 == "bee_acute_oral_ld50"` is `True`. All 16 endpoints present. Unit tests in `tests/python/test_endpoints.py`.

---

#### Task A2: Implement core data structures
**Depends on:** A1.
**File:** `python/edeon_models/types.py`
**Goal:** Implement all dataclasses from Section 5.1 verbatim. Use pydantic v2. Add `__all__`.

**Acceptance:** All classes validate with example inputs. Round-trip serialization (`.model_dump_json()` → `.model_validate_json()`) preserves values. Unit tests in `tests/python/test_types.py`.

---

#### Task A3: Implement ModelBackend ABC
**Depends on:** A1, A2.
**File:** `python/edeon_models/backend.py`

```python
from abc import ABC, abstractmethod
from typing import Optional
from .types import Prediction, ADStatus, ModelCard
from .endpoints import Endpoint


class ModelBackend(ABC):
    """Abstract base class for all Edeon predictor backends."""

    @abstractmethod
    def endpoint(self) -> Endpoint:
        """Canonical endpoint identifier this backend serves."""

    @abstractmethod
    def tier(self) -> int:
        """1=Reference, 2=Baseline, 3=External, 4=User."""

    @abstractmethod
    def version(self) -> str:
        """Semantic version string."""

    @abstractmethod
    def predict(
        self,
        smiles: list[str],
        conditions: Optional[dict] = None
    ) -> list[Prediction]:
        """Run prediction. Returns one Prediction per input SMILES.
        Must always populate ad_status (use ADStatus.UNKNOWN if no AD)."""

    @abstractmethod
    def applicability_domain(self, smiles: list[str]) -> list[ADStatus]:
        """Return AD status for each SMILES. Default backends without AD
        should return [ADStatus.UNKNOWN] * len(smiles)."""

    @abstractmethod
    def metadata(self) -> ModelCard:
        """Return the model card."""

    # Convenience: default implementations
    def model_id(self) -> str:
        return f"{self.endpoint().value}.t{self.tier()}.{self.version()}"
```

**Acceptance:** A minimal `MockBackend` subclass passing all abstract methods runs in tests. `model_id()` returns expected format.

---

#### Task A4: Implement BackendRegistry
**Depends on:** A3.
**File:** `python/edeon_models/registry.py`

```python
from typing import Optional
from .backend import ModelBackend
from .endpoints import Endpoint


class BackendRegistry:
    """Central registry mapping endpoints to available backends."""

    def __init__(self):
        self._backends: dict[Endpoint, dict[int, ModelBackend]] = {}
        self._preferences: dict[Endpoint, int] = {}  # endpoint → preferred tier

    def register(self, backend: ModelBackend) -> None:
        ep = backend.endpoint()
        tier = backend.tier()
        self._backends.setdefault(ep, {})[tier] = backend

    def get(
        self,
        endpoint: Endpoint,
        preferred_tier: Optional[int] = None
    ) -> ModelBackend:
        """Resolve a backend for the endpoint. Resolution order:
        1. Explicit preferred_tier if registered.
        2. User preference for this endpoint if set.
        3. Lowest available tier number (T1 before T2 before T3 before T4).
        Raises KeyError if no backend exists for the endpoint.
        """
        if endpoint not in self._backends:
            raise KeyError(f"No backend registered for {endpoint}")
        available = self._backends[endpoint]
        if preferred_tier is not None and preferred_tier in available:
            return available[preferred_tier]
        user_pref = self._preferences.get(endpoint)
        if user_pref is not None and user_pref in available:
            return available[user_pref]
        # Default: lowest tier number wins (T1 preferred)
        return available[min(available.keys())]

    def list_for_endpoint(self, endpoint: Endpoint) -> list[ModelBackend]:
        return list(self._backends.get(endpoint, {}).values())

    def set_preference(self, endpoint: Endpoint, tier: int) -> None:
        self._preferences[endpoint] = tier

    def all_endpoints(self) -> list[Endpoint]:
        return list(self._backends.keys())
```

**Acceptance:** Registering two backends for the same endpoint and calling `get()` returns the lowest-tier one by default. Setting preference changes the result. KeyError on unknown endpoint. Tests in `tests/python/test_registry.py`.

---

### Group B — UQ and AD Wrappers

#### Task B1: Implement Tanimoto k-NN AD strategy
**Depends on:** A2.
**File:** `python/edeon_models/ad/tanimoto_knn.py`

```python
from typing import Optional
import numpy as np
from rdkit import Chem, DataStructs
from rdkit.Chem import AllChem
from ..types import ADStatus
from .base import ADStrategy


class TanimotoKNN_AD(ADStrategy):
    """Applicability domain via Tanimoto distance to k nearest training neighbours.

    A query is IN if its mean distance to k nearest training neighbours is
    below the in_threshold (default 95th percentile of intra-training-set
    distances). BORDERLINE if between in_threshold and out_threshold (default
    99th percentile). OUT otherwise.
    """

    def __init__(
        self,
        training_smiles: list[str],
        k: int = 5,
        in_threshold: Optional[float] = None,
        out_threshold: Optional[float] = None,
        fp_radius: int = 2,
        fp_bits: int = 2048,
    ):
        self.k = k
        self.fp_radius = fp_radius
        self.fp_bits = fp_bits
        self._train_fps = [self._fp(s) for s in training_smiles]
        self._train_fps = [f for f in self._train_fps if f is not None]
        # Calibrate thresholds from training set if not provided
        if in_threshold is None or out_threshold is None:
            distances = self._calibrate()
            self.in_threshold = in_threshold or float(np.percentile(distances, 95))
            self.out_threshold = out_threshold or float(np.percentile(distances, 99))
        else:
            self.in_threshold = in_threshold
            self.out_threshold = out_threshold

    def _fp(self, smiles: str):
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None
        return AllChem.GetMorganFingerprintAsBitVect(mol, self.fp_radius, self.fp_bits)

    def _calibrate(self) -> np.ndarray:
        """Compute mean k-NN distance for each training compound (excluding itself)."""
        n = len(self._train_fps)
        result = []
        for i, fp in enumerate(self._train_fps):
            sims = DataStructs.BulkTanimotoSimilarity(
                fp, [f for j, f in enumerate(self._train_fps) if j != i]
            )
            dists = 1.0 - np.array(sims)
            top_k = np.sort(dists)[:self.k]
            result.append(float(np.mean(top_k)))
        return np.array(result)

    def score(self, smiles: list[str]) -> list[tuple[ADStatus, Optional[float]]]:
        out = []
        for s in smiles:
            fp = self._fp(s)
            if fp is None:
                out.append((ADStatus.UNKNOWN, None))
                continue
            sims = DataStructs.BulkTanimotoSimilarity(fp, self._train_fps)
            dists = 1.0 - np.array(sims)
            top_k = np.sort(dists)[:self.k]
            mean_dist = float(np.mean(top_k))
            if mean_dist <= self.in_threshold:
                status = ADStatus.IN
            elif mean_dist <= self.out_threshold:
                status = ADStatus.BORDERLINE
            else:
                status = ADStatus.OUT
            out.append((status, mean_dist))
        return out
```

**File:** `python/edeon_models/ad/base.py` — define `ADStrategy` ABC with `score()` method.

**Acceptance:** A toy training set of 50 SMILES, test with 5 in-domain (analogues) and 5 obviously out-of-domain (e.g., random ZINC structures) returns expected status. Tests in `tests/python/test_ad.py`.

---

#### Task B2: Implement ADWrapper
**Depends on:** B1, A3.
**File:** `python/edeon_models/ad/wrapper.py`

```python
from typing import Optional
from ..backend import ModelBackend
from ..types import Prediction, ADStatus
from ..endpoints import Endpoint
from .base import ADStrategy


class ADWrapper(ModelBackend):
    """Wraps a ModelBackend that lacks AD by applying an external ADStrategy."""

    def __init__(self, base: ModelBackend, ad_strategy: ADStrategy):
        self._base = base
        self._ad = ad_strategy

    def endpoint(self) -> Endpoint: return self._base.endpoint()
    def tier(self) -> int: return self._base.tier()
    def version(self) -> str: return f"{self._base.version()}+ad"

    def predict(self, smiles: list[str], conditions: Optional[dict] = None) -> list[Prediction]:
        preds = self._base.predict(smiles, conditions)
        ad_scores = self._ad.score(smiles)
        return [
            pred.model_copy(update={"ad_status": status, "ad_score": score})
            for pred, (status, score) in zip(preds, ad_scores)
        ]

    def applicability_domain(self, smiles: list[str]) -> list[ADStatus]:
        return [status for status, _ in self._ad.score(smiles)]

    def metadata(self):
        card = self._base.metadata()
        return card.model_copy(update={
            "applicability_domain": {
                "method": "tanimoto_knn",
                "threshold": self._ad.in_threshold if hasattr(self._ad, "in_threshold") else None,
            }
        })
```

**Acceptance:** Wrapping a backend that returns `ADStatus.UNKNOWN` produces predictions with proper AD scores.

---

#### Task B3: Implement UQ strategies
**Depends on:** A2.
**Files:**
- `python/edeon_models/uq/base.py` — `UQStrategy` ABC with `calibrate(...)` and `interval(point_estimate, smiles) -> (lower, upper)`.
- `python/edeon_models/uq/conformal.py` — `ConformalUQ` using split conformal prediction on a held-out calibration set.
- `python/edeon_models/uq/ensemble.py` — `EnsembleVarianceUQ` taking a list of point estimates from N ensemble members and computing mean ± z * std.

**Conformal implementation sketch:**

```python
class ConformalUQ(UQStrategy):
    def __init__(self, alpha: float = 0.05):
        self.alpha = alpha  # 0.05 → 95% CI
        self.quantile: Optional[float] = None

    def calibrate(self, predictions: np.ndarray, observations: np.ndarray) -> None:
        residuals = np.abs(predictions - observations)
        n = len(residuals)
        # Adjusted quantile for finite-sample coverage guarantee
        q_level = np.ceil((n + 1) * (1 - self.alpha)) / n
        self.quantile = float(np.quantile(residuals, q_level))

    def interval(self, point_estimate: float, smiles: Optional[str] = None) -> tuple[float, float]:
        if self.quantile is None:
            raise RuntimeError("Must call calibrate() before interval()")
        return (point_estimate - self.quantile, point_estimate + self.quantile)
```

**Acceptance:** On a synthetic regression task with known residual distribution, calibrated 95% intervals achieve empirical coverage ≥ 90% on held-out data. Tests in `tests/python/test_uq.py`.

---

#### Task B4: Implement UQWrapper
**Depends on:** B3, A3.
**File:** `python/edeon_models/uq/wrapper.py`

```python
class UQWrapper(ModelBackend):
    """Wraps a backend with point-estimate predictions to add UQ intervals."""

    def __init__(self, base: ModelBackend, uq_strategy: UQStrategy):
        self._base = base
        self._uq = uq_strategy

    # Delegate endpoint/tier/version/metadata to base, mark uncertainty_method in card.
    # predict(): for each Prediction, compute interval and set ci_lower/ci_upper.
    # Skip interval for categorical/binary predictions.
```

**Acceptance:** Numeric predictions get CI; categorical predictions pass through unchanged.

---

#### Task B5: Composite wrappers
**Depends on:** B2, B4.
**File:** `python/edeon_models/__init__.py` — provide convenience function `wrap_with_uq_and_ad(backend, training_smiles, calibration_residuals)`.

**Acceptance:** One-line composition produces a backend with both UQ and AD.

---

### Group C — ModelCard System

#### Task C1: ModelCard SQLite schema
**Depends on:** A2.
**File:** Add migration to existing SQLite schema (locate existing migrations folder under `src-tauri/migrations/` or similar). Create table:

```sql
CREATE TABLE IF NOT EXISTS model_cards (
    model_id TEXT PRIMARY KEY,
    endpoint TEXT NOT NULL,
    tier INTEGER NOT NULL,
    version TEXT NOT NULL,
    name TEXT NOT NULL,
    json_blob TEXT NOT NULL,           -- Full ModelCard as JSON
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_model_cards_endpoint ON model_cards(endpoint);
CREATE INDEX idx_model_cards_tier ON model_cards(tier);
```

**Acceptance:** Schema migration runs without error on a fresh database.

---

#### Task C2: ModelCard CRUD
**Depends on:** C1.
**File:** `python/edeon_models/card.py` — extend with:

```python
def save_card(card: ModelCard, db_path: str) -> None: ...
def load_card(model_id: str, db_path: str) -> Optional[ModelCard]: ...
def list_cards(endpoint: Optional[Endpoint] = None, db_path: str = ...) -> list[ModelCard]: ...
def delete_card(model_id: str, db_path: str) -> bool: ...
```

Use `json.dumps(card.model_dump(mode='json'))` for storage. Use `ModelCard.model_validate(json.loads(...))` for loading.

**Acceptance:** Round-trip storage preserves all fields including nested objects.

---

#### Task C3: ModelCard YAML serialization
**Depends on:** A2.
**File:** Extend `card.py` with:

```python
def card_to_yaml(card: ModelCard) -> str: ...
def card_from_yaml(yaml_str: str) -> ModelCard: ...
```

YAML is the human-readable export format. JSON in SQLite is for runtime.

**Acceptance:** Round-trip YAML preserves all fields.

---

#### Task C4: Document ModelCard schema
**Depends on:** A2.
**File:** `docs/MODEL_CARD_SCHEMA.md`
**Content:** Full field-by-field documentation of every ModelCard field with examples for at least one T1 and one T2 backend.

**Acceptance:** Markdown document exists with all fields documented.

---

### Group D — T2 Legacy Backend Migration

#### Task D1: Inventory existing predictors
**Depends on:** none.
**Action:** Locate the current Python files implementing the LogP-based predictors (likely under whatever directory holds `scoring.py`, `toxicity.py`, `selectivity.py`, `resistance.py`, etc.). Write inventory to `docs/PHASE0_NOTES.md` listing:
- Source file
- Function name
- Endpoint it serves
- Inputs (typically SMILES, sometimes computed properties)
- Output (currently raw values without metadata)

**Acceptance:** Inventory document complete for all 12 endpoints listed in the "Goal" of Section 0.

---

#### Task D2: Implement T2 backend wrappers
**Depends on:** D1, A3, A4.
**Files:** One file per endpoint under `python/edeon_models/backends/legacy/`.

**Pattern for each:**

```python
# python/edeon_models/backends/legacy/bee_ld50.py
from typing import Optional
from datetime import datetime
from edeon_models.backend import ModelBackend
from edeon_models.types import Prediction, PredictionValue, ADStatus, ModelCard
from edeon_models.endpoints import Endpoint
# Import the existing implementation (path will be discovered during D1)
from <existing_path> import predict_bee_ld50 as legacy_predict


class BeeLD50_T2(ModelBackend):
    _ENDPOINT = Endpoint.BEE_ACUTE_ORAL_LD50
    _VERSION = "0.1.0-legacy"
    _UNITS = "ug/bee"

    def endpoint(self) -> Endpoint: return self._ENDPOINT
    def tier(self) -> int: return 2
    def version(self) -> str: return self._VERSION

    def predict(self, smiles: list[str], conditions: Optional[dict] = None) -> list[Prediction]:
        out = []
        for s in smiles:
            try:
                value = legacy_predict(s)  # legacy returns a float
                out.append(Prediction(
                    smiles=s,
                    endpoint=self._ENDPOINT.value,
                    value=PredictionValue(kind="numeric", numeric=float(value)),
                    ad_status=ADStatus.UNKNOWN,
                    units=self._UNITS,
                    model_id=self.model_id(),
                    model_version=self._VERSION,
                    tier=2,
                    warnings=["Screening estimate — Tier-2 LogP-based heuristic"],
                ))
            except Exception as e:
                out.append(Prediction(
                    smiles=s,
                    endpoint=self._ENDPOINT.value,
                    value=PredictionValue(kind="numeric", numeric=float("nan")),
                    ad_status=ADStatus.UNKNOWN,
                    units=self._UNITS,
                    model_id=self.model_id(),
                    model_version=self._VERSION,
                    tier=2,
                    warnings=[f"Prediction failed: {e}"],
                ))
        return out

    def applicability_domain(self, smiles: list[str]) -> list[ADStatus]:
        return [ADStatus.UNKNOWN] * len(smiles)

    def metadata(self) -> ModelCard:
        return ModelCard(
            model_id=self.model_id(),
            name="Edeon Legacy Bee LD50 (LogP-based)",
            version=self._VERSION,
            tier=2,
            endpoint=self._ENDPOINT.value,
            description=(
                "Tier-2 baseline screening estimate of honeybee acute oral LD50 "
                "using a LogP-based heuristic from the original Edeon implementation."
            ),
            intended_use="Early-stage triage and qualitative ranking only.",
            not_intended_for=[
                "Regulatory dossier submission",
                "Quantitative risk assessment",
                "Replacement of OECD 213/214 testing",
            ],
            uncertainty_method=None,
            known_failure_modes=[
                "Structurally novel chemotypes outside typical agrochemical space",
                "Ionizable compounds where LogD ≠ LogP at relevant pH",
                "Compounds whose toxicity is mechanism-driven (e.g., neonicotinoids on nAChR)",
            ],
            references=[],
            license="Proprietary",
            authors=["Edeon Development Team"],
        )
```

Repeat this pattern for **every** endpoint listed in Section 4 that currently has a LogP-based implementation. Skip endpoints that don't currently exist in the codebase (e.g., `algae_growth_ec50`, `bcf` are not currently implemented — do not create T2 backends for missing endpoints).

**Acceptance:** Each existing LogP predictor has a corresponding T2 backend. Calling `predict(["CCO"])` on each returns a valid `Prediction`. Each backend has a populated `ModelCard`.

---

#### Task D3: Register T2 backends at startup
**Depends on:** D2, A4.
**File:** `python/edeon_models/__init__.py`

Add a `build_default_registry()` function that constructs a `BackendRegistry` and registers all T2 backends:

```python
def build_default_registry() -> BackendRegistry:
    from .registry import BackendRegistry
    from .backends.legacy import (
        BeeLD50_T2, FishLC50_T2, DaphniaEC50_T2,
        EarthwormLC50_T2, MallardLD50_T2, RatLD50_T2,
        SkinSensitization_T2, EyeIrritation_T2,
        SoilKoc_T2, SoilDT50_T2, GUSIndex_T2,
        Photostability_T2,
    )
    reg = BackendRegistry()
    for cls in [BeeLD50_T2, FishLC50_T2, DaphniaEC50_T2,
                EarthwormLC50_T2, MallardLD50_T2, RatLD50_T2,
                SkinSensitization_T2, EyeIrritation_T2,
                SoilKoc_T2, SoilDT50_T2, GUSIndex_T2,
                Photostability_T2]:
        reg.register(cls())
    return reg
```

**Acceptance:** `build_default_registry()` returns a registry with all 12 T2 backends. `reg.get(Endpoint.BEE_ACUTE_ORAL_LD50)` returns the T2 backend.

---

#### Task D4: Persist T2 ModelCards on startup
**Depends on:** D3, C2.
**Action:** Extend `build_default_registry()` to also call `save_card(backend.metadata(), db_path)` for each registered backend, creating or updating the SQLite entry.

**Acceptance:** After first startup, SQLite `model_cards` table contains rows for all 12 T2 backends.

---

### Group E — Rust Core & IPC

#### Task E1: Mirror Rust types
**Depends on:** Section 5.2.
**File:** `src-tauri/src/models/types.rs`
**Action:** Implement all Rust types from Section 5.2. Add `Endpoint` enum mirroring Python (use `#[serde(rename_all = "snake_case")]`).

**Acceptance:** Rust types deserialize from example JSON produced by Python `Prediction.model_dump_json()`.

---

#### Task E2: Implement BackendProxy
**Depends on:** E1.
**File:** `src-tauri/src/models/proxy.rs`

The Rust proxy calls into the Python predictor process. Use the existing IPC mechanism; do not invent a new one. Wrap calls in functions:

```rust
pub struct BackendProxy { /* handle to existing Python IPC */ }

impl BackendProxy {
    pub async fn predict(
        &self,
        endpoint: &str,
        smiles: Vec<String>,
        preferred_tier: Option<u8>,
    ) -> Result<Vec<Prediction>, BackendError>;

    pub async fn list_backends(&self, endpoint: &str) -> Result<Vec<ModelCard>, BackendError>;
    pub async fn get_card(&self, model_id: &str) -> Result<ModelCard, BackendError>;
    pub async fn set_preference(&self, endpoint: &str, tier: u8) -> Result<(), BackendError>;
    pub async fn get_preferences(&self) -> Result<HashMap<String, u8>, BackendError>;
}
```

**Acceptance:** Each method round-trips successfully against the Python IPC server (E5).

---

#### Task E3: Tier preference store
**Depends on:** C1.
**File:** `src-tauri/src/models/preferences.rs`

Persist user tier preferences in SQLite:

```sql
CREATE TABLE IF NOT EXISTS model_tier_preferences (
    endpoint TEXT PRIMARY KEY,
    tier INTEGER NOT NULL,
    updated_at TEXT NOT NULL
);
```

API: `set_preference(endpoint, tier)`, `get_preference(endpoint) -> Option<u8>`, `clear_preference(endpoint)`.

**Acceptance:** Preferences persist across app restarts.

---

#### Task E4: Tauri commands
**Depends on:** E2, E3.
**File:** `src-tauri/src/main.rs` (or wherever commands are registered)

Register Tauri commands:
- `model_predict(endpoint: String, smiles: Vec<String>, preferred_tier: Option<u8>) -> Vec<Prediction>`
- `model_list_for_endpoint(endpoint: String) -> Vec<ModelCard>`
- `model_get_card(model_id: String) -> ModelCard`
- `model_set_preference(endpoint: String, tier: u8) -> ()`
- `model_get_preference(endpoint: String) -> Option<u8>`
- `model_list_endpoints() -> Vec<String>`

**Acceptance:** Each command callable from frontend via `invoke()`.

---

#### Task E5: Python IPC server
**Depends on:** D3, A4.
**Files:** `python/edeon_models/ipc/server.py`, `python/edeon_models/ipc/commands.py`

Implement a JSON-over-stdio server that the Rust core spawns. Each request is `{"id": str, "command": str, "args": {...}}`. Each response is `{"id": str, "result": ..., "error": ...}`.

Commands supported:
- `predict`
- `list_for_endpoint`
- `get_card`
- `set_preference`
- `get_preference`
- `list_endpoints`

Server holds a singleton `BackendRegistry` from `build_default_registry()`.

**Acceptance:** Standalone script test: send each command as JSON, receive correctly-shaped response.

---

### Group F — QSAR Studio Deployment Bridge

#### Task F1: Extend SavedModel schema
**Depends on:** existing QSAR Studio code.
**Action:** Locate the existing `saved_models` SQLite schema. Add columns:

```sql
ALTER TABLE saved_models ADD COLUMN deploy_target TEXT;       -- Endpoint identifier or NULL
ALTER TABLE saved_models ADD COLUMN deployed_at TEXT;          -- Timestamp when deployed
ALTER TABLE saved_models ADD COLUMN deployment_status TEXT DEFAULT 'undeployed';
                                                                -- 'undeployed' | 'deployed' | 'archived'
```

**Acceptance:** Migration runs; existing saved models receive NULL `deploy_target` and `deployment_status = 'undeployed'`.

---

#### Task F2: StudioBackend wrapper
**Depends on:** F1, A3, B2, B4.
**File:** `python/edeon_models/backends/studio/studio_backend.py`

```python
class StudioBackend(ModelBackend):
    """Wraps a model trained in QSAR Studio for use as a T4 backend."""

    def __init__(self, saved_model_id: str, db_path: str, deploy_target: Endpoint):
        # Load pickled sklearn model from QSAR Studio storage
        # Load training SMILES for AD construction
        # Load calibration residuals if available, else compute on training set
        ...

    def endpoint(self) -> Endpoint: return self._deploy_target
    def tier(self) -> int: return 4
    def version(self) -> str: return f"studio-{self._saved_model_id}"

    def predict(self, smiles: list[str], conditions=None) -> list[Prediction]:
        # Featurize using the featurizer stored with the model
        # Run sklearn predict
        # Apply UQ wrapper for CI
        # Apply AD wrapper for AD status
        # Construct Prediction objects with tier=4
        ...

    def applicability_domain(self, smiles: list[str]) -> list[ADStatus]:
        ...

    def metadata(self) -> ModelCard:
        # Construct ModelCard from QSAR Studio metadata:
        # training data info, performance metrics from training,
        # featurizer name in description, etc.
        ...
```

**Acceptance:** Given a saved scikit-learn model from QSAR Studio, `StudioBackend` loads it and produces valid `Prediction` objects.

---

#### Task F3: Deployment service
**Depends on:** F2, A4, C2.
**File:** `python/edeon_models/backends/studio/__init__.py`

```python
def deploy_studio_model(saved_model_id: str, endpoint: Endpoint, registry, db_path: str) -> ModelCard:
    """Deploy a QSAR Studio model as a T4 backend for the given endpoint.

    Steps:
    1. Load saved model from QSAR Studio storage.
    2. Validate model output type matches endpoint expectation.
    3. Construct StudioBackend.
    4. Register in registry (replaces any prior T4 for the endpoint).
    5. Save ModelCard to SQLite.
    6. Update saved_models table: deploy_target, deployed_at, deployment_status='deployed'.
    7. Return the ModelCard.
    """

def undeploy_studio_model(saved_model_id: str, registry, db_path: str) -> None:
    """Reverse the deploy: remove from registry, update saved_models status."""
```

**Acceptance:** Deploy → predict via registry returns T4 prediction. Undeploy → registry falls back to T2.

---

#### Task F4: IPC commands for deployment
**Depends on:** F3, E5.
**Action:** Add commands `deploy_studio_model(saved_model_id, endpoint)` and `undeploy_studio_model(saved_model_id)` to the Python IPC server. Add corresponding Tauri commands in `src-tauri/`.

**Acceptance:** Tauri command `deploy_studio_model` callable from frontend.

---

#### Task F5: Studio UI "Deploy to Pipeline" button
**Depends on:** F4, existing QSAR Studio UI.
**Action:** In the QSAR Studio model card UI (locate existing model card component), add:
- A dropdown to select target `Endpoint` from the canonical list.
- A "Deploy to Pipeline" button that invokes `deploy_studio_model`.
- A status indicator showing whether the model is deployed and to which endpoint.
- An "Undeploy" button when deployed.

**Acceptance:** End-to-end: train a model in Studio → deploy via UI → run a prediction in Inspector → see Tier-4 prediction in the response.

---

### Group G — Frontend Components

#### Task G1: ModelTierBadge
**Depends on:** E4.
**File:** `src/components/models/ModelTierBadge.tsx`

Props: `tier: 1 | 2 | 3 | 4`. Renders a small badge with colour and label:
- T1: green, "Reference"
- T2: yellow, "Screening"
- T3: blue, "External"
- T4: purple, "Custom"

Tooltip on hover explains the tier. Visual style: rounded pill, ~20px height, inline with prediction value.

**Acceptance:** Storybook entry or test page renders all four tiers correctly.

---

#### Task G2: ADWarning
**Depends on:** E4.
**File:** `src/components/models/ADWarning.tsx`

Props: `status: 'in' | 'borderline' | 'out' | 'unknown'`, `score?: number`. Renders:
- IN: small green check icon, "In domain"
- BORDERLINE: yellow warning icon, "Borderline"
- OUT: red warning icon, "Out of domain"
- UNKNOWN: grey icon, "AD unknown"

Tooltip shows the AD score if provided.

**Acceptance:** All four states render.

---

#### Task G3: PredictionDisplay
**Depends on:** G1, G2.
**File:** `src/components/models/PredictionDisplay.tsx`

Props: `prediction: Prediction`. Renders:
- Primary value with units (large, prominent)
- CI as "[lower – upper]" if present (smaller, below value)
- TierBadge inline with value
- ADWarning inline with value
- Warnings (if any) as a small italic note below
- Click opens ModelCardViewer modal (G4)

This component replaces all direct value displays throughout the Inspector (honeycomb cells, fate gauge, toxicity panel, etc.).

**Acceptance:** Renders a complete prediction with all metadata visible.

---

#### Task G4: ModelCardViewer
**Depends on:** E4.
**File:** `src/components/models/ModelCardViewer.tsx`

Modal/dialog component. Props: `modelId: string` (fetches card via `model_get_card` IPC).

Layout:
- Header: model name, version, tier badge
- Description and intended use
- "Not intended for" warnings (prominent)
- Training data details (collapsible)
- Performance metrics table (if T1 with metrics)
- Applicability domain details
- Known failure modes (list)
- References (linked list)
- Authors and license

**Acceptance:** Opens for any model_id and displays all populated fields.

---

#### Task G5: TierPreferenceSelector
**Depends on:** E4.
**File:** `src/components/models/TierPreferenceSelector.tsx`

Used in Settings. Renders a list of all endpoints with a dropdown per endpoint allowing the user to pin a preferred tier or use "Auto" (default).

**Acceptance:** Setting a preference and re-running a prediction shows the chosen tier.

---

#### Task G6: Integrate into Inspector
**Depends on:** G3.
**Action:** Replace direct value displays in:
- Beneficial Organism Honeycomb (each cell)
- Environmental Fate gauge
- Toxicity panel
- Any other predictor surface

Each location uses `<PredictionDisplay prediction={...} />` instead of raw value rendering. The predictions come from new IPC calls to `model_predict` for each endpoint.

**Important:** This is a UI replacement, not a logic change. The same predictions render with metadata visible.

**Acceptance:** Every predicted value in the Inspector shows tier, AD, and CI (or "no CI" indicator) consistently.

---

#### Task G7: Settings panel for tier preferences
**Depends on:** G5.
**Action:** Add a "Model Preferences" section to the existing Settings view containing the `TierPreferenceSelector`.

**Acceptance:** Section visible and functional.

---

### Group H — Continuous Validation Harness

#### Task H1: Fixture schema
**Depends on:** A2.
**File:** `tests/regression/fixtures/SCHEMA.md`

Document the fixture CSV format:

```
smiles,endpoint,expected_value,expected_value_lower,expected_value_upper,notes
CCO,bee_acute_oral_ld50,12.5,5.0,30.0,"Tier-2 LogP baseline"
```

Note: "expected" values are not ground truth — they are the values the current implementation produces, frozen. The purpose is to detect *drift*, not to validate correctness (correctness comes in later phases).

**Acceptance:** Schema document exists.

---

#### Task H2: Generate initial fixtures
**Depends on:** D3, H1.
**Action:** For each registered T2 backend, run predictions on a fixed set of 20 SMILES (pick a representative agrochemistry-relevant set: 5 marketed pesticides per class — insecticides, herbicides, fungicides — plus 5 generic chemicals). Save outputs as CSV fixtures under `tests/regression/fixtures/<endpoint>_v1.csv`. Use seed 42 for any random sampling.

**Suggested seed compound set (20 SMILES):**

```
# Insecticides: imidacloprid, chlorpyrifos, deltamethrin, fipronil, chlorantraniliprole
# Herbicides: glyphosate, atrazine, mesotrione, sulfonylurea (chlorsulfuron), glufosinate
# Fungicides: azoxystrobin, propiconazole, boscalid, mancozeb, tebuconazole
# Reference chems: ethanol, benzene, caffeine, paracetamol, 4-chlorophenol
```

Provide actual SMILES in the fixture-generation script.

**Acceptance:** One CSV per endpoint, with 20 rows each.

---

#### Task H3: Tolerance configuration
**Depends on:** H1.
**File:** `tests/regression/tolerance.yaml`

```yaml
# Per-endpoint tolerance for numeric predictions.
# A prediction is considered drifted if |new - expected| > tolerance.
bee_acute_oral_ld50:
  rel_tol: 0.05      # 5% relative tolerance
  abs_tol: 0.001     # absolute floor
fish_acute_lc50:
  rel_tol: 0.05
  abs_tol: 0.001
# ... repeat for all endpoints

categorical_endpoints:
  - skin_sensitization
  - eye_irritation
  - photostability_class
# Categorical endpoints must match exactly.
```

**Acceptance:** YAML loads without error.

---

#### Task H4: Regression test runner
**Depends on:** H2, H3, D3.
**File:** `tests/regression/test_regression.py`

```python
import pytest
import yaml
from pathlib import Path
import pandas as pd
from edeon_models import build_default_registry
from edeon_models.endpoints import Endpoint

FIXTURES_DIR = Path(__file__).parent / "fixtures"
TOLERANCE = yaml.safe_load((Path(__file__).parent / "tolerance.yaml").read_text())


@pytest.fixture(scope="module")
def registry():
    return build_default_registry()


def fixture_files():
    return sorted(FIXTURES_DIR.glob("*.csv"))


@pytest.mark.parametrize("fixture_path", fixture_files(), ids=lambda p: p.stem)
def test_no_drift(fixture_path, registry):
    df = pd.read_csv(fixture_path)
    endpoint_str = df["endpoint"].iloc[0]
    endpoint = Endpoint(endpoint_str)
    backend = registry.get(endpoint, preferred_tier=2)  # Always test T2 in Phase 0
    smiles = df["smiles"].tolist()
    predictions = backend.predict(smiles)

    tol = TOLERANCE.get(endpoint_str, {"rel_tol": 0.05, "abs_tol": 0.001})
    is_categorical = endpoint_str in TOLERANCE.get("categorical_endpoints", [])

    failures = []
    for row, pred in zip(df.itertuples(), predictions):
        if is_categorical:
            if pred.value.categorical != row.expected_value:
                failures.append(f"{row.smiles}: expected {row.expected_value}, got {pred.value.categorical}")
        else:
            expected = float(row.expected_value)
            actual = pred.value.numeric
            if not (abs(actual - expected) <= tol["abs_tol"] + tol["rel_tol"] * abs(expected)):
                failures.append(f"{row.smiles}: expected {expected:.4g}, got {actual:.4g}")

    assert not failures, f"Drift detected for {endpoint_str}:\n" + "\n".join(failures)
```

**Acceptance:** Test runs green on first invocation (since fixtures were generated by the same backends). Manually breaking a T2 implementation causes the corresponding test to fail with a clear message.

---

#### Task H5: CI workflow
**Depends on:** H4.
**File:** `.github/workflows/regression.yml`

```yaml
name: Regression Tests
on: [push, pull_request]
jobs:
  regression:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: |
          pip install -e ./python
          pip install pytest rdkit pandas pyyaml pydantic
      - name: Run regression tests
        run: pytest tests/regression/ -v
```

**Acceptance:** CI runs on PR and reports pass/fail.

---

### Group I — Integration Tests

#### Task I1: End-to-end T2 prediction
**Depends on:** all of A, B, D, E, G.
**Action:** Integration test that:
1. Starts the Python IPC server.
2. Calls `model_predict` from Rust for `bee_acute_oral_ld50` with SMILES `["CCO"]`.
3. Asserts response shape: tier=2, units="ug/bee", warnings contains "Screening estimate".

**File:** `tests/integration/test_e2e_t2.py`

**Acceptance:** Test passes.

---

#### Task I2: End-to-end Studio deployment
**Depends on:** Group F, Group G.
**Action:** Integration test that:
1. Trains a trivial scikit-learn model via the QSAR Studio code path on a synthetic dataset for `bee_acute_oral_ld50`.
2. Calls `deploy_studio_model(saved_id, "bee_acute_oral_ld50")`.
3. Calls `model_predict` for `bee_acute_oral_ld50` — asserts tier=4.
4. Calls `undeploy_studio_model(saved_id)`.
5. Calls `model_predict` again — asserts tier=2 (fallback).

**File:** `tests/integration/test_e2e_studio_deployment.py`

**Acceptance:** Test passes.

---

#### Task I3: Smoke test for UI integration
**Depends on:** Group G.
**Action:** Manual test checklist documented in `docs/PHASE0_NOTES.md`:
- [ ] Open Inspector with a compound.
- [ ] Verify each predictor cell shows tier badge.
- [ ] Verify AD warning displays (UNKNOWN for T2 backends).
- [ ] Click a value → ModelCardViewer opens.
- [ ] Open Settings → Model Preferences shows endpoints.
- [ ] Set a preference → re-run prediction → preference respected.
- [ ] Open QSAR Studio → train a model → click "Deploy to Pipeline" → predict in Inspector → see T4 badge.

**Acceptance:** Checklist documented; manual run by developer passes all items.

---

## 7. Acceptance Criteria for Phase 0 Complete

Phase 0 is complete when ALL of the following are true:

1. `from edeon_models import build_default_registry; reg = build_default_registry()` returns a registry with all 12 T2 backends listed in Section 4 (excluding `algae_growth_ec50` and `bcf` which are not currently implemented).
2. Each T2 backend's `predict()` returns valid `Prediction` objects with `tier=2`, `warnings` containing screening notice, and `ad_status=UNKNOWN`.
3. Each T2 backend's `metadata()` returns a complete `ModelCard` persisted to SQLite.
4. The Tauri command `model_predict` works end-to-end from frontend → Rust → Python → response.
5. Every predicted value rendered in the Inspector shows a tier badge and AD status.
6. The QSAR Studio "Deploy to Pipeline" button successfully deploys a trained model as T4, and the registry serves it on subsequent prediction calls.
7. Undeploying a Studio model falls back cleanly to T2.
8. The regression CI workflow runs on every PR and detects deliberate drift in a T2 backend.
9. `docs/MODEL_CARD_SCHEMA.md` and `docs/PHASE0_NOTES.md` are populated.
10. All unit tests in `tests/python/` and integration tests in `tests/integration/` pass.

---

## 8. Out of Scope (for Phase 0)

Explicitly **do not** do the following in Phase 0:

- Train any new T1 models. (Phase 2.)
- Integrate any external T3 APIs (OPERA, EPI Suite). (Phase 5.)
- Replace any LogP-based science with better models. (Phase 2–6.)
- Refactor the QSAR Studio internals beyond adding the `deploy_target` field and deployment service.
- Modify the Knowledge tab, 3D viewer, or Reports.
- Build the Algae or BCF endpoints. (Phase 2.)
- Change the visual design of any existing component beyond inserting tier/AD/CI displays.
- Add user authentication, multi-user features, or cloud sync.
- Address the bioisostere engine or "fake docking" issues. (Phase 6.)

If the agent identifies that Phase 0 cannot be completed without one of these, document the blocker in `docs/PHASE0_NOTES.md` and stop — do not silently expand scope.

---

## 9. Conventions

- **Naming:** Python `snake_case`, Rust `snake_case` for functions / `PascalCase` for types, TypeScript `camelCase` for functions / `PascalCase` for components.
- **Errors:** Python raises typed exceptions (define `BackendError`, `EndpointNotFoundError`, `ModelLoadError` in `edeon_models.exceptions`); Rust returns `Result<T, BackendError>`.
- **Logging:** Python uses `logging` module with logger named `edeon_models`. Rust uses `tracing`.
- **Time:** All timestamps are UTC, ISO 8601 with timezone suffix.
- **SMILES:** All inputs are canonicalised with RDKit before any processing. Document this in the BackendProxy / IPC layer.
- **Commits:** One commit per task ID where possible, with message format `[A3] Implement ModelBackend ABC`.

---

## 10. Deviation Log

Maintain `docs/PHASE0_NOTES.md` with:
- Each assumption that turned out to be wrong (e.g., wrong file path, missing dependency)
- Each blocker encountered
- Each scope question resolved
- Final manual test results from I3

This is the artifact a human reviewer will read to understand what the agent actually did.

---

**End of Phase 0 Specification.**
