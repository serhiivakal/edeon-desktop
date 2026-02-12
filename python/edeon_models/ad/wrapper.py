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

    def endpoint(self) -> Endpoint: 
        return self._base.endpoint()
        
    def tier(self) -> int: 
        return self._base.tier()
        
    def version(self) -> str: 
        return f"{self._base.version()}+ad"

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
        threshold_val = self._ad.in_threshold if hasattr(self._ad, "in_threshold") else None
        
        from ..types import ADDefinition
        ad_obj = ADDefinition(
            method="tanimoto_knn",
            threshold=threshold_val
        )
        
        return card.model_copy(update={
            "applicability_domain": ad_obj
        })
