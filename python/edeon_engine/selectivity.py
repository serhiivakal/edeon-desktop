"""
Edeon Engine — Cross-Species Selectivity Analysis

Estimates selectivity indices for key non-target organisms using
calibrated QSAR models.

Organisms evaluated:
  - Honeybee (Apis mellifera) — contact/oral LD50 proxy
  - Earthworm (Eisenia fetida) — soil exposure
  - Fish (Oncorhynchus mykiss) — aquatic toxicity proxy
  - Bird (Colinus virginianus) — avian toxicity proxy
  - Daphnia (Daphnia magna) — aquatic invertebrate
  - Mammal (Rattus norvegicus) — mammalian oral toxicity proxy

Selectivity index = estimated non-target LC50 (or LD50) / estimated target EC50 (in ppm).
Higher = safer to non-target species.
"""

import math
import numpy as np
from typing import Optional, List, Dict, Any

from edeon_models import Endpoint
from edeon_models.ipc.commands import REGISTRY
from .tice_rules import check_tice_rules
from .properties import compute_properties_single

# Target organism mappings
ORGANISM_METADATA = {
    "Honeybee": {
        "latin": "Apis mellifera",
        "units": "× safety margin",
        "endpoint": Endpoint.BEE_ACUTE_ORAL_LD50, # Bee is handled as a min of oral and contact
        "conv_factor": 10.0, # 1 ug/bee ~= 10 ppm concentration equivalent
    },
    "Earthworm": {
        "latin": "Eisenia fetida",
        "units": "× safety margin",
        "endpoint": Endpoint.EARTHWORM_ACUTE_LC50,
        "conv_factor": 1.0,
    },
    "Fish": {
        "latin": "Oncorhynchus mykiss",
        "units": "× safety margin",
        "endpoint": Endpoint.FISH_ACUTE_LC50,
        "conv_factor": 1.0,
    },
    "Bird": {
        "latin": "Colinus virginianus",
        "units": "× safety margin",
        "endpoint": Endpoint.BIRD_ACUTE_ORAL_LD50,
        "conv_factor": 1.0,
    },
    "Daphnia": {
        "latin": "Daphnia magna",
        "units": "× safety margin",
        "endpoint": Endpoint.DAPHNIA_ACUTE_EC50,
        "conv_factor": 1.0,
    },
    "Mammal": {
        "latin": "Rattus norvegicus",
        "units": "× safety margin",
        "endpoint": Endpoint.RAT_ACUTE_ORAL_LD50,
        "conv_factor": 1.0,
    }
}


def _get_t2_fallback_value(endpoint: Endpoint, logp: float, mw: float) -> float:
    """Provides fallback heuristic values in native units when QSAR predictions fail."""
    if endpoint == Endpoint.BEE_ACUTE_ORAL_LD50 or endpoint == Endpoint.BEE_ACUTE_CONTACT_LD50:
        return 10.0 ** (2.5 - 0.5 * logp)
    elif endpoint == Endpoint.EARTHWORM_ACUTE_LC50:
        return 10.0 ** (3.0 - 0.4 * logp)
    elif endpoint == Endpoint.FISH_ACUTE_LC50:
        return 10.0 ** (1.6 - 0.55 * logp - 0.001 * mw)
    elif endpoint == Endpoint.DAPHNIA_ACUTE_EC50:
        return 10.0 ** (1.5 - 0.6 * logp)
    elif endpoint == Endpoint.BIRD_ACUTE_ORAL_LD50:
        return 10.0 ** (3.5 - 0.3 * logp)
    elif endpoint == Endpoint.RAT_ACUTE_ORAL_LD50:
        return 10.0 ** (4.0 - 0.3 * logp - 0.002 * mw)
    return 10.0


def _predict_target_potency_uM(compound_props: dict) -> float:
    """Predicts target potency in uM based on property heuristics."""
    tice = check_tice_rules(compound_props)
    level = tice.get("level", "High")
    if level == "High":
        return 0.5  # Potent (0.5 uM)
    elif level == "Med":
        return 2.0  # Moderate (2 uM)
    else:
        return 10.0 # Weak (10 uM)


def _get_organism_prediction(smiles: str, endpoint: Endpoint, props: dict) -> Dict[str, Any]:
    """Retrieves point prediction, CI, and AD status for a single endpoint, falling back to heuristics."""
    try:
        backend = REGISTRY.get(endpoint)
        pred = backend.predict([smiles])[0]
        
        val = pred.value.numeric
        if val is None or math.isnan(val) or val <= 0:
            raise ValueError("Invalid numeric value")
            
        return {
            "value": float(val),
            "ci_lower": float(pred.ci_lower) if pred.ci_lower is not None else None,
            "ci_upper": float(pred.ci_upper) if pred.ci_upper is not None else None,
            "ad_status": pred.ad_status.value if hasattr(pred.ad_status, 'value') else str(pred.ad_status),
            "ad_score": float(pred.ad_score) if pred.ad_score is not None else None,
        }
    except Exception:
        logp = props.get("logp", 2.0) or 2.0
        mw = props.get("mol_weight", 300.0) or 300.0
        val = _get_t2_fallback_value(endpoint, logp, mw)
        return {
            "value": float(val),
            "ci_lower": float(val / 3.0),
            "ci_upper": float(val * 3.0),
            "ad_status": "unknown",
            "ad_score": None,
        }


def _get_bee_prediction_composite(smiles: str, props: dict) -> Dict[str, Any]:
    """Retrieves bee composite toxicity by selecting the minimum of oral and contact."""
    oral = _get_organism_prediction(smiles, Endpoint.BEE_ACUTE_ORAL_LD50, props)
    contact = _get_organism_prediction(smiles, Endpoint.BEE_ACUTE_CONTACT_LD50, props)
    
    val_o = oral["value"]
    val_c = contact["value"]
    
    if val_o <= val_c:
        return oral
    return contact


def run_monte_carlo_propagation(
    log_tox_ppm: float,
    std_tox: float,
    log_target_ppm: float,
    std_target: float,
    n_samples: int = 1000
) -> tuple[float, float]:
    """Draws random samples to compute the 90% confidence bounds for fold-selectivity."""
    samples_tox = np.random.normal(log_tox_ppm, std_tox, n_samples)
    samples_target = np.random.normal(log_target_ppm, std_target, n_samples)
    
    samples_si = samples_tox - samples_target
    
    si_lower = float(np.percentile(samples_si, 5))
    si_upper = float(np.percentile(samples_si, 95))
    
    return 10.0 ** si_lower, 10.0 ** si_upper


def compute_single_selectivity(
    smiles: str,
    target_potency_uM: Optional[float] = None,
    target_mode: str = "predicted"
) -> dict:
    """Computes cross-species selectivity safety margins and propagates conformal intervals."""
    # 1. Compute single physicochemical properties
    props = compute_properties_single(smiles)
    if not props.get("valid", False):
        # Fallback for invalid SMILES
        empty_profiles = []
        for org, meta in ORGANISM_METADATA.items():
            empty_profiles.append({
                "organism": org,
                "selectivity_index": 0.0,
                "level": "danger",
                "detail": "Invalid structure",
                "ci_lower": 0.0,
                "ci_upper": 0.0,
                "ad_status": "unknown"
            })
        return {
            "profiles": empty_profiles,
            "min_selectivity": 0.0,
            "overall_level": "danger",
            "uq": {
                "lower": 0.0,
                "upper": 0.0,
                "ad_status": "unknown",
                "ad_score": None,
                "coverage": 0.90,
                "model_id": "selectivity_ensemble",
                "model_version": "0.1.0"
            }
        }

    mw = props.get("mol_weight", 300.0) or 300.0

    # 2. Determine target potency (ppm)
    if target_mode == "user" and target_potency_uM is not None:
        uM = target_potency_uM
    else:
        uM = _predict_target_potency_uM(props)
        
    EC50_target_ppm = uM * mw / 1000.0
    log_target_ppm = math.log10(EC50_target_ppm)
    std_target = 0.0 if target_mode == "user" else 0.1

    # 3. Predict non-target toxicities & calculate safety margins
    profiles = []
    min_si_val = float("inf")
    all_lower_bounds = []
    all_upper_bounds = []
    ad_statuses = []
    ad_scores = []

    for organism, meta in ORGANISM_METADATA.items():
        # Fetch toxicity prediction (native units)
        if organism == "Honeybee":
            pred = _get_bee_prediction_composite(smiles, props)
        else:
            pred = _get_organism_prediction(smiles, meta["endpoint"], props)
            
        tox_val = pred["value"]
        
        # Convert to ppm equivalent
        tox_ppm = tox_val * meta["conv_factor"]
        log_tox_ppm = math.log10(tox_ppm)

        # Determine standard deviation of log-toxicity for Monte Carlo
        if pred["ci_lower"] is not None and pred["ci_upper"] is not None and pred["ci_lower"] > 0:
            log_l = math.log10(pred["ci_lower"] * meta["conv_factor"])
            log_u = math.log10(pred["ci_upper"] * meta["conv_factor"])
            std_tox = max(0.01, (log_u - log_l) / 3.92)
        else:
            std_tox = 0.2 # Default standard deviation of 0.2 log units

        # Propagate intervals via Monte Carlo
        ci_l_linear, ci_u_linear = run_monte_carlo_propagation(log_tox_ppm, std_tox, log_target_ppm, std_target)

        # Safety margin (ratio)
        si_linear = tox_ppm / EC50_target_ppm
        min_si_val = min(min_si_val, si_linear)
        all_lower_bounds.append(ci_l_linear)
        all_upper_bounds.append(ci_u_linear)

        # Apply thresholds for risk levels
        # Default safety margin criteria: Safe >= 10, Moderate >= 3, else Danger
        # Mammal is stricter: Safe >= 100, Moderate >= 10, else Danger
        if organism == "Mammal":
            if si_linear >= 100.0:
                level = "safe"
                detail = "Low mammalian toxicity expected"
            elif si_linear >= 10.0:
                level = "moderate"
                detail = "Moderate mammalian exposure risk"
            else:
                level = "danger"
                detail = "High mammalian oral risk"
        elif organism == "Honeybee":
            if si_linear >= 10.0:
                level = "safe"
                detail = "Low contact toxicity expected"
            elif si_linear >= 3.0:
                level = "moderate"
                detail = "Moderate oral/contact risk"
            else:
                level = "danger"
                detail = "High bee toxicity risk"
        elif organism == "Earthworm":
            if si_linear >= 8.0:
                level = "safe"
                detail = "Low soil organism toxicity"
            elif si_linear >= 3.0:
                level = "moderate"
                detail = "Moderate soil exposure concern"
            else:
                level = "danger"
                detail = "High earthworm toxicity"
        elif organism == "Fish":
            if si_linear >= 10.0:
                level = "safe"
                detail = "Low aquatic toxicity"
            elif si_linear >= 3.0:
                level = "moderate"
                detail = "Moderate aquatic risk"
            else:
                level = "danger"
                detail = "High fish toxicity risk"
        elif organism == "Daphnia":
            if si_linear >= 10.0:
                level = "safe"
                detail = "Low invertebrate toxicity"
            elif si_linear >= 3.0:
                level = "moderate"
                detail = "Moderate aquatic invertebrate risk"
            else:
                level = "danger"
                detail = "High Daphnia toxicity"
        else: # Bird
            if si_linear >= 10.0:
                level = "safe"
                detail = "Low avian toxicity expected"
            elif si_linear >= 5.0:
                level = "moderate"
                detail = "Moderate dietary exposure risk"
            else:
                level = "danger"
                detail = "High avian toxicity risk"

        profiles.append({
            "organism": organism,
            "latin": meta["latin"],
            "selectivity_index": round(si_linear, 1),
            "level": level,
            "detail": detail,
            "ci_lower": round(ci_l_linear, 1),
            "ci_upper": round(ci_u_linear, 1),
            "ad_status": pred["ad_status"],
            "ad_score": pred["ad_score"],
        })
        ad_statuses.append(pred["ad_status"])
        if pred["ad_score"] is not None:
            ad_scores.append(pred["ad_score"])

    # Compute overall level
    danger_count = sum(1 for p in profiles if p["level"] == "danger")
    moderate_count = sum(1 for p in profiles if p["level"] == "moderate")
    
    if danger_count > 0:
        overall_level = "danger"
    elif moderate_count >= 2:
        overall_level = "moderate"
    else:
        overall_level = "safe"

    # Assemble composite UQ envelope
    if "out" in ad_statuses:
        composite_ad = "out"
    elif "borderline" in ad_statuses:
        composite_ad = "borderline"
    elif "in" in ad_statuses:
        composite_ad = "in"
    else:
        composite_ad = "unknown"

    uq_envelope = {
        "lower": round(min(all_lower_bounds), 1),
        "upper": round(min(all_upper_bounds), 1), # conservative worst-case bounds
        "ad_status": composite_ad,
        "ad_score": float(np.mean(ad_scores)) if ad_scores else None,
        "coverage": 0.90,
        "model_id": "selectivity_ensemble",
        "model_version": "0.1.0"
    }

    return {
        "profiles": profiles,
        "min_selectivity": round(min_si_val, 1),
        "overall_level": overall_level,
        "uq": uq_envelope,
    }


def compute_selectivity(compound: dict) -> dict:
    """Main wrapper compat entry point for single compound."""
    smiles = compound.get("smiles", "")
    return compute_single_selectivity(smiles)


def selectivity_batch(compounds: list[dict], target_potency: Optional[dict] = None) -> list[dict]:
    """Compute selectivity profiles for a batch of compounds."""
    results = []
    
    # Parse target potency parameters
    mode = "predicted"
    values = []
    single_val = None
    
    if target_potency is not None:
        mode = target_potency.get("mode", "predicted")
        if mode == "user":
            if "values" in target_potency:
                values = target_potency["values"]
            elif "value" in target_potency:
                single_val = float(target_potency["value"])

    for idx, c in enumerate(compounds):
        smiles = c.get("smiles", "")
        
        # Determine specific user potency value if available
        uM_val = None
        if mode == "user":
            if idx < len(values):
                uM_val = float(values[idx])
            else:
                uM_val = single_val if single_val is not None else 1.0

        results.append(compute_single_selectivity(smiles, target_potency_uM=uM_val, target_mode=mode))
        
    return results
