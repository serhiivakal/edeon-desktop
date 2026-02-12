"""
Edeon Engine — Toxicity Prediction

Estimates acute toxicity for key non-target organisms using
property-based heuristic QSAR models. Predictions include:
  - Honeybee (Apis mellifera) — contact LD50 category
  - Fish (Oncorhynchus mykiss / Danio rerio) — 96h LC50 category
  - Bird (Colinus virginianus) — oral LD50 category
  - Mammal (Rattus norvegicus) — oral LD50 category

Risk levels correspond to EPA ecotox thresholds:
  "Low"  — practically non-toxic / slight toxicity
  "Med"  — moderately toxic
  "High" — highly toxic / very highly toxic

Each prediction includes:
  - Confidence score (0.0–1.0) from applicability domain check
  - Estimated toxicity category with regulatory threshold comparison
  - Applicability domain flag (in_domain / borderline / out_of_domain)

NOTE: These are heuristic models for demonstration. Production
deployment would use validated QSAR/QSPR models trained on
curated experimental datasets (e.g., EPA ECOTOX, PPDB).
"""

import math


# ── Applicability Domain ─────────────────────────────────────
# Property ranges of the "training set" (typical agrochemicals)

AD_BOUNDS = {
    "mol_weight": (100, 600),
    "logp": (-2.0, 8.0),
    "tpsa": (0, 200),
    "hbd": (0, 6),
    "hba": (0, 14),
    "rotatable_bonds": (0, 15),
}


def _check_applicability_domain(props: dict) -> dict:
    """Check if the compound falls within the applicability domain.

    Returns:
        dict with:
            status: "in_domain", "borderline", or "out_of_domain"
            confidence: 0.0–1.0
            warnings: list of out-of-range properties
    """
    warnings = []
    penalties = 0.0

    for prop_key, (low, high) in AD_BOUNDS.items():
        value = props.get(prop_key)
        if value is None:
            penalties += 0.1
            warnings.append(f"{prop_key}: missing value")
            continue

        span = high - low
        if value < low:
            frac_out = (low - value) / span
            penalties += min(0.5, frac_out)
            warnings.append(f"{prop_key}: {value} below range [{low}–{high}]")
        elif value > high:
            frac_out = (value - high) / span
            penalties += min(0.5, frac_out)
            warnings.append(f"{prop_key}: {value} above range [{low}–{high}]")

    confidence = max(0.0, 1.0 - penalties)

    if confidence >= 0.7:
        status = "in_domain"
    elif confidence >= 0.4:
        status = "borderline"
    else:
        status = "out_of_domain"

    return {
        "status": status,
        "confidence": round(confidence, 2),
        "warnings": warnings,
    }


# ── EPA Ecotoxicity Regulatory Thresholds ────────────────────
# Reference: EPA Technical Overview of Ecological Risk Assessment

EPA_THRESHOLDS = {
    "bee": {
        "High": "Contact LD50 < 2 µg/bee",
        "Med": "Contact LD50 2–11 µg/bee",
        "Low": "Contact LD50 > 11 µg/bee",
    },
    "fish": {
        "High": "96h LC50 < 0.1 mg/L",
        "Med": "96h LC50 0.1–10 mg/L",
        "Low": "96h LC50 > 10 mg/L",
    },
    "bird": {
        "High": "Oral LD50 < 50 mg/kg",
        "Med": "Oral LD50 50–500 mg/kg",
        "Low": "Oral LD50 > 500 mg/kg",
    },
    "mammal": {
        "High": "Oral LD50 < 50 mg/kg",
        "Med": "Oral LD50 50–500 mg/kg",
        "Low": "Oral LD50 > 500 mg/kg",
    },
}


def _predict_bee_toxicity(props: dict) -> dict:
    """Predict honeybee toxicity category."""
    logp = props.get("logp", 2.0) or 2.0
    mw = props.get("mol_weight", 300) or 300
    hbd = props.get("hbd", 1) or 1
    tpsa = props.get("tpsa", 60) or 60

    # Heuristic model: lipophilic + small = more bee-toxic
    risk_score = 5.0
    risk_score += logp * 0.8       # Lipophilicity increases bee uptake
    risk_score -= (mw - 200) * 0.008  # Higher MW = less bioavailable
    risk_score -= hbd * 0.4        # HBD reduces membrane permeation
    risk_score -= (tpsa - 40) * 0.02  # Higher polarity = less uptake

    risk_score = max(0, min(10, risk_score))

    if risk_score >= 7:
        level = "High"
        detail = "High contact/oral toxicity predicted"
    elif risk_score >= 4:
        level = "Med"
        detail = "Moderate bee toxicity expected"
    else:
        level = "Low"
        detail = "Low bee toxicity predicted"

    return {
        "organism": "Honeybee",
        "organism_latin": "Apis mellifera",
        "level": level,
        "risk_score": round(risk_score, 1),
        "detail": detail,
        "threshold": EPA_THRESHOLDS["bee"][level],
    }


def _predict_fish_toxicity(props: dict) -> dict:
    """Predict acute fish toxicity (96h LC50 category)."""
    logp = props.get("logp", 2.0) or 2.0
    mw = props.get("mol_weight", 300) or 300
    tpsa = props.get("tpsa", 60) or 60

    # Narcosis baseline: high LogP = bioconcentration = high fish tox
    risk_score = 3.0
    risk_score += logp * 1.2       # Strong driver via bioconcentration
    risk_score -= (mw - 300) * 0.005  # Very large MW less bioavailable
    risk_score -= (tpsa - 40) * 0.015  # More polar = less absorbed through gills

    risk_score = max(0, min(10, risk_score))

    if risk_score >= 7:
        level = "High"
        detail = "High acute aquatic toxicity predicted"
    elif risk_score >= 4:
        level = "Med"
        detail = "Moderate fish toxicity expected"
    else:
        level = "Low"
        detail = "Low fish toxicity predicted"

    return {
        "organism": "Fish",
        "organism_latin": "Oncorhynchus mykiss",
        "level": level,
        "risk_score": round(risk_score, 1),
        "detail": detail,
        "threshold": EPA_THRESHOLDS["fish"][level],
    }


def _predict_bird_toxicity(props: dict) -> dict:
    """Predict avian toxicity (oral LD50 category)."""
    logp = props.get("logp", 2.0) or 2.0
    mw = props.get("mol_weight", 300) or 300
    hba = props.get("hba", 4) or 4

    # Birds: less susceptible overall, but lipophilic compounds persist
    risk_score = 2.5
    risk_score += logp * 0.6
    risk_score -= hba * 0.2        # Polar acceptors reduce oral absorption
    risk_score -= (mw - 250) * 0.004

    risk_score = max(0, min(10, risk_score))

    if risk_score >= 7:
        level = "High"
        detail = "High avian toxicity predicted"
    elif risk_score >= 4:
        level = "Med"
        detail = "Moderate avian toxicity expected"
    else:
        level = "Low"
        detail = "Low avian toxicity predicted"

    return {
        "organism": "Bird",
        "organism_latin": "Colinus virginianus",
        "level": level,
        "risk_score": round(risk_score, 1),
        "detail": detail,
        "threshold": EPA_THRESHOLDS["bird"][level],
    }


def _predict_mammal_toxicity(props: dict) -> dict:
    """Predict mammalian toxicity (rat oral LD50 category)."""
    logp = props.get("logp", 2.0) or 2.0
    mw = props.get("mol_weight", 300) or 300
    tpsa = props.get("tpsa", 60) or 60
    hbd = props.get("hbd", 1) or 1
    hba = props.get("hba", 4) or 4
    rot = props.get("rotatable_bonds", 3) or 3

    # Mammalian oral toxicity: driven by oral bioavailability
    risk_score = 3.0

    # Optimal oral absorption (Lipinski-like): increases toxicity risk
    if 1.0 <= logp <= 4.0:
        risk_score += 1.5
    elif logp > 4.0:
        risk_score += 0.5  # Very lipophilic may have poor solubility
    else:
        risk_score -= 0.5

    if mw <= 500:
        risk_score += 0.5
    else:
        risk_score -= 1.0  # Poor oral absorption

    if tpsa <= 140:
        risk_score += 0.5
    else:
        risk_score -= 0.5

    if hbd <= 5 and hba <= 10:
        risk_score += 0.5  # Good intestinal absorption

    risk_score = max(0, min(10, risk_score))

    if risk_score >= 7:
        level = "High"
        detail = "High mammalian toxicity predicted"
    elif risk_score >= 4:
        level = "Med"
        detail = "Moderate mammalian toxicity expected"
    else:
        level = "Low"
        detail = "Low mammalian toxicity predicted"

    return {
        "organism": "Mammal",
        "organism_latin": "Rattus norvegicus",
        "level": level,
        "risk_score": round(risk_score, 1),
        "detail": detail,
        "threshold": EPA_THRESHOLDS["mammal"][level],
    }


def predict_toxicity(compound: dict) -> dict:
    """Predict toxicity profile for a single compound.

    Args:
        compound: dict with mol_weight, logp, tpsa, hbd, hba, rotatable_bonds

    Returns:
        dict with:
            predictions: list of per-organism toxicity dicts
            overall_level: "Low", "Med", or "High" (worst case)
            applicability_domain: AD check result
    """
    predictions = [
        _predict_bee_toxicity(compound),
        _predict_fish_toxicity(compound),
        _predict_bird_toxicity(compound),
        _predict_mammal_toxicity(compound),
    ]

    ad = _check_applicability_domain(compound)

    high_count = sum(1 for p in predictions if p["level"] == "High")
    med_count = sum(1 for p in predictions if p["level"] == "Med")

    if high_count > 0:
        overall_level = "High"
    elif med_count >= 2:
        overall_level = "Med"
    else:
        overall_level = "Low"

    return {
        "predictions": predictions,
        "overall_level": overall_level,
        "applicability_domain": ad,
    }


def toxicity_batch(compounds: list[dict]) -> list[dict]:
    """Predict toxicity for a batch of compounds."""
    return [predict_toxicity(c) for c in compounds]
