"""
Edeon Engine — Resistance Risk Analysis

Estimates resistance development risk for herbicide candidates based
on structural and physicochemical features.

Risk factors evaluated:
  - Target site diversity (proxy from structural complexity)
  - Metabolic stability (LogP, MW based)
  - Mode of action uniqueness (heuristic from fingerprint diversity)
  - HRAC/IRAC/FRAC classification (heuristic MoA group assignment)
  - Cross-resistance scoring

Risk levels:
  "Low"  — multiple MOA features, metabolically labile
  "Med"  — some resistance concern
  "High" — single-target, metabolically stable, high risk

NOTE: Heuristic model for demonstration. Real deployment would use
target-site binding data and known resistance mutation databases.
"""


# ── HRAC / IRAC / FRAC Classification ───────────────────────
# Heuristic assignment of mode-of-action groups based on property
# profiles. Real implementation would use SMARTS pattern matching
# against known pharmacophores.

def classify_moa_group(compound: dict) -> dict:
    """Classify probable mode-of-action group.

    Returns dict with:
        classification: "HRAC", "IRAC", or "FRAC"
        group: group letter/number
        group_name: descriptive name
        confidence: "high", "moderate", or "low"
    """
    mw = compound.get("mol_weight", 300) or 300
    logp = compound.get("logp", 2.0) or 2.0
    tpsa = compound.get("tpsa", 60) or 60
    hbd = compound.get("hbd", 1) or 1
    hba = compound.get("hba", 4) or 4

    # Property profile heuristics for MoA class assignment
    # Herbicide-like: moderate MW, balanced LogP
    if 200 <= mw <= 400 and 1.0 <= logp <= 4.5 and 40 <= tpsa <= 100:
        if logp <= 2.5 and hba >= 4:
            return {
                "classification": "HRAC",
                "group": "B",
                "group_name": "ALS inhibitors",
                "confidence": "moderate",
                "resistance_prevalence": "High — >160 resistant species globally",
            }
        elif logp >= 3.0 and tpsa <= 60:
            return {
                "classification": "HRAC",
                "group": "A",
                "group_name": "ACCase inhibitors",
                "confidence": "moderate",
                "resistance_prevalence": "High — common in grasses",
            }
        else:
            return {
                "classification": "HRAC",
                "group": "C1",
                "group_name": "Photosystem II inhibitors",
                "confidence": "moderate",
                "resistance_prevalence": "High — widespread in broadleaves",
            }

    # Insecticide-like: smaller, more lipophilic
    elif mw <= 350 and logp >= 2.0:
        if tpsa <= 50:
            return {
                "classification": "IRAC",
                "group": "3A",
                "group_name": "Pyrethroids (sodium channel modulators)",
                "confidence": "low",
                "resistance_prevalence": "High — kdr mutations common",
            }
        else:
            return {
                "classification": "IRAC",
                "group": "4A",
                "group_name": "Neonicotinoids (nAChR agonists)",
                "confidence": "low",
                "resistance_prevalence": "Moderate — metabolic resistance increasing",
            }

    # Fungicide-like: various
    elif mw >= 250 and hba >= 3:
        return {
            "classification": "FRAC",
            "group": "3",
            "group_name": "DMI fungicides (sterol biosynthesis)",
            "confidence": "low",
            "resistance_prevalence": "Moderate — CYP51 mutations",
        }

    # Default fallback
    return {
        "classification": "HRAC",
        "group": "Z",
        "group_name": "Unknown / novel MoA",
        "confidence": "low",
        "resistance_prevalence": "Unknown — potentially novel target",
    }


def assess_cross_resistance(moa: dict, compound: dict) -> dict:
    """Assess cross-resistance risk based on MoA classification.

    Returns dict with:
        level: "Low", "Med", "High"
        detail: explanation
        related_groups: list of groups with known cross-resistance
    """
    group = moa.get("group", "Z")
    classification = moa.get("classification", "HRAC")

    # Known high cross-resistance groups
    high_xr = {
        "HRAC": {"A", "B", "C1", "G"},
        "IRAC": {"3A", "1A"},
        "FRAC": {"3", "7", "11"},
    }

    med_xr = {
        "HRAC": {"C2", "D", "E", "K1"},
        "IRAC": {"4A", "28"},
        "FRAC": {"3", "9"},
    }

    if group in high_xr.get(classification, set()):
        return {
            "level": "High",
            "detail": f"Group {group} ({classification}) has extensive documented cross-resistance",
            "related_groups": list(high_xr.get(classification, set()) - {group}),
        }
    elif group in med_xr.get(classification, set()):
        return {
            "level": "Med",
            "detail": f"Group {group} ({classification}) has moderate cross-resistance risk",
            "related_groups": list(med_xr.get(classification, set()) - {group}),
        }
    else:
        return {
            "level": "Low",
            "detail": f"Group {group} ({classification}) — limited cross-resistance data",
            "related_groups": [],
        }


def assess_resistance(compound: dict) -> dict:
    """Assess resistance development risk for a single compound.

    Args:
        compound: dict with mol_weight, logp, tpsa, hbd, hba, rotatable_bonds

    Returns:
        dict with:
            level: "Low", "Med", or "High"
            risk_score: 0-10 (higher = more resistance risk)
            factors: list of risk factor assessments
    """
    mw = compound.get("mol_weight", 300) or 300
    logp = compound.get("logp", 2.0) or 2.0
    tpsa = compound.get("tpsa", 60) or 60
    hbd = compound.get("hbd", 1) or 1
    hba = compound.get("hba", 4) or 4
    rot = compound.get("rotatable_bonds", 3) or 3

    risk_score = 5.0  # Base risk
    factors = []

    # MoA classification and cross-resistance
    moa = classify_moa_group(compound)
    xr = assess_cross_resistance(moa, compound)

    # Adjust base risk from cross-resistance prevalence
    if xr["level"] == "High":
        risk_score += 1.0
    elif xr["level"] == "Med":
        risk_score += 0.5

    factors.append({
        "factor": "MoA classification",
        "assessment": f"{moa['classification']} Group {moa['group']}",
        "detail": moa["group_name"],
    })

    # 1. Metabolic stability (high LogP, low TPSA = more stable = more resistance risk)
    if logp > 4.0:
        risk_score += 1.5
        factors.append({
            "factor": "Metabolic stability",
            "assessment": "High",
            "detail": f"LogP {logp:.1f} suggests slow metabolism"
        })
    elif logp > 2.5:
        risk_score += 0.5
        factors.append({
            "factor": "Metabolic stability",
            "assessment": "Moderate",
            "detail": f"LogP {logp:.1f} — moderate metabolic rate"
        })
    else:
        risk_score -= 1.0
        factors.append({
            "factor": "Metabolic stability",
            "assessment": "Low",
            "detail": f"LogP {logp:.1f} — rapid metabolism expected"
        })

    # 2. Structural complexity (proxy for multi-target potential)
    complexity = (hbd + hba + rot) / 3.0
    if complexity > 5:
        risk_score -= 1.5
        factors.append({
            "factor": "Target diversity",
            "assessment": "Multi-target likely",
            "detail": "High structural complexity reduces single-target resistance"
        })
    elif complexity > 3:
        risk_score -= 0.5
        factors.append({
            "factor": "Target diversity",
            "assessment": "Moderate",
            "detail": "Some multi-target potential"
        })
    else:
        risk_score += 1.0
        factors.append({
            "factor": "Target diversity",
            "assessment": "Single-target likely",
            "detail": "Simple structure suggests single binding site"
        })

    # 3. Cross-resistance potential (TPSA proxy)
    if tpsa < 40:
        risk_score += 1.0
        factors.append({
            "factor": "Cross-resistance",
            "assessment": "High",
            "detail": f"Low TPSA ({tpsa:.0f}) — similar to known resistance-prone classes"
        })
    elif tpsa > 100:
        risk_score -= 0.5
        factors.append({
            "factor": "Cross-resistance",
            "assessment": "Low",
            "detail": f"High TPSA ({tpsa:.0f}) — distinct pharmacophore"
        })
    else:
        factors.append({
            "factor": "Cross-resistance",
            "assessment": "Moderate",
            "detail": f"TPSA {tpsa:.0f} — standard range"
        })

    # 4. MW influence on resistance evolution
    if mw < 250:
        risk_score += 0.5
        factors.append({
            "factor": "Size effect",
            "assessment": "Small molecule",
            "detail": "Small molecules more prone to efflux pump resistance"
        })
    elif mw > 400:
        risk_score -= 0.5
        factors.append({
            "factor": "Size effect",
            "assessment": "Large molecule",
            "detail": "Larger compounds less affected by common efflux mechanisms"
        })

    risk_score = max(0, min(10, risk_score))

    if risk_score <= 3.5:
        level = "Low"
    elif risk_score <= 6.5:
        level = "Med"
    else:
        level = "High"

    return {
        "level": level,
        "risk_score": round(risk_score, 1),
        "factors": factors,
        "moa_classification": moa,
        "cross_resistance": xr,
    }


def resistance_batch(compounds: list[dict]) -> list[dict]:
    """Assess resistance risk for a batch of compounds."""
    return [assess_resistance(c) for c in compounds]

