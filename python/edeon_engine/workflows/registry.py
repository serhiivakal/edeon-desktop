from .contracts import WorkflowSpec
from .w1_registration import W1_SPEC
from .w2_pollinator import W2_SPEC
from .w3_tp_liability import W3_SPEC
from .w4_lead_opt import W4_SPEC
from .w5_triage import W5_SPEC
from .w6_benchmarking import W6_SPEC
from .w7_selectivity_window import W7_SPEC
from .w8_scaffold_hop import W8_SPEC

REGISTRY = {
    W1_SPEC.id: W1_SPEC,
    W2_SPEC.id: W2_SPEC,
    W3_SPEC.id: W3_SPEC,
    W4_SPEC.id: W4_SPEC,
    W5_SPEC.id: W5_SPEC,
    W6_SPEC.id: W6_SPEC,
    W7_SPEC.id: W7_SPEC,
    W8_SPEC.id: W8_SPEC
}


def list_workflows() -> list[dict]:
    """Discover available pre-made workflows for the UI gallery."""
    return [
        {
            "id": spec.id,
            "name": spec.name,
            "persona": spec.persona,
            "input_kind": spec.input_kind,
            "default_params": spec.default_params,
            "step_names": [step.name for step in spec.steps]
        }
        for spec in REGISTRY.values()
    ]
