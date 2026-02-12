from typing import Any, List, Dict
from .contracts import WorkflowSpec, Step, WorkflowResult, Verdict
from edeon_engine.workflows.objectives import maximin_selectivity

def w7_aggregator(step_outputs: dict, params: dict) -> WorkflowResult:
    std_out = step_outputs.get("standardize", [])
    if not isinstance(std_out, list):
        std_out = [std_out]
        
    selectivity_out = step_outputs.get("selectivity") or []
    suggested_analogs_out = step_outputs.get("suggest_analogs") or []
    
    analog_std_out = step_outputs.get("analog_standardize") or []
    analog_selectivity_out = step_outputs.get("analog_selectivity") or []

    
    # Build original→canonical map from standardization
    analog_canonical_map = {}
    if isinstance(analog_std_out, list):
        for item in analog_std_out:
            if isinstance(item, dict) and item.get("valid") and "original" in item:
                analog_canonical_map[item["original"]] = item["canonical"]
    
    # Map analog selectivity results by canonical SMILES for easy lookup
    analog_sel_clean = {}
    if isinstance(analog_selectivity_out, list):
        for item in analog_selectivity_out:
            if isinstance(item, dict):
                orig = item.get("_source_smiles") or item.get("original")
                if orig:
                    canon = analog_canonical_map.get(orig, orig)
                    if isinstance(item, list) and len(item) > 0:
                        item = item[0]
                    analog_sel_clean[canon] = item

    penalize_ood = params.get("penalize_ood", True)
    warnings = []
    per_compound_results = []
    
    for idx, parent_item in enumerate(std_out):
        if not parent_item or not parent_item.get("valid"):
            continue
        parent_smiles = parent_item["canonical"]
        parent_name = parent_item.get("name") or f"Compound {idx+1}"
        
        parent_sel = selectivity_out[idx] if idx < len(selectivity_out) else {}
        if isinstance(parent_sel, list) and len(parent_sel) > 0:
            parent_sel = parent_sel[0]
            
        p_analogs = suggested_analogs_out[idx] if idx < len(suggested_analogs_out) else []
        if isinstance(p_analogs, dict) and "result" in p_analogs:
            p_analogs = p_analogs["result"]
            
        # 1. Identify limiting parent margin
        p_profiles = parent_sel.get("profiles", []) if isinstance(parent_sel, dict) else []
        parent_min_margin = parent_sel.get("min_selectivity", 999.0) if isinstance(parent_sel, dict) else 999.0
        
        limiting_organism = "Unknown"
        for p in p_profiles:
            if p.get("selectivity_index") == parent_min_margin:
                limiting_organism = p.get("organism", "Unknown")
                break
                
        # 2. Evaluate and rank structural analogs
        ranked_analogs = []
        if isinstance(p_analogs, list):
            for anal in p_analogs:
                if not isinstance(anal, dict):
                    continue
                anal_smiles = anal.get("smiles")
                transformation = anal.get("transformation", "Modification")
                
                # Fetch selectivity prediction for analog
                a_sel = analog_sel_clean.get(anal_smiles, {})
                if not a_sel:
                    continue
                    
                # Run maximin selectivity assessment
                eval_res = maximin_selectivity(a_sel, parent_sel, penalize_ood=penalize_ood)
                
                # Check for collapses or OOD
                trade_offs = []
                if eval_res["collapses_margin"]:
                    trade_offs.append("Collapses another safety margin below threshold")
                if eval_res["is_ood"]:
                    trade_offs.append("Out of Domain prediction (low confidence)")
                    
                ranked_analogs.append({
                    "smiles": anal_smiles,
                    "transformation": transformation,
                    "min_selectivity": eval_res["score"],
                    "lift": eval_res["lift"],
                    "collapses_margin": eval_res["collapses_margin"],
                    "trade_offs": trade_offs,
                    "rank_score": eval_res["final_rank_score"],
                    "is_in_domain": not eval_res["is_ood"],
                    "profiles": a_sel.get("profiles", [])
                })
                
        # Sort analogs: prioritising no margin collapses, then by rank_score (lift) descending
        ranked_analogs.sort(key=lambda x: (not x["collapses_margin"], x["rank_score"]), reverse=True)
        
        # Limit to top N
        n_limit = params.get("n_analogs", 10)
        ranked_analogs = ranked_analogs[:n_limit]
        
        per_compound_results.append({
            "name": parent_name,
            "smiles": parent_smiles,
            "parent_min_margin": parent_min_margin,
            "limiting_organism": limiting_organism,
            "parent_profiles": p_profiles,
            "analogs": ranked_analogs
        })

    overall = None
    if per_compound_results:
        top_res = per_compound_results[0]
        # Overall verdict: GO if top analog achieves lift and doesn't collapse margins, else CONDITIONAL
        top_analogs = top_res["analogs"]
        if top_analogs and top_analogs[0]["lift"] > 0 and not top_analogs[0]["collapses_margin"]:
            band = "GO"
            driver = f"Widen selectivity window via limiting margin '{top_res['limiting_organism']}'"
            rationale = f"Enables widening of the narrowest margin from {top_res['parent_min_margin']} to {top_analogs[0]['min_selectivity']} (Lift: {top_analogs[0]['lift']}x) without collapsing other margins."
        else:
            band = "CONDITIONAL"
            driver = "No clean selectivity lift"
            rationale = "No structural analogs were identified that improve the limiting safety margin without causing trade-off violations."
            
        overall = Verdict(
            band=band,
            driver=driver,
            confidence="high",
            rationale=rationale
        )

    sections = {
        "summary": "Selectivity Window Optimization report targeting the limiting non-target species safety margin using maximin multi-species objectives.",
        "disclaimer": "IN-SILICO SCREENING ONLY — These results are computational triage signals based on predicted endpoints and structural pattern matching. They are NOT regulatory determinations and cannot replace experimental studies or expert regulatory assessment."
    }

    return WorkflowResult(
        workflow_id="selectivity_optimization",
        per_compound=per_compound_results,
        overall=overall,
        sections=sections,
        warnings=list(set(warnings)),
        provenance={}
    )

W7_SPEC = WorkflowSpec(
    id="selectivity_optimization",
    name="Selectivity Window Optimization",
    persona="Ecotox / Discovery",
    input_kind="single",
    default_params={
        "penalize_ood": True,
        "n_analogs": 10,
        "analog_strategy": "default"
    },
    steps=[
        Step(name="standardize", method="standardize", applies_to="parent", params={"smiles": "$input.smiles"}),
        Step(name="selectivity", method="selectivity", applies_to="each_compound", params={"compounds": [{"smiles": "$standardize.canonical"}]}),
        Step(name="suggest_analogs", method="suggest_analogs", applies_to="each_compound", params={"smiles": "$standardize.canonical", "improve": "toxicity", "strategy": "$params.analog_strategy"}),
        Step(name="analog_standardize", method="standardize", applies_to="each_tp", params={"smiles": "$suggest_analogs.smiles"}),
        Step(name="analog_selectivity", method="selectivity", applies_to="each_tp", params={"compounds": [{"smiles": "$analog_standardize.canonical"}]})
    ],
    aggregator=w7_aggregator,
    report_template="w7_window"
)
