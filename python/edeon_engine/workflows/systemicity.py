import math
from typing import Optional, List

def compute_systemicity(log_kow: float, pka: Optional[float] = None, is_acid: bool = False) -> dict:
    """
    Computes phloem/xylem mobility index from log Kow and pKa using Briggs/Kleier models.
    """
    # Xylem concentration (TSCF) using Briggs:
    tscf = 0.784 * math.exp(-((log_kow - 1.78) ** 2) / 2.44) + 0.03
    
    # Phloem concentration factor (PCF) using Kleier weak acid logic:
    if pka is not None and is_acid:
        # Weak acid accumulation: optimized for pKa between 4.5 and 7.5
        dist_pka = abs(pka - 6.0)
        pka_factor = max(0.0, 1.0 - (dist_pka / 3.0))
        # Weak acid phloem mobility peaks around log Kow 1.0 to 2.0
        kow_factor = max(0.0, 1.0 - (abs(log_kow - 1.5) / 2.0))
        pcf = 0.9 * pka_factor * kow_factor
    else:
        # Non-ionized/neutral phloem mobility is lower
        pcf = 0.3 * max(0.0, 1.0 - (abs(log_kow - 1.0) / 2.0))

    # Normalize indices
    xylem_index = min(1.0, max(0.0, tscf / 0.8))
    phloem_index = min(1.0, max(0.0, pcf))

    systemicity_index = max(xylem_index, phloem_index)

    # Classify route
    if systemicity_index < 0.2:
        route = "contact"
    elif (phloem_index > xylem_index or is_acid) and phloem_index > 0.3:
        route = "phloem"
    else:
        route = "xylem"

    # AD range: log_kow should be in [-2.0, 5.0]
    in_domain = -2.0 <= log_kow <= 5.0
    ad_status = "in_domain" if in_domain else "out_of_domain"
    ad_score = 1.0 if in_domain else 0.0

    return {
        "systemicity_index": round(systemicity_index, 2),
        "route": route,
        "is_estimate": True,
        "envelope": {
            "value": round(systemicity_index, 2),
            "lower": round(max(0.0, systemicity_index - 0.15), 2),
            "upper": round(min(1.0, systemicity_index + 0.15), 2),
            "coverage": 0.95,
            "ad_status": ad_status,
            "ad_score": ad_score,
            "model_id": "systemicity_briggs_kleier_v1.0"
        }
    }

def compute_systemicity_batch(compounds: list[dict]) -> list[dict]:
    """Computes systemicity for a list of compounds."""
    results = []
    for c in compounds:
        if not isinstance(c, dict):
            # Fallback for unexpected formats
            results.append(compute_systemicity(2.0, None, False))
            continue
            
        log_kow_val = c.get("logp")
        if log_kow_val is None:
            lk = c.get("log_kow")
            if isinstance(lk, dict):
                log_kow_val = lk.get("value")
            else:
                log_kow_val = lk
        if log_kow_val is None:
            log_kow_val = 2.0
            
        pka = c.get("pka")
        if isinstance(pka, dict):
            pka = pka.get("value")
            
        is_acid = c.get("is_acid", False)
        smiles = c.get("smiles", "")
        if smiles and ("C(=O)O" in smiles or "C(=O)[O-]" in smiles):
            is_acid = True
            if pka is None:
                pka = 4.8  # typical carboxylic acid pKa
        
        res = compute_systemicity(log_kow_val, pka, is_acid)
        results.append(res)
    return results
