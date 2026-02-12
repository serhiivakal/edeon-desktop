from typing import Any, List, Dict
from .contracts import WorkflowSpec, Step, WorkflowResult, Verdict

def w4_aggregator(step_outputs: dict, params: dict) -> WorkflowResult:
    standardize_out = step_outputs.get("standardize", [])
    if not isinstance(standardize_out, list):
        standardize_out = [standardize_out]
        
    fate_out = step_outputs.get("environmental_fate", [])
    selectivity_out = step_outputs.get("selectivity", [])
    suggested_analogs_out = step_outputs.get("suggest_analogs", [])
    
    analog_std_out = step_outputs.get("analog_standardize", [])
    analog_fate_out = step_outputs.get("analog_fate", [])
    analog_selectivity_out = step_outputs.get("analog_selectivity", [])
    
    # Map analog properties by canonical smiles
    analog_fate_by_canonical = {}
    if isinstance(analog_fate_out, list):
        for item in analog_fate_out:
            if isinstance(item, dict) and "original" in item:
                # We can standardize or map via analog_std_out
                analog_fate_by_canonical[item["original"]] = item

    analog_canonical_map = {}
    if isinstance(analog_std_out, list):
        for item in analog_std_out:
            if isinstance(item, dict) and item.get("valid"):
                analog_canonical_map[item["original"]] = item["canonical"]

    # Re-map by canonical for robust lookups
    analog_fate_clean = {}
    for orig, item in analog_fate_by_canonical.items():
        canon = analog_canonical_map.get(orig, orig)
        analog_fate_clean[canon] = item
        
    analog_selectivity_clean = {}
    if isinstance(analog_selectivity_out, list):
        for item in analog_selectivity_out:
            if isinstance(item, dict):
                orig = item.get("_source_smiles") or item.get("original")
                if orig:
                    canon = analog_canonical_map.get(orig, orig)
                    analog_selectivity_clean[canon] = item

    objective = params.get("objective", "selectivity")
    warnings = []
    per_compound_results = []
    
    for idx, parent_item in enumerate(standardize_out):
        if not isinstance(parent_item, dict) or not parent_item.get("valid"):
            continue
        parent_smiles = parent_item["canonical"]
        parent_name = parent_item.get("name") or f"Compound {idx+1}"
        
        p_fate = fate_out[idx] if idx < len(fate_out) else {}
        p_sel = selectivity_out[idx] if idx < len(selectivity_out) else {}
        
        # Get suggested analogs for this specific parent
        p_analogs = suggested_analogs_out[idx] if idx < len(suggested_analogs_out) else []
        if isinstance(p_analogs, dict) and "result" in p_analogs:
            p_analogs = p_analogs["result"]
            
        ranked_analogs = []
        if isinstance(p_analogs, list):
            for anal in p_analogs:
                if not isinstance(anal, dict):
                    continue
                anal_smiles = anal.get("smiles")
                transformation = anal.get("transformation", "Modification")
                
                # Fetch scores
                a_fate = analog_fate_clean.get(anal_smiles, {})
                a_sel = analog_selectivity_clean.get(anal_smiles, {})
                
                # Compare objective delta
                delta = 0.0
                trade_offs = []
                ad_status = "in_domain"
                
                if objective == "selectivity":
                    p_val = p_sel.get("min_selectivity", 1.0)
                    a_val = a_sel.get("min_selectivity", 1.0)
                    delta = a_val - p_val
                    ad_status = a_sel.get("uq", {}).get("ad_status", "in_domain")
                else: # fate / persistence
                    p_val = p_fate.get("dt50_soil", {}).get("value", 50.0) or 50.0
                    a_val = a_fate.get("dt50_soil", {}).get("value", 50.0) or 50.0
                    delta = p_val - a_val  # positive delta means persistence decreased (improved!)
                    ad_status = a_fate.get("dt50_soil", {}).get("ad_status", "in_domain")
                    
                # Check for "no free lunch" trade-offs (e.g. if toxicity gets worse while fate improves)
                p_tox = p_sel.get("min_selectivity", 1.0)
                a_tox = a_sel.get("min_selectivity", 1.0)
                if a_tox < p_tox / 1.5:
                    trade_offs.append(f"Selectivity margin dropped ({a_tox:.1f} vs parent {p_tox:.1f})")
                    
                p_pers = p_fate.get("dt50_soil", {}).get("value", 0.0) or 0.0
                a_pers = a_fate.get("dt50_soil", {}).get("value", 0.0) or 0.0
                if a_pers > p_pers * 1.5 and a_pers > 90:
                    trade_offs.append(f"Persistence increased ({a_pers:.0f}d vs parent {p_pers:.0f}d)")
                    
                ranked_analogs.append({
                    "smiles": anal_smiles,
                    "transformation": transformation,
                    "delta": round(delta, 2),
                    "ad_status": ad_status,
                    "trade_offs": trade_offs,
                    "score": round(delta - (0.5 * len(trade_offs)), 2), # composite score penalizing trade-offs
                    "is_in_domain": ad_status in ("in", "in_domain")
                })
                
        # Sort analogs: in-domain first, then by score
        ranked_analogs.sort(key=lambda x: (x["is_in_domain"], x["score"]), reverse=True)
        
        # Limit to top N
        n_limit = params.get("n_analogs", 10)
        ranked_analogs = ranked_analogs[:n_limit]
        
        per_compound_results.append({
            "name": parent_name,
            "smiles": parent_smiles,
            "objective": objective,
            "parent_score": p_sel.get("min_selectivity") if objective == "selectivity" else p_fate.get("dt50_soil", {}).get("value"),
            "analogs": ranked_analogs
        })
        
    # Generate overall verdict based on best analog results
    overall = None
    if per_compound_results:
        top = per_compound_results[0]
        analogs = top.get("analogs", [])
        if analogs:
            best = analogs[0]
            if best["delta"] > 0 and best["is_in_domain"] and not best["trade_offs"]:
                overall = Verdict(
                    band="GO",
                    driver=f"Improved {top['objective']} via {best['transformation']}",
                    confidence="high",
                    rationale=f"Top analog improves {top['objective']} by {best['delta']:+.2f} without trade-offs."
                )
            elif best["delta"] > 0:
                trade_off_summary = "; ".join(best["trade_offs"]) if best["trade_offs"] else "OOD prediction"
                overall = Verdict(
                    band="CONDITIONAL",
                    driver=f"Improvement with trade-offs",
                    confidence="moderate" if best["is_in_domain"] else "low",
                    rationale=f"Top analog improves {top['objective']} by {best['delta']:+.2f} but has trade-offs: {trade_off_summary}."
                )
            else:
                overall = Verdict(
                    band="NO_GO",
                    driver="No improvement found",
                    confidence="high",
                    rationale=f"No structural analog improved the {top['objective']} objective within applicability domain."
                )
        else:
            overall = Verdict(
                band="NO_GO",
                driver="No analogs generated",
                confidence="moderate",
                rationale="The analog generation engine did not produce viable candidates for this lead compound."
            )

    sections = {
        "summary": "Prescriptive Lead-Optimization Proposal showing recommended structural analogs to optimize safety margins while maintaining efficacy.",
        "disclaimer": "IN-SILICO SCREENING ONLY — These results are computational triage signals based on predicted endpoints and structural pattern matching. They are NOT regulatory determinations and cannot replace experimental studies or expert regulatory assessment."
    }
    
    return WorkflowResult(
        workflow_id="lead_optimization",
        per_compound=per_compound_results,
        overall=overall,
        sections=sections,
        warnings=list(set(warnings)),
        provenance={}
    )

W4_SPEC = WorkflowSpec(
    id="lead_optimization",
    name="Lead-Optimization Cycle",
    persona="Agro chemist (daily)",
    input_kind="series",
    default_params={
        "objective": "selectivity",
        "preserve": "efficacy",
        "n_analogs": 10,
        "analog_strategy": "default"
    },
    steps=[
        Step(name="standardize", method="standardize", applies_to="parent", params={"smiles": "$input.smiles"}),
        Step(name="environmental_fate", method="environmental_fate", applies_to="parent", params={"smiles": "$standardize.canonical"}),
        Step(name="selectivity", method="selectivity", applies_to="parent", params={"compounds": "$environmental_fate"}),
        Step(name="suggest_analogs", method="suggest_analogs", applies_to="each_compound", params={"smiles": "$standardize.canonical", "improve": "$params.objective", "strategy": "$params.analog_strategy"}),
        Step(name="analog_standardize", method="standardize", applies_to="each_tp", params={"smiles": "$suggest_analogs.smiles"}),
        Step(name="analog_fate", method="environmental_fate", applies_to="each_tp", params={"smiles": "$analog_standardize.canonical"}),
        Step(name="analog_selectivity", method="selectivity", applies_to="each_tp", params={"compounds": "$analog_fate"}),
    ],
    aggregator=w4_aggregator,
    report_template="w4_opt_proposal"
)
