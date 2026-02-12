from typing import Dict, List
from .schema import EndpointDelta, BioisostereSuggestion, TransformationRule

def score_transformation(
    deltas: List[EndpointDelta],
    weights: Dict[str, float] = None,
) -> float:
    """Returns a transformation score (higher = better).
    
    Default weights prioritize: better ecotox profile (lower bee/fish toxicity),
    lower mammalian toxicity, lower environmental persistence, with property
    space staying in pesticide-like range.
    """
    weights = weights or {
        "bee_acute_oral_ld50": +0.20,            # higher LD50 is better -> positive delta good
        "fish_acute_lc50": +0.15,
        "rat_acute_oral_ld50": +0.15,
        "mutagenicity_ames": -0.10,             # lower prob is better -> negative delta good
        "skin_sensitization": -0.05,
        "soil_dt50": -0.10,                     # lower DT50 (less persistent) is better -> negative delta good
        "bcf": -0.10,
    }
    
    score = 0.0
    for delta in deltas:
        w = weights.get(delta.endpoint, 0.0)
        # Add weighted delta
        score += w * delta.delta
        
    return score

class RankingEngine:
    def __init__(self, weights: Dict[str, float] = None):
        self._weights = weights

    def rank(self, suggestions: List[BioisostereSuggestion], sort_by: str = "composite") -> List[BioisostereSuggestion]:
        """Ranks suggestions by composite score, minimal change, or occurrence frequency."""
        if sort_by == "composite":
            return sorted(suggestions, key=lambda s: s.composite_score, reverse=True)
        elif sort_by == "minimal_change":
            # Sort by minimal delta sum as a proxy for minimal change
            return sorted(suggestions, key=lambda s: sum(abs(d.delta) for d in s.deltas))
        elif sort_by == "occurrence":
            return sorted(suggestions, key=lambda s: s.rule.occurrence_frequency, reverse=True)
        else:
            return suggestions
