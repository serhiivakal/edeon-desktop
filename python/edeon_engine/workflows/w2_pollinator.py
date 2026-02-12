from typing import Any, List, Dict
from .contracts import WorkflowSpec, Step, WorkflowResult, Verdict
from .systemicity import compute_systemicity
from .verdict import resolve_confidence_label, map_ad_to_confidence

def w2_aggregator(step_outputs: dict, params: dict) -> WorkflowResult:
    standardize_out = step_outputs.get("standardize", [])
    if not isinstance(standardize_out, list):
        standardize_out = [standardize_out]
        
    selectivity_out = step_outputs.get("selectivity", [])
    systemicity_out = step_outputs.get("systemicity", [])
    
    warnings = []
    per_compound_results = []
    
    for idx, parent_item in enumerate(standardize_out):
        if not isinstance(parent_item, dict) or not parent_item.get("valid"):
            continue
        parent_smiles = parent_item["canonical"]
        parent_name = parent_item.get("name") or f"Compound {idx+1}"
        
        # Get selectivity profiles
        p_sel = selectivity_out[idx] if idx < len(selectivity_out) else {}
        p_sys = systemicity_out[idx] if idx < len(systemicity_out) else {}
        
        # Extract bee LD50s
        bee_oral = 10.0
        bee_contact = 10.0
        bee_oral_ad = "unknown"
        bee_contact_ad = "unknown"
        
        if isinstance(p_sel, dict) and isinstance(p_sel.get("profiles"), list):
            for prof in p_sel["profiles"]:
                if prof.get("organism") == "Honeybee":
                    # selectivity composite already resolved to min, let's look at profiles or extract values
                    bee_oral = prof.get("selectivity_index", 10.0)
                    bee_oral_ad = prof.get("ad_status", "unknown")
                    
        # Systemicity
        sys_val = p_sys.get("systemicity_index", 0.0)
        sys_route = p_sys.get("route", "contact")
        sys_ad = p_sys.get("envelope", {}).get("ad_status", "in_domain")
        
        # Intrinsic toxicity categorisation (using standard honeybee LD50 ug/bee limits)
        # We'll use the minimum index or values to classify hazard
        min_bee_val = bee_oral # selectivity index
        if min_bee_val < 2.0:
            tox_hazard = "high"
        elif min_bee_val < 11.0:
            tox_hazard = "moderate"
        else:
            tox_hazard = "low"
            
        sys_exposure = "high" if sys_val >= 0.5 else "low"
        
        # Determine risk band and driver
        if tox_hazard == "high" and sys_exposure == "high":
            band = "High"
            driver = "exposure-driven (systemic bee toxicity)"
            rationale = f"Compound is highly toxic to bees (index={min_bee_val}) and highly systemic (index={sys_val})."
        elif tox_hazard == "high" and sys_exposure == "low":
            band = "Med"
            driver = "contact-route-driven (non-systemic bee toxicity)"
            rationale = f"Compound is highly toxic to bees (index={min_bee_val}) but has low systemicity (index={sys_val})."
        elif tox_hazard == "moderate" and sys_exposure == "high":
            band = "Med"
            driver = "exposure-driven (moderate systemic bee toxicity)"
            rationale = f"Compound has moderate bee toxicity (index={min_bee_val}) and high systemicity (index={sys_val})."
        elif tox_hazard == "moderate" and sys_exposure == "low":
            band = "Low"
            driver = "contact-route-driven (moderate bee toxicity)"
            rationale = f"Compound has moderate bee toxicity (index={min_bee_val}) and low systemicity (index={sys_val})."
        else:
            band = "Low"
            driver = "low bee toxicity"
            rationale = f"Compound is classified as safe to bees (index={min_bee_val})."
            
        # Confidence resolution based on AD of both inputs
        conf_score = min(map_ad_to_confidence(bee_oral_ad), map_ad_to_confidence(sys_ad))
        confidence = resolve_confidence_label(conf_score)
        
        if confidence == "low":
            warnings.append(f"Low confidence for compound '{parent_name}' due to out-of-domain model prediction.")
            
        per_compound_results.append({
            "name": parent_name,
            "smiles": parent_smiles,
            "bee_oral_ld50": min_bee_val,
            "systemicity_index": sys_val,
            "systemicity_route": sys_route,
            "verdict": {
                "band": band,
                "driver": driver,
                "confidence": confidence,
                "rationale": rationale
            }
        })
        
    overall_verdict = per_compound_results[0]["verdict"] if per_compound_results else None
    if overall_verdict:
        overall_verdict = Verdict(
            band=overall_verdict["band"],
            driver=overall_verdict["driver"],
            confidence=overall_verdict["confidence"],
            rationale=overall_verdict["rationale"]
        )
        
    sections = {
        "summary": "Pollinator Safety Assessment integrating honeybee toxicity profiles with Briggs/Kleier phloem and xylem systemicity models.",
        "disclaimer": "IN-SILICO SCREENING ONLY — These results are computational triage signals based on predicted endpoints and structural pattern matching. They are NOT regulatory determinations and cannot replace experimental studies or expert regulatory assessment."
    }
    
    return WorkflowResult(
        workflow_id="pollinator_safety",
        per_compound=per_compound_results,
        overall=overall_verdict,
        sections=sections,
        warnings=list(set(warnings)),
        provenance={}
    )

W2_SPEC = WorkflowSpec(
    id="pollinator_safety",
    name="Pollinator Safety Screen",
    persona="Ecotox / Discovery",
    input_kind="series",
    default_params={},
    steps=[
        Step(name="standardize", method="standardize", applies_to="parent", params={"smiles": "$input.smiles"}),
        Step(name="environmental_fate", method="environmental_fate", applies_to="parent", params={"smiles": "$standardize.canonical"}),
        Step(name="selectivity", method="selectivity", applies_to="parent", params={"compounds": "$environmental_fate"}),
        Step(name="systemicity", method="systemicity", applies_to="parent", params={"compounds": "$environmental_fate"}),
    ],
    aggregator=w2_aggregator,
    report_template="w2_pollinator"
)
