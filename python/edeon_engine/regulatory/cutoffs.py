"""
Edeon Engine — Regulatory Numeric Cut-off Evaluations

Applies published regulatory thresholds to predicted environmental fate
and ecotoxicity endpoints to determine:
  1. PBT / vPvB status (REACH Annex XIII)
  2. Groundwater leaching concern (EU Drinking Water Directive 0.1 µg/L trigger)
  3. CLP Aquatic Hazard Classification (H400/H410/H411/H412)
  4. Acute mammalian toxicity category (CLP / GHS)
  5. Persistence classification (EU 1107/2009 soil DT50 thresholds)

All cut-offs reference EU regulatory text (public domain) and are applied
as IN-SILICO SCREENING — not regulatory determinations.

References:
  - REACH Regulation (EC) No 1907/2006, Annex XIII (PBT/vPvB criteria)
  - Regulation (EC) No 1272/2008 (CLP) — Aquatic hazard + acute tox
  - EU Pesticides Regulation (EC) No 1107/2009 — persistence + mobility
  - EU Drinking Water Directive 98/83/EC — 0.1 µg/L threshold
  - Gustafson (1989) GUS leaching index thresholds
"""

from typing import Dict, Any, Optional, List


# ─────────────────────────────────────────────────────────────────────────────
# REACH ANNEX XIII — PBT / vPvB THRESHOLDS
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_pbt(
    dt50_soil: Optional[float],
    dt50_water: Optional[float],
    bcf: Optional[float],
    log_kow: Optional[float],
    fish_lc50_mg_l: Optional[float],
    daphnia_ec50_mg_l: Optional[float],
    algae_ec50_mg_l: Optional[float],
    mammal_noael_mg_kg_d: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Evaluate PBT/vPvB criteria per REACH Annex XIII.

    Thresholds:
      P:  DT50 soil > 120 d OR DT50 water > 40 d
      vP: DT50 soil > 180 d OR DT50 water > 60 d
      B:  BCF > 2000 L/kg (or log Kow > 4.5 as screening)
      vB: BCF > 5000 L/kg
      T:  Chronic NOEC < 0.01 mg/L (aquatic) OR CMR classification
          For screening: acute LC50 < 0.1 mg/L (conservative proxy)

    Returns dict with individual flags and overall verdict.
    """
    # Persistence
    is_p = False
    is_vp = False
    p_evidence = []

    if dt50_soil is not None:
        if dt50_soil > 180.0:
            is_vp = True
            is_p = True
            p_evidence.append(f"Soil DT50 = {dt50_soil:.0f} d > 180 d (vP)")
        elif dt50_soil > 120.0:
            is_p = True
            p_evidence.append(f"Soil DT50 = {dt50_soil:.0f} d > 120 d (P)")

    if dt50_water is not None:
        if dt50_water > 60.0:
            is_vp = True
            is_p = True
            p_evidence.append(f"Water DT50 = {dt50_water:.0f} d > 60 d (vP)")
        elif dt50_water > 40.0:
            is_p = True
            p_evidence.append(f"Water DT50 = {dt50_water:.0f} d > 40 d (P)")

    # Bioaccumulation
    is_b = False
    is_vb = False
    b_evidence = []

    if bcf is not None:
        if bcf > 5000.0:
            is_vb = True
            is_b = True
            b_evidence.append(f"BCF = {bcf:.0f} > 5000 (vB)")
        elif bcf > 2000.0:
            is_b = True
            b_evidence.append(f"BCF = {bcf:.0f} > 2000 (B)")

    if log_kow is not None and not is_b:
        if log_kow > 4.5:
            is_b = True
            b_evidence.append(f"Log Kow = {log_kow:.2f} > 4.5 (B screening)")

    # Toxicity (conservative acute screening proxy)
    is_t = False
    t_evidence = []

    if fish_lc50_mg_l is not None and fish_lc50_mg_l < 0.1:
        is_t = True
        t_evidence.append(f"Fish LC50 = {fish_lc50_mg_l:.4f} mg/L < 0.1 (T)")

    if daphnia_ec50_mg_l is not None and daphnia_ec50_mg_l < 0.1:
        is_t = True
        t_evidence.append(f"Daphnia EC50 = {daphnia_ec50_mg_l:.4f} mg/L < 0.1 (T)")

    if algae_ec50_mg_l is not None and algae_ec50_mg_l < 0.1:
        is_t = True
        t_evidence.append(f"Algae EC50 = {algae_ec50_mg_l:.4f} mg/L < 0.1 (T)")

    # Overall verdict
    if is_vp and is_vb:
        verdict = "vPvB"
        status = "likely_showstopper"
    elif is_p and is_b and is_t:
        verdict = "PBT"
        status = "likely_showstopper"
    elif (is_p and is_b) or (is_p and is_t) or (is_b and is_t):
        active = []
        if is_vp:
            active.append("vP")
        elif is_p:
            active.append("P")
        if is_vb:
            active.append("vB")
        elif is_b:
            active.append("B")
        if is_t:
            active.append("T")
        verdict = f"Concern ({'+'.join(active)})"
        status = "watch"
    elif is_p or is_b or is_t:
        active = []
        if is_p:
            active.append("P")
        if is_b:
            active.append("B")
        if is_t:
            active.append("T")
        verdict = f"Single flag: {'+'.join(active)}"
        status = "watch"
    else:
        verdict = "Not PBT/vPvB"
        status = "pass"

    return {
        "criterion": "PBT/vPvB (REACH Annex XIII)",
        "status": status,
        "verdict": verdict,
        "flags": {"p": is_p, "vp": is_vp, "b": is_b, "vb": is_vb, "t": is_t},
        "evidence": p_evidence + b_evidence + t_evidence,
        "source_ref": "Regulation (EC) No 1907/2006, Annex XIII",
    }


# ─────────────────────────────────────────────────────────────────────────────
# GROUNDWATER LEACHING CONCERN (EU DWD)
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_groundwater(
    gus_value: Optional[float],
    gus_class: Optional[str],
    koc: Optional[float],
    dt50_soil: Optional[float],
) -> Dict[str, Any]:
    """
    Evaluate groundwater contamination concern.

    Criteria:
      - GUS > 2.8 → leacher (likely to exceed EU 0.1 µg/L DWD limit)
      - GUS 1.8–2.8 → transitional
      - Koc < 75 + DT50 > 21 d → mobility + persistence combo flag
    """
    evidence = []
    status = "pass"

    if gus_value is not None:
        if gus_value > 2.8:
            status = "likely_showstopper"
            evidence.append(f"GUS = {gus_value:.2f} > 2.8 (leacher)")
        elif gus_value >= 1.8:
            status = "watch"
            evidence.append(f"GUS = {gus_value:.2f} in transition zone [1.8–2.8]")
        else:
            evidence.append(f"GUS = {gus_value:.2f} < 1.8 (non-leacher)")

    # Additional mobility + persistence combination
    if koc is not None and dt50_soil is not None:
        if koc < 75.0 and dt50_soil > 21.0:
            if status == "pass":
                status = "watch"
            evidence.append(
                f"Low Koc ({koc:.0f} < 75) + moderate persistence "
                f"(DT50 = {dt50_soil:.0f} d > 21 d) — mobility concern"
            )

    if gus_class is not None:
        evidence.append(f"GUS classification: {gus_class}")

    return {
        "criterion": "Groundwater concern (EU DWD 0.1 µg/L trigger)",
        "status": status,
        "evidence": evidence,
        "source_ref": "EU Drinking Water Directive 98/83/EC; EU 1107/2009 Annex II 3.7",
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLP AQUATIC HAZARD CLASSIFICATION (H400/H410/H411/H412)
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_aquatic_hazard(
    fish_lc50_mg_l: Optional[float],
    daphnia_ec50_mg_l: Optional[float],
    algae_ec50_mg_l: Optional[float],
    bcf: Optional[float],
    log_kow: Optional[float],
    is_rapidly_degradable: bool = False,
) -> Dict[str, Any]:
    """
    Classify CLP aquatic hazard (Regulation EC 1272/2008, Table 4.1.0).

    Acute (H400): Acute toxicity ≤ 1 mg/L (L(E)C50)
    Chronic Cat 1 (H410): Acute ≤ 1 mg/L + not rapidly degradable + BCF ≥ 500 (or log Kow ≥ 4)
    Chronic Cat 2 (H411): Acute ≤ 10 mg/L + not rapidly degradable + BCF ≥ 500
    Chronic Cat 3 (H412): Acute ≤ 100 mg/L + not rapidly degradable
    """
    evidence = []
    hazard_statements = []

    # Determine minimum acute endpoint
    acute_values = []
    if fish_lc50_mg_l is not None:
        acute_values.append(("Fish LC50", fish_lc50_mg_l))
    if daphnia_ec50_mg_l is not None:
        acute_values.append(("Daphnia EC50", daphnia_ec50_mg_l))
    if algae_ec50_mg_l is not None:
        acute_values.append(("Algae EC50", algae_ec50_mg_l))

    if not acute_values:
        return {
            "criterion": "Aquatic hazard (CLP H400/H410/H411/H412)",
            "status": "pass",
            "hazard_statements": [],
            "evidence": ["No aquatic endpoint data available"],
            "source_ref": "Regulation (EC) No 1272/2008, Table 4.1.0",
        }

    min_name, min_acute = min(acute_values, key=lambda x: x[1])
    evidence.append(f"Most sensitive endpoint: {min_name} = {min_acute:.4f} mg/L")

    # Bioaccumulation potential
    is_bioaccumulative = False
    if bcf is not None and bcf >= 500:
        is_bioaccumulative = True
        evidence.append(f"BCF = {bcf:.0f} ≥ 500 (bioaccumulative)")
    elif log_kow is not None and log_kow >= 4.0:
        is_bioaccumulative = True
        evidence.append(f"Log Kow = {log_kow:.2f} ≥ 4.0 (bioaccumulation screening)")

    if is_rapidly_degradable:
        evidence.append("Compound considered rapidly degradable")
    else:
        evidence.append("Not rapidly degradable (default assumption)")

    # Classification logic
    if min_acute <= 1.0:
        hazard_statements.append("H400 (Very toxic to aquatic life)")
        if not is_rapidly_degradable and is_bioaccumulative:
            hazard_statements.append("H410 (Chronic Cat 1 — very toxic with long-lasting effects)")
        elif not is_rapidly_degradable:
            hazard_statements.append("H411 (Chronic Cat 2 — toxic with long-lasting effects)")
    elif min_acute <= 10.0:
        if not is_rapidly_degradable and is_bioaccumulative:
            hazard_statements.append("H411 (Chronic Cat 2 — toxic with long-lasting effects)")
        elif not is_rapidly_degradable:
            hazard_statements.append("H412 (Chronic Cat 3 — harmful with long-lasting effects)")
    elif min_acute <= 100.0:
        if not is_rapidly_degradable:
            hazard_statements.append("H412 (Chronic Cat 3 — harmful with long-lasting effects)")

    # Determine overall status
    if "H400" in str(hazard_statements) or "H410" in str(hazard_statements):
        status = "likely_showstopper"
    elif "H411" in str(hazard_statements):
        status = "watch"
    elif hazard_statements:
        status = "watch"
    else:
        status = "pass"

    return {
        "criterion": "Aquatic hazard (CLP H400/H410/H411/H412)",
        "status": status,
        "hazard_statements": hazard_statements,
        "evidence": evidence,
        "source_ref": "Regulation (EC) No 1272/2008, Table 4.1.0",
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLP ACUTE MAMMALIAN TOXICITY CATEGORY
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_acute_mammalian(
    oral_ld50_mg_kg: Optional[float],
) -> Dict[str, Any]:
    """
    Classify CLP/GHS acute oral toxicity category.

    Category 1 (H300): LD50 ≤ 5 mg/kg — Fatal
    Category 2 (H300): LD50 5–50 mg/kg — Fatal
    Category 3 (H301): LD50 50–300 mg/kg — Toxic
    Category 4 (H302): LD50 300–2000 mg/kg — Harmful
    Category 5:         LD50 2000–5000 mg/kg — May be harmful
    Not classified:     LD50 > 5000 mg/kg
    """
    if oral_ld50_mg_kg is None:
        return {
            "criterion": "Acute mammalian toxicity (CLP oral)",
            "status": "pass",
            "category": None,
            "hazard_statement": None,
            "evidence": ["No oral LD50 prediction available"],
            "source_ref": "Regulation (EC) No 1272/2008, Table 3.1.1",
        }

    ld50 = oral_ld50_mg_kg
    evidence = [f"Predicted rat oral LD50 = {ld50:.0f} mg/kg"]

    if ld50 <= 5:
        category = 1
        h_statement = "H300 (Fatal if swallowed)"
        status = "likely_showstopper"
    elif ld50 <= 50:
        category = 2
        h_statement = "H300 (Fatal if swallowed)"
        status = "likely_showstopper"
    elif ld50 <= 300:
        category = 3
        h_statement = "H301 (Toxic if swallowed)"
        status = "watch"
    elif ld50 <= 2000:
        category = 4
        h_statement = "H302 (Harmful if swallowed)"
        status = "watch"
    elif ld50 <= 5000:
        category = 5
        h_statement = "May be harmful if swallowed"
        status = "pass"
    else:
        category = None
        h_statement = "Not classified (LD50 > 5000 mg/kg)"
        status = "pass"

    return {
        "criterion": "Acute mammalian toxicity (CLP oral)",
        "status": status,
        "category": category,
        "hazard_statement": h_statement,
        "evidence": evidence,
        "source_ref": "Regulation (EC) No 1272/2008, Table 3.1.1",
    }


# ─────────────────────────────────────────────────────────────────────────────
# SOIL PERSISTENCE (EU 1107/2009)
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_persistence(
    dt50_soil: Optional[float],
) -> Dict[str, Any]:
    """
    Evaluate soil persistence against EU 1107/2009 trigger values.

    Trigger: DT50 > 90 days (concern for accumulation)
    Cut-off: DT50 > 120 days (P flag)
    High concern: DT50 > 365 days (very persistent)
    """
    if dt50_soil is None:
        return {
            "criterion": "Soil persistence (EU 1107/2009)",
            "status": "pass",
            "evidence": ["No soil DT50 prediction available"],
            "source_ref": "Regulation (EC) No 1107/2009, Annex II, 3.7.1",
        }

    evidence = [f"Predicted soil DT50 = {dt50_soil:.0f} days"]

    if dt50_soil > 365:
        status = "likely_showstopper"
        evidence.append("DT50 > 365 d — very persistent, likely to accumulate")
    elif dt50_soil > 120:
        status = "likely_showstopper"
        evidence.append("DT50 > 120 d — exceeds persistence cut-off criterion")
    elif dt50_soil > 90:
        status = "watch"
        evidence.append("DT50 > 90 d — triggers further risk assessment")
    else:
        status = "pass"
        evidence.append("DT50 ≤ 90 d — below persistence trigger")

    return {
        "criterion": "Soil persistence (EU 1107/2009)",
        "status": status,
        "evidence": evidence,
        "source_ref": "Regulation (EC) No 1107/2009, Annex II, 3.7.1",
    }


# ─────────────────────────────────────────────────────────────────────────────
# COMBINED EVALUATION (used by scorecard)
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_regulatory_cutoffs(
    dt50_soil: Optional[float] = None,
    dt50_water: Optional[float] = None,
    koc: Optional[float] = None,
    bcf: Optional[float] = None,
    log_kow: Optional[float] = None,
    gus_value: Optional[float] = None,
    gus_class: Optional[str] = None,
    fish_lc50_mg_l: Optional[float] = None,
    daphnia_ec50_mg_l: Optional[float] = None,
    algae_ec50_mg_l: Optional[float] = None,
    oral_ld50_mg_kg: Optional[float] = None,
    is_rapidly_degradable: bool = False,
) -> List[Dict[str, Any]]:
    """
    Evaluate all numeric regulatory cut-offs and return a list of criterion results.
    Each result is a dict with: criterion, status, evidence, source_ref, and
    criterion-specific extra fields.
    """
    results = []

    # 1. PBT/vPvB
    results.append(evaluate_pbt(
        dt50_soil=dt50_soil,
        dt50_water=dt50_water,
        bcf=bcf,
        log_kow=log_kow,
        fish_lc50_mg_l=fish_lc50_mg_l,
        daphnia_ec50_mg_l=daphnia_ec50_mg_l,
        algae_ec50_mg_l=algae_ec50_mg_l,
    ))

    # 2. Groundwater
    results.append(evaluate_groundwater(
        gus_value=gus_value,
        gus_class=gus_class,
        koc=koc,
        dt50_soil=dt50_soil,
    ))

    # 3. Aquatic hazard
    results.append(evaluate_aquatic_hazard(
        fish_lc50_mg_l=fish_lc50_mg_l,
        daphnia_ec50_mg_l=daphnia_ec50_mg_l,
        algae_ec50_mg_l=algae_ec50_mg_l,
        bcf=bcf,
        log_kow=log_kow,
        is_rapidly_degradable=is_rapidly_degradable,
    ))

    # 4. Acute mammalian
    results.append(evaluate_acute_mammalian(
        oral_ld50_mg_kg=oral_ld50_mg_kg,
    ))

    # 5. Persistence
    results.append(evaluate_persistence(
        dt50_soil=dt50_soil,
    ))

    return results
