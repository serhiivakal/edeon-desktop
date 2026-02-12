from typing import Any
from .contracts import WorkflowSpec, Step, WorkflowResult, Verdict
from .verdict import make_confidence_aware_verdict

def w1_aggregator(step_outputs: dict, params: dict) -> WorkflowResult:
    # Parents list
    standardize_out = step_outputs.get("standardize", [])
    if not isinstance(standardize_out, list):
        standardize_out = [standardize_out]
        
    fate_out = step_outputs.get("environmental_fate", [])
    selectivity_out = step_outputs.get("selectivity", [])
    tp_out = step_outputs.get("transformation_products", [])
    reg_risk_out = step_outputs.get("registration_risk", [])
    
    # TPs list
    tp_reg_risk_out = step_outputs.get("tp_registration_risk", [])
    
    # Index TPs outputs by smiles for easy access
    tp_reg_risk_by_smiles = {}
    if isinstance(tp_reg_risk_out, list):
        for item in tp_reg_risk_out:
            if isinstance(item, dict) and "smiles" in item:
                tp_reg_risk_by_smiles[item["smiles"]] = item

    warnings = []
    per_compound_results = []
    
    for idx, parent_item in enumerate(standardize_out):
        if not isinstance(parent_item, dict) or not parent_item.get("valid"):
            continue
        parent_smiles = parent_item["canonical"]
        parent_name = parent_item.get("name") or f"Compound {idx+1}"
        
        # Get parent fate, selectivity, registration_risk
        p_fate = fate_out[idx] if idx < len(fate_out) else {}
        p_selectivity = selectivity_out[idx] if idx < len(selectivity_out) else {}
        p_reg_risk = reg_risk_out[idx] if idx < len(reg_risk_out) else {}
        
        # Get metabolites
        parent_tps = tp_out[idx] if idx < len(tp_out) else []
        if isinstance(parent_tps, dict) and "result" in parent_tps:
            parent_tps = parent_tps["result"]
            
        prob_cutoff = params.get("tp_probability_cutoff", 0.1)
        valid_tps = []
        if isinstance(parent_tps, list):
            for tp in parent_tps:
                if isinstance(tp, dict):
                    prob = tp.get("probability", 1.0)
                    if prob >= prob_cutoff:
                        valid_tps.append(tp)
                    
        # Find the worst TP registration risk
        worst_tp_risk = None
        worst_tp_scorecard = None
        worst_tp_smiles = None
        
        for tp in valid_tps:
            tp_smiles = tp.get("smiles")
            tp_card = tp_reg_risk_by_smiles.get(tp_smiles)
            if tp_card:
                risk_level = tp_card.get("overall", {}).get("risk", "low")
                if worst_tp_risk is None:
                    worst_tp_risk = risk_level
                    worst_tp_scorecard = tp_card
                    worst_tp_smiles = tp_smiles
                else:
                    rank = {"showstopper": 4, "high": 3, "medium": 2, "low": 1}
                    if rank.get(risk_level, 0) > rank.get(worst_tp_risk, 0):
                        worst_tp_risk = risk_level
                        worst_tp_scorecard = tp_card
                        worst_tp_smiles = tp_smiles
                        
        # Evaluate parent criteria showstoppers
        showstoppers = []
        
        p_ad_fate = "in_domain"
        if isinstance(p_fate, dict):
            for k in ["log_kow", "bcf", "dt50_soil", "koc"]:
                env = p_fate.get(k, {})
                if isinstance(env, dict) and env.get("ad_status") == "out_of_domain":
                    p_ad_fate = "out_of_domain"
                    warnings.append(f"Fate prediction for endpoint '{k}' is Out of Domain for parent.")
                    
        p_ad_tox = "in_domain"
        if isinstance(p_selectivity, dict) and isinstance(p_selectivity.get("profiles"), list):
            for prof in p_selectivity["profiles"]:
                if isinstance(prof, dict) and prof.get("applicability_domain", {}).get("status") == "out_of_domain":
                    p_ad_tox = "out_of_domain"
                    warnings.append(f"Toxicity prediction for endpoint '{prof.get('endpoint')}' is Out of Domain for parent.")

        if isinstance(p_reg_risk, dict) and isinstance(p_reg_risk.get("criteria"), list):
            for crit in p_reg_risk["criteria"]:
                crit_name = crit["criterion"]
                triggered = crit["status"] == "likely_showstopper"
                straddling = crit["status"] == "watch"
                
                ad_status = "in_domain"
                if "PBT" in crit_name or "Soil persistence" in crit_name or "Groundwater" in crit_name:
                    ad_status = p_ad_fate
                elif "Aquatic hazard" in crit_name or "Acute mammalian" in crit_name:
                    ad_status = p_ad_tox
                    
                showstoppers.append({
                    "name": crit_name,
                    "triggered": triggered,
                    "straddling": straddling,
                    "ad_status": ad_status,
                    "rationale": ", ".join(crit.get("evidence", []))
                })
            
        verdict = make_confidence_aware_verdict(showstoppers)
        
        # Metabolite risk check
        if worst_tp_scorecard:
            tp_showstoppers = [c for c in worst_tp_scorecard.get("criteria", []) if c["status"] == "likely_showstopper"]
            parent_showstoppers = []
            if isinstance(p_reg_risk, dict) and isinstance(p_reg_risk.get("criteria"), list):
                parent_showstoppers = [c for c in p_reg_risk["criteria"] if c["status"] == "likely_showstopper"]
            parent_showstopper_names = {c["criterion"] for c in parent_showstoppers}
            
            new_showstoppers = [c for c in tp_showstoppers if c["criterion"] not in parent_showstopper_names]
            if new_showstoppers:
                new_names = ", ".join([c["criterion"] for c in new_showstoppers])
                verdict = Verdict(
                    band="CONDITIONAL",
                    driver="metabolite-driven risk",
                    confidence="moderate",
                    rationale=f"Parent cleared showstoppers, but metabolite {worst_tp_smiles} introduces showstoppers: {new_names}."
                )
                
        per_compound_results.append({
            "name": parent_name,
            "smiles": parent_smiles,
            "verdict": {
                "band": verdict.band,
                "driver": verdict.driver,
                "confidence": verdict.confidence,
                "rationale": verdict.rationale
            },
            "scorecard": p_reg_risk,
            "worst_tp": worst_tp_scorecard,
            "tp_count": len(valid_tps),
            "metabolite_risk": worst_tp_risk or "low"
        })
        
    overall_verdict = per_compound_results[0]["verdict"] if per_compound_results else None
    if overall_verdict:
        overall_verdict = Verdict(**overall_verdict)
        
    sections = {
        "summary": "Registration readiness assessment dossier comparing parent compounds and predicted transformation products under EU 1107/2009 and CLP regulations.",
        "disclaimer": "IN-SILICO SCREENING ONLY — These results are computational triage signals based on predicted endpoints and structural pattern matching. They are NOT regulatory determinations and cannot replace experimental studies or expert regulatory assessment."
    }
    
    return WorkflowResult(
        workflow_id="registration_readiness",
        per_compound=per_compound_results,
        overall=overall_verdict,
        sections=sections,
        warnings=list(set(warnings)),
        provenance={}
    )

W1_SPEC = WorkflowSpec(
    id="registration_readiness",
    name="Registration Readiness Pre-Screen",
    persona="Regulatory affairs / project lead",
    input_kind="single",
    default_params={
        "use_predicted_fate": True,
        "tp_depth": 2,
        "tp_routes": ["abiotic", "metabolic"],
        "tp_probability_cutoff": 0.1
    },
    steps=[
        Step(name="standardize", method="standardize", applies_to="parent", params={"smiles": "$input.smiles"}),
        Step(name="environmental_fate", method="environmental_fate", applies_to="parent", params={"smiles": "$standardize.canonical"}),
        Step(name="selectivity", method="selectivity", applies_to="parent", params={"compounds": "$environmental_fate"}),
        Step(name="transformation_products", method="transformation_products", applies_to="each_compound", params={"smiles": "$standardize.canonical", "routes": "$params.tp_routes", "max_depth": "$params.tp_depth"}),
        Step(name="tp_standardize", method="standardize", applies_to="each_tp", params={"smiles": "$transformation_products.smiles"}),
        Step(name="tp_registration_risk", method="registration_risk", applies_to="each_tp", params={"smiles": "$tp_standardize.canonical", "use_predicted_fate": "$params.use_predicted_fate"}),
        Step(name="registration_risk", method="registration_risk", applies_to="each_compound", params={"smiles": "$standardize.canonical", "use_predicted_fate": "$params.use_predicted_fate"}),
    ],
    aggregator=w1_aggregator,
    report_template="w1_dossier"
)
