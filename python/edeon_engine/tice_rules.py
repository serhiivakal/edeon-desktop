"""
Edeon Engine — Pesticide-likeness (Tice Rules)

Applies Tice's rules for herbicide-likeness to scored compounds.
Based on: Tice, C.M. (2001) "Selecting the right compounds for screening."
Pest Manag Sci 57:3-16.

Herbicide property ranges:
  MW:             150 – 500
  LogP:           -1  – 8
  HBD:             0  – 3
  HBA:             1  – 12
  RotatableBonds:  0  – 12
  TPSA:           20  – 150

Scoring:
  "High" = all rules pass
  "Med"  = 1 violation
  "Low"  = 2+ violations
"""

# Tice rule boundaries for herbicides
TICE_RULES = [
    ("mol_weight",      150,  500,  "MW"),
    ("logp",            -1,   8,    "LogP"),
    ("hbd",             0,    3,    "HBD"),
    ("hba",             1,    12,   "HBA"),
    ("rotatable_bonds", 0,    12,   "RotBonds"),
    ("tpsa",            20,   150,  "TPSA"),
]


def check_tice_rules(compound: dict) -> dict:
    """Check a single compound against Tice's herbicide rules.

    Args:
        compound: dict with keys matching property names
                  (mol_weight, logp, tpsa, hbd, hba, rotatable_bonds)

    Returns:
        dict with:
            level: "High", "Med", or "Low"
            violations: list of violation descriptions
            rules_checked: number of rules that could be checked
    """
    violations = []
    rules_checked = 0

    for prop_key, low, high, label in TICE_RULES:
        value = compound.get(prop_key)
        if value is None:
            continue  # Skip properties that weren't computed

        rules_checked += 1

        if value < low:
            violations.append(f"{label} too low ({value} < {low})")
        elif value > high:
            violations.append(f"{label} too high ({value} > {high})")

    n_violations = len(violations)
    if n_violations == 0:
        level = "High"
    elif n_violations == 1:
        level = "Med"
    else:
        level = "Low"

    return {
        "level": level,
        "violations": violations,
        "rules_checked": rules_checked,
    }


def pesticide_likeness_batch(compounds: list[dict]) -> list[dict]:
    """Score a batch of compounds for pesticide-likeness.

    Each compound dict should have property values (mol_weight, logp, etc.).
    """
    return [check_tice_rules(c) for c in compounds]
