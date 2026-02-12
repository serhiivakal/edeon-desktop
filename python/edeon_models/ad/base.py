from abc import ABC, abstractmethod
from typing import Optional
from ..types import ADStatus

class ADStrategy(ABC):
    """Abstract base class for all applicability domain (AD) strategies."""

    @abstractmethod
    def score(self, smiles: list[str]) -> list[tuple[ADStatus, Optional[float]]]:
        """Assess the applicability domain of a list of SMILES compounds.
        
        Returns a list of tuples containing (ADStatus, score) for each compound.
        The score can represent the Tanimoto distance, leverage, or any other numeric
        metric defining the distance to the training set distribution.
        """
