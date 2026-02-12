from dataclasses import dataclass
from typing import Any, Callable, Optional, Union

@dataclass
class Step:
    name: str                    # e.g., "environmental_fate"
    method: str                  # JSON-RPC method to call
    applies_to: str              # "parent" | "each_compound" | "each_tp"
    params: dict                 # may reference prior outputs via "$step.field"
    on_fail: str = "warn"        # "warn" | "abort" | "skip"
    gate: bool = False
    expensive: bool = False

@dataclass
class WorkflowSpec:
    id: str                      # "registration_readiness"
    name: str                    # "Registration Readiness Pre-Screen"
    persona: str                 # "Regulatory affairs / project lead"
    input_kind: str              # "single" | "series" | "library"
    default_params: dict         # UI renders these
    steps: list[Step]
    aggregator: Callable         # (step_outputs, params) -> WorkflowResult
    report_template: str         # printpdf template id

@dataclass
class Verdict:
    band: str                    # "GO" | "CONDITIONAL" | "NO_GO"
    driver: str                  # plain language reason
    confidence: str              # "high" | "moderate" | "low"
    rationale: str

@dataclass
class WorkflowResult:
    workflow_id: str
    per_compound: list[dict]     # list of compound dictionaries (envelope results)
    overall: Optional[Verdict]   # overall verdict
    sections: dict               # dossier structured blocks
    warnings: list[str]
    provenance: dict
