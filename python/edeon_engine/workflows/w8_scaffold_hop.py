from typing import Any, List, Dict
from .contracts import WorkflowSpec, Step, WorkflowResult, Verdict
from edeon_engine.workflows.objectives import scaffold_novelty

def w8_aggregator(step_outputs: dict, params: dict) -> WorkflowResult:
    std_out = step_outputs.get("standardize", [])
    if not isinstance(std_out, list):
        std_out = [std_out]
        
    selectivity_out = step_outputs.get("selectivity") or []
    fate_out = step_outputs.get("environmental_fate") or []
    suggested_analogs_out = step_outputs.get("suggest_analogs") or []
    
    analog_std_out = step_outputs.get("analog_standardize") or []
    analog_selectivity_out = step_outputs.get("analog_selectivity") or []
    analog_fate_out = step_outputs.get("analog_fate") or []

    
    # Build original→canonical map from standardization
    analog_canonical_map = {}
    if isinstance(analog_std_out, list):
        for item in analog_std_out:
            if isinstance(item, dict) and item.get("valid") and "original" in item:
                analog_canonical_map[item["original"]] = item["canonical"]
    
    # Map analog properties by canonical SMILES for easy lookup
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
                    
    analog_fate_clean = {}
    if isinstance(analog_fate_out, list):
        for item in analog_fate_out:
            if isinstance(item, dict):
                orig = item.get("_source_smiles") or item.get("original")
                if orig:
                    canon = analog_canonical_map.get(orig, orig)
                    if isinstance(item, list) and len(item) > 0:
                        item = item[0]
                    analog_fate_clean[canon] = item

    min_novelty_dist = float(params.get("min_novelty_distance", 0.2))
    warnings = []
    per_compound_results = []
    
    for idx, parent_item in enumerate(std_out):
        if not parent_item or not parent_item.get("valid"):
            continue
        parent_smiles = parent_item["canonical"]
        parent_name = parent_item.get("name") or f"Compound {idx+1}"
        
        parent_sel = selectivity_out[idx] if idx < len(selectivity_out) else {}
        parent_fate = fate_out[idx] if idx < len(fate_out) else {}
        if isinstance(parent_sel, list) and len(parent_sel) > 0:
            parent_sel = parent_sel[0]
        if isinstance(parent_fate, list) and len(parent_fate) > 0:
            parent_fate = parent_fate[0]
            
        p_analogs = suggested_analogs_out[idx] if idx < len(suggested_analogs_out) else []
        if isinstance(p_analogs, dict) and "result" in p_analogs:
            p_analogs = p_analogs["result"]
            
        parent_min_margin = parent_sel.get("min_selectivity", 10.0) if isinstance(parent_sel, dict) else 10.0
        parent_dt50 = 30.0
        if isinstance(parent_fate, dict) and "dt50_soil" in parent_fate:
            p_dt50_val = parent_fate["dt50_soil"].get("value")
            parent_dt50 = p_dt50_val.get("numeric", 30.0) if isinstance(p_dt50_val, dict) else float(p_dt50_val or 30.0)

        ranked_hops = []
        if isinstance(p_analogs, list):
            for anal in p_analogs:
                if not isinstance(anal, dict):
                    continue
                anal_smiles = anal.get("smiles")
                transformation = anal.get("transformation", "Modification")
                
                # Fetch selectivity and fate for analog
                a_sel = analog_sel_clean.get(anal_smiles, {})
                a_fate = analog_fate_clean.get(anal_smiles, {})
                
                if not a_sel or not a_fate:
                    continue
                    
                # 1. Compute scaffold novelty
                novelty_res = scaffold_novelty(anal_smiles, parent_smiles)
                
                # Filter: must be different Murcko scaffold AND distance >= threshold
                if not novelty_res["is_novel_scaffold"] or novelty_res["novelty"] < min_novelty_dist:
                    continue
                    
                # 2. Check profile match (within tolerance)
                # E.g. selectivity must not drop below half of parent, soil persistence not double
                a_min_margin = a_sel.get("min_selectivity", 0.0)
                a_dt50 = 30.0
                if "dt50_soil" in a_fate:
                    a_dt50_val = a_fate["dt50_soil"].get("value")
                    a_dt50 = a_dt50_val.get("numeric", 30.0) if isinstance(a_dt50_val, dict) else float(a_dt50_val or 30.0)
                    
                is_profile_match = (a_min_margin >= parent_min_margin / 2.0) and (a_dt50 <= parent_dt50 * 2.0)
                
                # Novelty rank score: novelty_distance * profile_match_factor
                match_factor = 1.0 if is_profile_match else 0.2
                rank_score = novelty_res["novelty"] * match_factor
                
                ranked_hops.append({
                    "smiles": anal_smiles,
                    "transformation": transformation,
                    "novelty": novelty_res["novelty"],
                    "min_ref_distance": novelty_res["min_ref_distance"],
                    "nearest_ref_active": novelty_res["nearest_ref_active"],
                    "min_selectivity": a_min_margin,
                    "soil_dt50": a_dt50,
                    "is_profile_match": is_profile_match,
                    "rank_score": round(rank_score, 4)
                })
                
        # Sort by rank score descending
        ranked_hops.sort(key=lambda x: x["rank_score"], reverse=True)
        
        # Limit to top N
        n_limit = params.get("n_analogs", 10)
        ranked_hops = ranked_hops[:n_limit]
        
        per_compound_results.append({
            "name": parent_name,
            "smiles": parent_smiles,
            "parent_min_margin": parent_min_margin,
            "parent_dt50": parent_dt50,
            "analogs": ranked_hops
        })

    overall = None
    if per_compound_results:
        top_res = per_compound_results[0]
        top_analogs = top_res["analogs"]
        if top_analogs and top_analogs[0]["is_profile_match"]:
            band = "GO"
            driver = "Successful Scaffold-Hop Identified"
            rationale = f"Found structurally novel scaffold (Tanimoto distance: {top_analogs[0]['novelty']:.2f}) maintaining safety profile (Selectivity margin: {top_analogs[0]['min_selectivity']:.1f} vs parent {top_res['parent_min_margin']:.1f})."
        else:
            band = "CONDITIONAL"
            driver = "No clean profile-matching scaffold-hops"
            rationale = "Candidate scaffold hops were identified, but none fully match the lead's safety and environmental fate profile within tolerance."
            
        overall = Verdict(
            band=band,
            driver=driver,
            confidence="high",
            rationale=rationale
        )

    sections = {
        "summary": "Scaffold-Hop & Chemistry Novelty Explorer dossier mapping structurally distinct Bemis-Murcko scaffolds that retain safety profiles.",
        "legal_disclaimer": "STRUCTURAL HEURISTIC ONLY — This is a chemical/structural similarity assessment representing mathematical distance from a lead molecule. This is NOT a freedom-to-operate (FTO), patentability, or legal novelty determination. Edeon reports structural distance metrics solely as discovery heuristics and does not query patent databases or perform legal assessments.",
        "disclaimer": "IN-SILICO SCREENING ONLY — These results are computational triage signals based on predicted endpoints and structural pattern matching. They are NOT regulatory determinations and cannot replace experimental studies or expert regulatory assessment."
    }

    return WorkflowResult(
        workflow_id="scaffold_hop",
        per_compound=per_compound_results,
        overall=overall,
        sections=sections,
        warnings=list(set(warnings)),
        provenance={}
    )

W8_SPEC = WorkflowSpec(
    id="scaffold_hop",
    name="Scaffold-Hop / Novelty Explorer",
    persona="Discovery / IP strategy",
    input_kind="single",
    default_params={
        "min_novelty_distance": 0.2,
        "n_analogs": 10,
        "analog_strategy": "default"
    },
    steps=[
        Step(name="standardize", method="standardize", applies_to="parent", params={"smiles": "$input.smiles"}),
        Step(name="selectivity", method="selectivity", applies_to="each_compound", params={"compounds": [{"smiles": "$standardize.canonical"}]}),
        Step(name="environmental_fate", method="environmental_fate", applies_to="each_compound", params={"smiles": ["$standardize.canonical"]}),
        Step(name="suggest_analogs", method="suggest_analogs", applies_to="each_compound", params={"smiles": "$standardize.canonical", "improve": "toxicity", "strategy": "$params.analog_strategy"}),
        Step(name="analog_standardize", method="standardize", applies_to="each_tp", params={"smiles": "$suggest_analogs.smiles"}),
        Step(name="analog_selectivity", method="selectivity", applies_to="each_tp", params={"compounds": [{"smiles": "$analog_standardize.canonical"}]}),
        Step(name="analog_fate", method="environmental_fate", applies_to="each_tp", params={"smiles": ["$analog_standardize.canonical"]})
    ],
    aggregator=w8_aggregator,
    report_template="w8_scaffold_hop"
)
