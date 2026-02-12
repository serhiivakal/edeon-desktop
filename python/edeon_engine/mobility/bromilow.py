"""
Edeon Engine — Bromilow Weak-Acid Phloem Ion-Trapping Model (1990)
"""

import math
from typing import Optional, List


def calculate_bromilow_cf(
    pka_values: Optional[List[float]],
    ph_apoplast: float = 5.5,
    ph_phloem: float = 8.0,
) -> float:
    """Calculate the Bromilow phloem concentration factor (CF) based on Henderson-Hasselbalch ion trapping.

    CF = (1 + 10^(ph_phloem - pKa)) / (1 + 10^(ph_apoplast - pKa))

    Returns:
        float Concentration Factor >= 1.0
    """
    if not pka_values:
        return 1.0

    # Select the primary acidic pKa (lowest pKa in range 2.0 to 9.0)
    acidic_pkas = [p for p in pka_values if 2.0 <= p <= 9.0]
    if not acidic_pkas:
        return 1.0

    primary_pka = min(acidic_pkas)

    # Henderson-Hasselbalch ratio:
    num = 1.0 + 10.0 ** max(-5.0, min(8.0, ph_phloem - primary_pka))
    den = 1.0 + 10.0 ** max(-5.0, min(8.0, ph_apoplast - primary_pka))

    cf = num / den
    return round(float(max(1.0, min(500.0, cf))), 2)
