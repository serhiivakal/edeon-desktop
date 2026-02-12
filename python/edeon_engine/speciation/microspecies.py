"""
Edeon Engine — Microspecies Distributions & Henderson-Hasselbalch Calculations
"""

import math
from typing import List, Dict, Any
from rdkit import Chem


def calculate_fractional_populations(
    variants: List[Dict[str, Any]],
    ph_target: float,
    pka_values: List[float] = None
) -> List[Dict[str, Any]]:
    """Calculate fractional populations of microspecies at ph_target using Henderson-Hasselbalch or charge weights.

    Returns list of dicts:
        [
            {
                "smiles": str,
                "charge": int,
                "fraction_at_target": float,
                "dominant": bool
            }
        ]
    """
    if not variants:
        return []

    # If single variant, 100% population
    if len(variants) == 1:
        return [
            {
                "smiles": variants[0]["smiles"],
                "charge": variants[0]["charge"],
                "fraction_at_target": 1.0,
                "dominant": True,
            }
        ]

    # Calculate unnormalized weights at ph_target using pKa or charge differences
    weights = []
    if pka_values and len(pka_values) > 0:
        # Henderson-Hasselbalch weighting:
        # For acids: ratio [A-]/[HA] = 10^(pH - pKa)
        pka = pka_values[0]
        for v in variants:
            chg = v.get("charge", 0)
            if chg < 0: # Acidic species
                w = 10 ** (ph_target - pka)
            elif chg > 0: # Basic species
                w = 10 ** (pka - ph_target)
            else: # Neutral
                w = 1.0
            weights.append(max(w, 1e-6))
    else:
        # Distance-based charge penalty fallback
        for v in variants:
            chg = v.get("charge", 0)
            if chg < 0:
                w = 1.0 / (1.0 + math.exp(4.5 - ph_target))
            elif chg > 0:
                w = 1.0 / (1.0 + math.exp(ph_target - 9.0))
            else:
                w = 1.0
            weights.append(max(w, 1e-4))

    total_w = sum(weights)
    fractions = [w / total_w for w in weights]

    max_idx = max(range(len(fractions)), key=lambda i: fractions[i])

    result = []
    for idx, v in enumerate(variants):
        result.append(
            {
                "smiles": v["smiles"],
                "charge": v["charge"],
                "fraction_at_target": round(fractions[idx], 4),
                "dominant": (idx == max_idx),
            }
        )

    return result
