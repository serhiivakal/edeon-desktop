"""
Edeon Engine — Synthesizability Feasibility & Tier Assignment
"""

from typing import Tuple, Dict, Any


def compute_feasibility(
    sa_score: float,
    solved: bool,
    leaves_in_stock_frac: float,
    n_steps: int = 1
) -> Tuple[float, str]:
    """Calculate composite feasibility_score in [0.0, 1.0] and tier ('green', 'amber', 'red').

    Formula:
    composite = 0.5 * sa_score + 0.3 * leaves_in_stock_frac + (0.2 if solved else 0.0) - 0.05 * max(0, n_steps - 3)
    """
    solved_bonus = 0.2 if solved else 0.0
    step_penalty = 0.05 * max(0, n_steps - 3)

    raw_score = 0.5 * sa_score + 0.3 * leaves_in_stock_frac + solved_bonus - step_penalty
    score = round(float(max(0.0, min(1.0, raw_score))), 2)

    if score >= 0.70:
        tier = "green"
    elif score >= 0.45:
        tier = "amber"
    else:
        tier = "red"

    return (score, tier)
