"""
Edeon Engine — Registration Risk Scorecard

Assembles the full registration-risk scorecard for a single compound by:
  1. Running structural alert screening (genotoxicity, ED, skin sensitization)
  2. Predicting environmental fate endpoints via the existing fate module
  3. Predicting ecotoxicity endpoints via the model registry
  4. Evaluating all numeric regulatory cut-offs
  5. Combining everything into a per-criterion verdict with overall risk.

The scorecard output is the basis for:
  - The UI traffic-light scorecard component
  - The Registration Risk Dossier PDF export
  - The "Reg Risk" badge column in ResultsTable

IMPORTANT: This is an IN-SILICO SCREENING tool. All outputs are triage
signals, NOT regulatory determinations. Every surface rendering these
results must include a disclaimer to that effect.
"""

import math
from typing import Dict, Any, List, Optional

from .alerts import screen_structural_alerts
from .cutoffs import evaluate_regulatory_cutoffs

# Attempt to import fate and model prediction machinery
try:
    from edeon_engine.fate.parent_fate import predict_compound_fate
    HAS_FATE = True
except ImportError:
    HAS_FATE = False

try:
    from edeon_models import Endpoint
    from edeon_models.ipc.commands import REGISTRY
    HAS_MODELS = True
except ImportError:
    HAS_MODELS = False


def _safe_get_prediction_value(endpoint: "Endpoint", smiles: str) -> Optional[float]:
    """Safely retrieve a numeric prediction value from the model registry."""
    if not HAS_MODELS:
        return None
    try:
        backend = REGISTRY.get(endpoint)
        pred = backend.predict([smiles])[0]
        val = pred.value.numeric
        if val is None or math.isnan(val) or val <= 0:
            return None
        return float(val)
    except Exception:
        return None


def _extract_fate_values(fate_result: dict) -> dict:
    """Extract numeric values from fate prediction result for cutoff evaluation."""
    values = {}

    # DT50 soil
    dt50 = fate_result.get("dt50_soil", {})
    if isinstance(dt50, dict) and dt50.get("value") is not None:
        values["dt50_soil"] = dt50["value"]

    # Koc
    koc = fate_result.get("koc", {})
    if isinstance(koc, dict) and koc.get("value") is not None:
        values["koc"] = koc["value"]

    # BCF
    bcf = fate_result.get("bcf", {})
    if isinstance(bcf, dict) and bcf.get("value") is not None:
        values["bcf"] = bcf["value"]

    # Log Kow
    log_kow = fate_result.get("log_kow", {})
    if isinstance(log_kow, dict) and log_kow.get("value") is not None:
        values["log_kow"] = log_kow["value"]

    # GUS
    gus = fate_result.get("gus", {})
    if isinstance(gus, dict):
        if gus.get("value") is not None:
            values["gus_value"] = gus["value"]
        if gus.get("class") is not None:
            values["gus_class"] = gus["class"]

    return values


def assess_registration_risk(
    smiles: str,
    use_predicted_fate: bool = True,
    fate_data: Optional[dict] = None,
    selectivity_data: Optional[dict] = None,
) -> Dict[str, Any]:
    """
    Full registration-risk assessment for a single compound.

    Args:
        smiles: SMILES string of the query compound.
        use_predicted_fate: If True, run fate predictions (DT50, Koc, BCF, etc.)
                           to feed the regulatory cut-off evaluations.
        fate_data: Optional pre-computed fate data (from fateStore). If provided,
                   skips re-running fate predictions.
        selectivity_data: Optional pre-computed selectivity data. If provided,
                         can extract ecotox values for aquatic hazard evaluation.

    Returns:
        {
            "smiles": str,
            "criteria": [
                {
                    "criterion": str,
                    "status": "pass" | "watch" | "likely_showstopper",
                    "evidence": [str, ...],
                    "source_ref": str,
                    ... (criterion-specific fields)
                }, ...
            ],
            "structural_alerts": { ... screen_structural_alerts output ... },
            "overall": {
                "risk": "low" | "medium" | "high" | "showstopper",
                "showstopper_count": int,
                "watch_count": int,
                "pass_count": int,
            },
            "disclaimer": str,
        }
    """
    if not smiles or not isinstance(smiles, str):
        return {
            "smiles": smiles or "",
            "criteria": [
                {
                    "criterion": "Invalid SMILES / Standardization Failure",
                    "status": "watch",
                    "evidence": ["The compound SMILES is invalid or None."],
                    "source_ref": "System validation"
                }
            ],
            "structural_alerts": {
                "alerts_fired": [],
                "alert_summary": {"genotoxicity": 0, "endocrine_disruption": 0, "skin_sensitization": 0}
            },
            "overall": {
                "risk": "low",
                "showstopper_count": 0,
                "watch_count": 1,
                "pass_count": 0,
            },
            "disclaimer": "Invalid compound — cannot assess registration risk."
        }

    # ── 1. Structural Alert Screening ──────────────────────────────────────
    alerts_result = screen_structural_alerts(smiles)

    # Convert alert summary to a criterion-style result
    alert_criteria = []

    # Genotoxicity alerts as a criterion
    genotox_alerts = [a for a in alerts_result["alerts_fired"] if a["category"] == "genotoxicity"]
    if genotox_alerts:
        high_count = sum(1 for a in genotox_alerts if a["severity"] == "high")
        if high_count > 0:
            genotox_status = "likely_showstopper"
        else:
            genotox_status = "watch"
        genotox_evidence = [f"{a['name']} ({a['severity']}): {a['mechanism']}" for a in genotox_alerts]
    else:
        genotox_status = "pass"
        genotox_evidence = ["No genotoxicity structural alerts detected"]

    alert_criteria.append({
        "criterion": "Genotoxicity / Mutagenicity alerts (Benigni-Bossa)",
        "status": genotox_status,
        "evidence": genotox_evidence,
        "source_ref": "Benigni & Bossa (2008) Chem Rev; OECD QSAR Toolbox profilers",
    })

    # Endocrine disruption alerts
    ed_alerts = [a for a in alerts_result["alerts_fired"] if a["category"] == "endocrine_disruption"]
    if ed_alerts:
        high_ed = sum(1 for a in ed_alerts if a["severity"] == "high")
        if high_ed > 0:
            ed_status = "likely_showstopper"
        else:
            ed_status = "watch"
        ed_evidence = [f"{a['name']} ({a['severity']}): {a['mechanism']}" for a in ed_alerts]
    else:
        ed_status = "pass"
        ed_evidence = ["No endocrine disruption structural alerts detected"]

    alert_criteria.append({
        "criterion": "Endocrine disruption screening (structural)",
        "status": ed_status,
        "evidence": ed_evidence,
        "source_ref": "OECD/JRC ED profilers; EFSA ED guidance",
    })

    # Skin sensitization alerts
    skin_alerts = [a for a in alerts_result["alerts_fired"] if a["category"] == "skin_sensitization"]
    if skin_alerts:
        high_skin = sum(1 for a in skin_alerts if a["severity"] == "high")
        skin_status = "likely_showstopper" if high_skin > 0 else "watch"
        skin_evidence = [f"{a['name']} ({a['severity']}): {a['mechanism']}" for a in skin_alerts]
    else:
        skin_status = "pass"
        skin_evidence = ["No skin sensitization alerts detected"]

    alert_criteria.append({
        "criterion": "Skin sensitization alerts (protein reactivity)",
        "status": skin_status,
        "evidence": skin_evidence,
        "source_ref": "OECD QSAR Toolbox protein binding profiler",
    })

    # ── 2. Environmental Fate + Ecotox Predictions ─────────────────────────
    fate_values = {}

    if fate_data is not None:
        # Use pre-computed fate data
        fate_values = _extract_fate_values(fate_data)
    elif use_predicted_fate and HAS_FATE:
        try:
            fate_result = predict_compound_fate(smiles)
            fate_values = _extract_fate_values(fate_result)
        except Exception:
            pass

    # Attempt to get aquatic ecotox endpoints for CLP classification
    fish_lc50 = None
    daphnia_ec50 = None
    oral_ld50 = None

    if HAS_MODELS:
        fish_lc50 = _safe_get_prediction_value(Endpoint.FISH_ACUTE_LC50, smiles)
        daphnia_ec50 = _safe_get_prediction_value(Endpoint.DAPHNIA_ACUTE_EC50, smiles)
        oral_ld50 = _safe_get_prediction_value(Endpoint.RAT_ACUTE_ORAL_LD50, smiles)

    # ── 3. Numeric Cut-off Evaluations ─────────────────────────────────────
    cutoff_criteria = evaluate_regulatory_cutoffs(
        dt50_soil=fate_values.get("dt50_soil"),
        dt50_water=None,  # Not predicted in current fate module
        koc=fate_values.get("koc"),
        bcf=fate_values.get("bcf"),
        log_kow=fate_values.get("log_kow"),
        gus_value=fate_values.get("gus_value"),
        gus_class=fate_values.get("gus_class"),
        fish_lc50_mg_l=fish_lc50,
        daphnia_ec50_mg_l=daphnia_ec50,
        algae_ec50_mg_l=None,
        oral_ld50_mg_kg=oral_ld50,
        is_rapidly_degradable=False,
    )

    # ── 4. Assemble Full Criteria List ─────────────────────────────────────
    all_criteria = alert_criteria + cutoff_criteria

    # ── 5. Compute Overall Risk ────────────────────────────────────────────
    showstopper_count = sum(1 for c in all_criteria if c["status"] == "likely_showstopper")
    watch_count = sum(1 for c in all_criteria if c["status"] == "watch")
    pass_count = sum(1 for c in all_criteria if c["status"] == "pass")

    if showstopper_count >= 2:
        overall_risk = "showstopper"
    elif showstopper_count == 1:
        overall_risk = "high"
    elif watch_count >= 3:
        overall_risk = "high"
    elif watch_count >= 1:
        overall_risk = "medium"
    else:
        overall_risk = "low"

    return {
        "smiles": smiles,
        "criteria": all_criteria,
        "structural_alerts": alerts_result,
        "overall": {
            "risk": overall_risk,
            "showstopper_count": showstopper_count,
            "watch_count": watch_count,
            "pass_count": pass_count,
        },
        "disclaimer": (
            "IN-SILICO SCREENING ONLY — These results are computational triage "
            "signals based on predicted endpoints and structural pattern matching. "
            "They are NOT regulatory determinations and cannot replace experimental "
            "studies or expert regulatory assessment. Use for early-stage prioritization only."
        ),
    }


def assess_registration_risk_batch(
    smiles_list: List[str],
    use_predicted_fate: bool = True,
) -> List[Dict[str, Any]]:
    """Assess registration risk for a batch of compounds."""
    return [assess_registration_risk(s, use_predicted_fate=use_predicted_fate) for s in smiles_list]
