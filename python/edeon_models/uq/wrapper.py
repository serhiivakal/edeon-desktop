from typing import Optional
from ..backend import ModelBackend
from ..types import Prediction, ADStatus, ModelCard
from ..endpoints import Endpoint
from .base import UQStrategy

class UQWrapper(ModelBackend):
    """Wraps a ModelBackend with point-estimate predictions to add UQ intervals."""

    def __init__(self, base: ModelBackend, uq_strategy: UQStrategy):
        self._base = base
        self._uq = uq_strategy

    def endpoint(self) -> Endpoint: 
        return self._base.endpoint()
        
    def tier(self) -> int: 
        return self._base.tier()
        
    def version(self) -> str: 
        return f"{self._base.version()}+uq"

    def predict(self, smiles: list[str], conditions: Optional[dict] = None) -> list[Prediction]:
        preds = self._base.predict(smiles, conditions)
        
        out = []
        for pred in preds:
            # Skip interval calculation for categorical or binary predictions
            if pred.value.kind == "numeric" and pred.value.numeric is not None:
                lower, upper = self._uq.interval(pred.value.numeric, pred.smiles)
                out.append(pred.model_copy(update={
                    "ci_lower": lower,
                    "ci_upper": upper,
                    "ci_level": getattr(self._uq, "alpha", 0.05) if hasattr(self._uq, "alpha") else 0.95
                }))
            else:
                out.append(pred)
        return out

    def applicability_domain(self, smiles: list[str]) -> list[ADStatus]:
        return self._base.applicability_domain(smiles)

    def metadata(self) -> ModelCard:
        card = self._base.metadata()
        uq_method_name = self._uq.__class__.__name__
        
        return card.model_copy(update={
            "version": f"{card.version}+uq",
            "uncertainty_method": uq_method_name
        })
