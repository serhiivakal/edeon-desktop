"""
Edeon Bottleneck Analyzer — Gate-Attrition Bottleneck

Identifies the workflow gate that causes the highest compound attrition.
Uses per-gate pass/fail counts from WorkflowResult data to locate the
"hardest" gate — the one where the most leads are lost.

Extends the existing AttritionWaterfall UI with a dominant-gate callout.
"""


def compute_gate_attrition(
    gate_results: list[dict],
) -> dict:
    """Compute attrition statistics for each gate in a workflow.

    Args:
        gate_results: list of dicts with:
            - gate_name: str
            - n_input: int (compounds entering gate)
            - n_passed: int (compounds passing gate)

    Returns:
        {
            "gates": [
                {
                    "gate_name": str,
                    "n_input": int,
                    "n_passed": int,
                    "n_failed": int,
                    "attrition_rate": float (0-1),
                    "cumulative_survival": float (0-1)
                }
            ],
            "dominant_gate": str | None,
            "dominant_attrition": float,
            "total_input": int,
            "total_output": int,
            "overall_attrition": float,
        }
    """
    if not gate_results:
        return {
            "gates": [],
            "dominant_gate": None,
            "dominant_attrition": 0.0,
            "total_input": 0,
            "total_output": 0,
            "overall_attrition": 0.0,
        }

    processed = []
    total_input = gate_results[0].get("n_input", 0) if gate_results else 0
    cumulative_survival = 1.0

    for g in gate_results:
        n_in = g.get("n_input", 0)
        n_pass = g.get("n_passed", 0)
        n_fail = n_in - n_pass

        attrition_rate = n_fail / n_in if n_in > 0 else 0.0
        cumulative_survival *= (1.0 - attrition_rate) if n_in > 0 else 1.0

        processed.append({
            "gate_name": g.get("gate_name", ""),
            "n_input": n_in,
            "n_passed": n_pass,
            "n_failed": n_fail,
            "attrition_rate": round(attrition_rate, 4),
            "cumulative_survival": round(cumulative_survival, 4),
        })

    # Find dominant gate (highest absolute attrition)
    dominant = max(processed, key=lambda x: x["n_failed"])
    total_output = processed[-1]["n_passed"] if processed else 0

    overall_attrition = 1.0 - (total_output / total_input) if total_input > 0 else 0.0

    return {
        "gates": processed,
        "dominant_gate": dominant["gate_name"],
        "dominant_attrition": dominant["attrition_rate"],
        "total_input": total_input,
        "total_output": total_output,
        "overall_attrition": round(overall_attrition, 4),
    }
