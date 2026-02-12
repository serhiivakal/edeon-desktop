from typing import List, Optional, Tuple, Dict, Any
from .contracts import Verdict

def map_ad_to_confidence(ad_status: str) -> int:
    """Map AD status to a numeric value for min evaluation: 3 = high, 2 = moderate, 1 = low."""
    status = str(ad_status).lower().strip()
    if status in ("in", "in_domain", "true", "yes"):
        return 3
    elif status in ("borderline", "moderate"):
        return 2
    else:
        return 1

def resolve_confidence_label(score: int) -> str:
    if score >= 3:
        return "high"
    elif score == 2:
        return "moderate"
    else:
        return "low"

def make_confidence_aware_verdict(
    showstoppers: List[Dict[str, Any]]  # dict with keys: name, triggered, straddling, ad_status, rationale
) -> Verdict:
    """
    Applies the §1.3 Confidence-Aware Verdict Rule:
    1. If any showstopper is triggered and its inputs are in_domain -> NO_GO, confidence = high/moderate.
    2. If any showstopper triggers but inputs are out_of_domain or intervals straddle the threshold -> CONDITIONAL, confidence = low, driver = "insufficient model coverage — measured data needed".
    3. If no showstoppers trigger but there are borderline/straddling watch items -> CONDITIONAL, confidence = moderate.
    4. All clear and in_domain -> GO, confidence = high.
    """
    # Track the minimum confidence across all binding elements
    min_conf_score = 3
    
    triggered_in_domain = []
    triggered_out_or_straddle = []
    straddling_only = []
    
    for item in showstoppers:
        name = item.get("name", "Unknown Criterion")
        triggered = item.get("triggered", False)
        straddling = item.get("straddling", False)
        ad_status = item.get("ad_status", "out")
        rationale = item.get("rationale", "")
        
        conf_score = map_ad_to_confidence(ad_status)
        
        if triggered:
            if ad_status in ("in", "in_domain") and not straddling:
                triggered_in_domain.append((name, rationale))
                min_conf_score = min(min_conf_score, conf_score)
            else:
                triggered_out_or_straddle.append((name, rationale))
                min_conf_score = 1  # force low confidence
        elif straddling:
            straddling_only.append((name, rationale))
            min_conf_score = min(min_conf_score, 2)  # caps at moderate
            
    confidence_label = resolve_confidence_label(min_conf_score)
    
    if triggered_in_domain:
        # NO_GO: triggered showstoppers with high confidence
        drivers = ", ".join([name for name, _ in triggered_in_domain])
        rationales = "; ".join([rat for _, rat in triggered_in_domain if rat])
        return Verdict(
            band="NO_GO",
            driver=f"Showstopper triggered: {drivers}",
            confidence=confidence_label,
            rationale=rationales or "Showstopper criteria violated with high confidence."
        )
        
    if triggered_out_or_straddle:
        # CONDITIONAL due to insufficient model coverage
        drivers = ", ".join([name for name, _ in triggered_out_or_straddle])
        return Verdict(
            band="CONDITIONAL",
            driver="insufficient model coverage — measured data needed",
            confidence="low",
            rationale=f"Potential showstopper ({drivers}) identified but key inputs are out of domain or intervals straddle the threshold."
        )
        
    if straddling_only:
        # CONDITIONAL watch-level (near threshold or borderline domain)
        drivers = ", ".join([name for name, _ in straddling_only])
        return Verdict(
            band="CONDITIONAL",
            driver=f"Watch-level alert: {drivers}",
            confidence=confidence_label,
            rationale="Criteria are near threshold or inputs are borderline. Further evaluation recommended."
        )
        
    # All clear
    return Verdict(
        band="GO",
        driver="All criteria cleared",
        confidence="high",
        rationale="All evaluated parameters cleared the threshold with high confidence."
    )
