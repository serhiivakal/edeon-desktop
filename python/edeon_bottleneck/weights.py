"""
Edeon Bottleneck Analyzer — Objective Weight Suggestions

Given a leverage profile (ranked endpoints with leverage values and
classifications), suggest K10-style objective weights that would
focus BO acquisition on the most impactful chemical bottlenecks.

The weight vector is a starting point: users can adjust via the K10 UI.
"""


def suggest_weights(
    leverage_results: list[dict],
    n_top: int = 5,
    base_weight: float = 0.1,
) -> dict:
    """Suggest objective weights seeded from the leverage profile.

    Chemical bottlenecks → high weight (proportional to leverage).
    Epistemic bottlenecks → lower weight (improvement via measurement, not design).
    Distractors → near-zero weight.

    Args:
        leverage_results: list of dicts with:
            - endpoint: str
            - leverage: float
            - kind: "chemical" | "epistemic" | "distractor"
        n_top: how many top endpoints to weight significantly
        base_weight: minimum weight for any endpoint

    Returns:
        {"weights": {endpoint: weight}, "rationale": str}
    """
    if not leverage_results:
        return {"weights": {}, "rationale": "No leverage data available"}

    weights = {}

    # Sort by leverage descending
    sorted_results = sorted(leverage_results, key=lambda x: x.get("leverage", 0), reverse=True)

    max_leverage = sorted_results[0].get("leverage", 1.0) if sorted_results else 1.0
    if max_leverage <= 0:
        max_leverage = 1.0

    chemical_bottlenecks = []

    for i, item in enumerate(sorted_results):
        ep = item.get("endpoint", "")
        leverage = item.get("leverage", 0.0)
        kind = item.get("kind", "chemical")

        if kind == "distractor":
            weights[ep] = base_weight * 0.1
        elif kind == "epistemic":
            # Some weight, but less than chemical
            weights[ep] = base_weight + 0.3 * (leverage / max_leverage) if leverage > 0 else base_weight
        else:
            # Chemical: proportional to leverage, with top-N boost
            if i < n_top:
                weights[ep] = base_weight + 0.9 * (leverage / max_leverage)
                chemical_bottlenecks.append(ep)
            else:
                weights[ep] = base_weight + 0.5 * (leverage / max_leverage)

    # Normalize to sum to 1.0
    total = sum(weights.values())
    if total > 0:
        weights = {k: round(v / total, 4) for k, v in weights.items()}

    if chemical_bottlenecks:
        rationale = f"Weights focus on top chemical bottleneck(s): {', '.join(chemical_bottlenecks[:3])}"
    else:
        rationale = "No chemical bottlenecks identified; weights distributed evenly"

    return {
        "weights": weights,
        "rationale": rationale,
    }
