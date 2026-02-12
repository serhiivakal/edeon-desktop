"""
Edeon Engine — Kleier Membrane Permeability and Accumulation Model (1988)
"""

import math
from typing import Tuple


def calculate_kleier_indices(log_kow: float, mw: float, pka: float = None) -> Tuple[float, float, float]:
    """Calculate membrane log permeability (log Pm), xylem index, and phloem index according to Kleier (1988).

    Returns:
        (log_pm, xylem_index, phloem_index)
    """
    # Kleier empirical permeability estimation: log Pm (m/s)
    # log Pm = -6.8 + 0.75 * log_kow - 0.004 * (mw - 200)
    mw_term = 0.004 * max(0.0, mw - 200.0)
    log_pm = -6.8 + 0.75 * log_kow - mw_term

    # Xylem index: peaks around logKow ~ 1.5-2.0 (optimal transpiration stream movement)
    # Gaussian bell curve centered at logKow = 1.8
    xylem_index = math.exp(-0.4 * ((log_kow - 1.8) ** 2))
    xylem_index = round(max(0.0, min(1.0, xylem_index)), 4)

    # Phloem index: permeability gate combined with optional weak acid trapping
    # Optimal phloem entry requires log Pm between -8.5 and -5.5
    pm_center = -7.0
    phloem_gate = math.exp(-0.5 * (((log_pm - pm_center) / 1.5) ** 2))

    if pka is not None and 3.0 <= pka <= 6.5:
        # Acidic boost for phloem trapping
        acid_boost = 1.0 + 1.5 * math.exp(-0.5 * (((pka - 4.5) / 1.0) ** 2))
        phloem_index = phloem_gate * acid_boost
    else:
        phloem_index = phloem_gate

    phloem_index = round(max(0.0, min(2.5, phloem_index)), 4)

    return (round(log_pm, 4), xylem_index, phloem_index)
