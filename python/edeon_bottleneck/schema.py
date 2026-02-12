"""
Edeon Bottleneck Analyzer — Result Schema

Typed dataclasses for the bottleneck analysis output.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class EndpointResult:
    """Analysis result for a single endpoint."""
    endpoint: str
    display_name: str
    leverage: float
    leverage_ci: tuple[float, float]
    headroom: float
    mean_desirability: float
    achievable_target: float
    rank: int
    rank_stability: float
    kind: str                   # "chemical" | "epistemic" | "distractor"
    recommended_action: str
    reason: str
    reliability: str            # "ok" | "low" | "insufficient_data"
    n_in_ad: int
    weight: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BottleneckAnalysis:
    """Full bottleneck analysis result."""
    analysis_id: str
    project_id: str
    profile: str
    n_compounds: int
    endpoints: list[EndpointResult]
    top_endpoint: Optional[str]
    top_kind: Optional[str]
    bottleneck_ambiguous: bool
    tradeoff_matrix: dict
    overall_reliability: str
    params_hash: str

    # Optional journal payload (Rust extracts + persists)
    journal_payload: Optional[dict] = None

    def to_dict(self) -> dict:
        result = {
            "analysis_id": self.analysis_id,
            "project_id": self.project_id,
            "profile": self.profile,
            "n_compounds": self.n_compounds,
            "endpoints": [ep.to_dict() for ep in self.endpoints],
            "top_endpoint": self.top_endpoint,
            "top_kind": self.top_kind,
            "bottleneck_ambiguous": self.bottleneck_ambiguous,
            "tradeoff_matrix": self.tradeoff_matrix,
            "overall_reliability": self.overall_reliability,
            "params_hash": self.params_hash,
        }
        if self.journal_payload:
            result["journal_payload"] = self.journal_payload
        return result


@dataclass
class CompoundBottleneck:
    """Per-compound weakest-link analysis."""
    compound_id: str
    weakest_endpoint: str
    weakest_desirability: float
    overall_desirability: float
    kind: str
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AttritionResult:
    """Gate-attrition bottleneck analysis."""
    gates: list[dict]
    dominant_gate: Optional[str]
    dominant_attrition: float
    total_input: int
    total_output: int
    overall_attrition: float

    def to_dict(self) -> dict:
        return asdict(self)
