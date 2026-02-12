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
