import math
from typing import Optional
from edeon_models import Endpoint
from edeon_models.ipc.commands import REGISTRY
from edeon_engine.properties import compute_properties_single

def predict_compound_fate(smiles: str) -> dict:
    """Predict environmental fate parameters for a single compound.

    Returns a dict containing:
        - dt50_soil: Prediction envelope
        - koc: Prediction envelope
        - bcf: Prediction envelope
        - log_kow: Prediction envelope
        - henry: Prediction envelope
        - gus: Prediction envelope + "class" field
        - pbt: PBT scorecard status dict
    """
    try:
        props = compute_properties_single(smiles)
        if not props.get("valid", False):
            raise ValueError("Invalid SMILES structure.")
            
        logp = props.get("logp", 2.0)
        mw = props.get("mol_weight", 300)
        tpsa = props.get("tpsa", 60)
        hbd = props.get("hbd", 1)
        if logp is None: logp = 2.0
        if mw is None: mw = 300
        if tpsa is None: tpsa = 60
        if hbd is None: hbd = 1

        # 1. Retrieve predictions from registry
        dt50_pred = REGISTRY.get(Endpoint.SOIL_DT50).predict([smiles])[0]
        koc_pred = REGISTRY.get(Endpoint.SOIL_KOC).predict([smiles])[0]
        bcf_pred = REGISTRY.get(Endpoint.BCF).predict([smiles])[0]

        # 2. Estimate Log Kow (based on Crippen LogP descriptor)
        log_kow_val = float(logp)
        log_kow_envelope = {
            "value": log_kow_val,
            "ci_lower": log_kow_val - 0.5,
            "ci_upper": log_kow_val + 0.5,
            "ci_level": 0.95,
            "ad_status": "in",
            "ad_score": 1.0,
            "units": "log units",
            "model_id": "edeon_log_kow_descriptor",
            "model_version": "0.1.0",
            "tier": 2,
            "warnings": ["Calculated directly from RDKit Crippen LogP"]
        }

        # 3. Estimate Henry's Law Constant (atm-m3/mol)
        log_h = -4.5 + 0.5 * log_kow_val - 0.05 * float(tpsa) - 0.2 * float(hbd)
        log_h = max(-15.0, min(2.0, log_h))
        henry_val = float(10 ** log_h)
        henry_envelope = {
            "value": henry_val,
            "ci_lower": float(10 ** (log_h - 1.5)),
            "ci_upper": float(10 ** (log_h + 1.5)),
            "ci_level": 0.95,
            "ad_status": "unknown",
            "ad_score": None,
            "units": "atm-m3/mol",
            "model_id": "edeon_legacy_henry",
            "model_version": "0.1.0-legacy",
            "tier": 2,
            "warnings": ["Screening estimate — Tier-2 descriptor-based heuristic"]
        }

        # Extract values for calculations
        dt50_val = max(0.1, dt50_pred.value.numeric if dt50_pred.value.numeric is not None else 20.0)
        koc_val = max(1.0, koc_pred.value.numeric if koc_pred.value.numeric is not None else 100.0)

        # 4. Calculate GUS Index
        log_koc = math.log10(koc_val)
        log_dt50 = math.log10(dt50_val)
        gus_val = log_dt50 * (4.0 - log_koc) if log_koc < 4.0 else 0.0

        # Propagate GUS intervals
        gus_ci_lower = None
        gus_ci_upper = None
        if dt50_pred.ci_lower is not None and dt50_pred.ci_upper is not None and koc_pred.ci_lower is not None and koc_pred.ci_upper is not None:
            dt50_l = max(0.1, dt50_pred.ci_lower)
            dt50_u = max(0.1, dt50_pred.ci_upper)
            koc_l = max(1.0, koc_pred.ci_lower)
            koc_u = max(1.0, koc_pred.ci_upper)
            
            # Lower bound of GUS occurs at lower DT50 and upper Koc
            log_koc_u = math.log10(koc_u)
            gus_ci_lower = math.log10(dt50_l) * (4.0 - log_koc_u) if log_koc_u < 4.0 else 0.0
            
            # Upper bound of GUS occurs at upper DT50 and lower Koc
            log_koc_l = math.log10(koc_l)
            gus_ci_upper = math.log10(dt50_u) * (4.0 - log_koc_l) if log_koc_l < 4.0 else 0.0

        # Combine AD status
        s1 = dt50_pred.ad_status.value if hasattr(dt50_pred.ad_status, 'value') else str(dt50_pred.ad_status)
        s2 = koc_pred.ad_status.value if hasattr(koc_pred.ad_status, 'value') else str(koc_pred.ad_status)
        if s1 == "out" or s2 == "out":
            gus_ad = "out"
        elif s1 == "borderline" or s2 == "borderline":
            gus_ad = "borderline"
        elif s1 == "in" and s2 == "in":
            gus_ad = "in"
        else:
            gus_ad = "unknown"

        # GUS Classification
        if gus_val > 2.8:
            gus_class = "leacher"
        elif gus_val >= 1.8:
            gus_class = "transition"
        else:
            gus_class = "non-leacher"

        gus_envelope = {
            "value": float(gus_val),
            "ci_lower": float(gus_ci_lower) if gus_ci_lower is not None else None,
            "ci_upper": float(gus_ci_upper) if gus_ci_upper is not None else None,
            "ci_level": 0.95,
            "ad_status": gus_ad,
            "ad_score": None,
            "units": "unitless",
            "model_id": "edeon_gus_propagator",
            "model_version": "0.1.0",
            "tier": 2,
            "warnings": ["Calculated from predicted Soil Koc and Soil DT50"],
            "class": gus_class
        }

        # 5. REACH Annex XIII PBT/vPvB scorecard
        # P flag: DT50 > 120 days (soil)
        is_p = dt50_val > 120.0
        is_vp = dt50_val > 180.0

        # B flag: BCF > 2000 (or Log Kow > 4.5)
        bcf_val = bcf_pred.value.numeric if bcf_pred.value.numeric is not None else 10.0
        is_b = bcf_val > 2000.0 or log_kow_val > 4.5
        is_vb = bcf_val > 5000.0

        # T flag: Ecotoxicity < 0.1 mg/L for fish/daphnia
        # Retrieve predictions for aquatic toxicity endpoints
        try:
            fish_pred = REGISTRY.get(Endpoint.FISH_ACUTE_LC50).predict([smiles])[0]
            fish_lc50 = fish_pred.value.numeric if fish_pred.value.numeric is not None else 999.0
        except Exception:
            fish_lc50 = 999.0

        try:
            daphnia_pred = REGISTRY.get(Endpoint.DAPHNIA_ACUTE_EC50).predict([smiles])[0]
            daphnia_ec50 = daphnia_pred.value.numeric if daphnia_pred.value.numeric is not None else 999.0
        except Exception:
            daphnia_ec50 = 999.0

        is_t = (fish_lc50 < 0.1) or (daphnia_ec50 < 0.1)

        # Overall PBT verdict
        if is_vp and is_vb:
            pbt_verdict = "vPvB"
        elif is_p and is_b and is_t:
            pbt_verdict = "PBT"
        else:
            active_flags = []
            if is_vp: active_flags.append("vP")
            elif is_p: active_flags.append("P")
            if is_vb: active_flags.append("vB")
            elif is_b: active_flags.append("B")
            if is_t: active_flags.append("T")
            
            if active_flags:
                pbt_verdict = f"Concern: {'+'.join(active_flags)}"
            else:
                pbt_verdict = "Not PBT/vPvB"

        pbt_scorecard = {
            "p": bool(is_p),
            "vp": bool(is_vp),
            "b": bool(is_b),
            "vb": bool(is_vb),
            "t": bool(is_t),
            "verdict": pbt_verdict
        }

        # Helper function to serialize standard Prediction objects
        def to_envelope(pred) -> dict:
            return {
                "value": float(pred.value.numeric) if pred.value.numeric is not None else None,
                "ci_lower": float(pred.ci_lower) if pred.ci_lower is not None else None,
                "ci_upper": float(pred.ci_upper) if pred.ci_upper is not None else None,
                "ci_level": pred.ci_level,
                "ad_status": pred.ad_status.value if hasattr(pred.ad_status, 'value') else str(pred.ad_status),
                "ad_score": float(pred.ad_score) if pred.ad_score is not None else None,
                "units": pred.units,
                "model_id": pred.model_id,
                "model_version": pred.model_version,
                "tier": pred.tier,
                "warnings": pred.warnings
            }

        return {
            "smiles": smiles,
            "dt50_soil": to_envelope(dt50_pred),
            "koc": to_envelope(koc_pred),
            "bcf": to_envelope(bcf_pred),
            "log_kow": log_kow_envelope,
            "henry": henry_envelope,
            "gus": gus_envelope,
            "pbt": pbt_scorecard
        }

    except Exception as e:
        # Return fallback/error response
        error_env = {
            "value": None, "ci_lower": None, "ci_upper": None, "ci_level": 0.95,
            "ad_status": "unknown", "ad_score": None, "units": "",
            "model_id": "failed", "model_version": "", "tier": 2, "warnings": [str(e)]
        }
        return {
            "smiles": smiles,
            "dt50_soil": error_env,
            "koc": error_env,
            "bcf": error_env,
            "log_kow": error_env,
            "henry": error_env,
            "gus": dict(error_env, **{"class": "unknown"}),
            "pbt": {"p": False, "vp": False, "b": False, "vb": False, "t": False, "verdict": "Failed"}
        }

def environmental_fate_batch(smiles_list: list[str]) -> list[dict]:
    """Compute environmental fate profiles for a batch of compounds."""
    return [predict_compound_fate(s) for s in smiles_list]
