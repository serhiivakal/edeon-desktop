from typing import Any, List, Dict
from .contracts import WorkflowSpec, Step, WorkflowResult, Verdict
from .verdict import map_ad_to_confidence, resolve_confidence_label

def w3_aggregator(step_outputs: dict, params: dict) -> WorkflowResult:
    # Parents list
    standardize_out = step_outputs.get("standardize", [])
    if not isinstance(standardize_out, list):
        standardize_out = [standardize_out]
        
    fate_out = step_outputs.get("environmental_fate", [])
    selectivity_out = step_outputs.get("selectivity", [])
    tp_out = step_outputs.get("transformation_products", [])
    
    # TPs list
    tp_std_out = step_outputs.get("tp_standardize", [])
    tp_fate_out = step_outputs.get("tp_fate", [])
    tp_selectivity_out = step_outputs.get("tp_selectivity", [])
    
    # Map TP standardizations and results by canonical/original smiles
    tp_fate_by_smiles = {}
    if isinstance(tp_fate_out, list):
        for item in tp_fate_out:
            if isinstance(item, dict) and "original" in item:
                tp_fate_by_smiles[item["original"]] = item
                
    tp_canonical_map = {}
    if isinstance(tp_std_out, list):
        for item in tp_std_out:
            if isinstance(item, dict) and item.get("valid"):
                tp_canonical_map[item["original"]] = item["canonical"]

    # We index TP fate and selectivity by canonical SMILES
    tp_fate_by_canonical = {}
    for orig, item in tp_fate_by_smiles.items():
        canon = tp_canonical_map.get(orig, orig)
        tp_fate_by_canonical[canon] = item
        
    tp_selectivity_by_canonical = {}
    if isinstance(tp_selectivity_out, list) and isinstance(tp_std_out, list):
        # Build original→canonical map from standardization
        tp_orig_to_canon = {}
        for item in tp_std_out:
            if isinstance(item, dict) and item.get("valid") and "original" in item:
                tp_orig_to_canon[item["original"]] = item["canonical"]
        # Key selectivity by canonical SMILES using the original field
        for item in tp_selectivity_out:
            if isinstance(item, dict):
                orig = item.get("_source_smiles") or item.get("original")
                if orig:
                    canon = tp_orig_to_canon.get(orig, orig)
                    tp_selectivity_by_canonical[canon] = item
                elif "min_selectivity" in item:
                    # Fallback: try positional alignment as last resort
                    pass

    warnings = []
    per_compound_results = []
    
    for idx, parent_item in enumerate(standardize_out):
        if not isinstance(parent_item, dict) or not parent_item.get("valid"):
            continue
        parent_smiles = parent_item["canonical"]
        parent_name = parent_item.get("name") or f"Compound {idx+1}"
        
        # Get parent fate & selectivity
        p_fate = fate_out[idx] if idx < len(fate_out) else {}
        p_sel = selectivity_out[idx] if idx < len(selectivity_out) else {}
        
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
                        
        flagged_tps = []
        # Track minimum AD confidence across all TP predictions used
        min_conf_score = 3  # start at "high"
        
        for tp in valid_tps:
            tp_smiles = tp.get("smiles")
            tp_prob = tp.get("probability", 1.0)
            tp_route = tp.get("route", "")
            tp_rule = tp.get("rule", "")
            
            # Look up fate and tox
            tp_f = tp_fate_by_canonical.get(tp_smiles, {})
            tp_s = tp_selectivity_by_canonical.get(tp_smiles, {})
            
            # Track AD status of TP predictions for confidence resolution
            for endpoint_key in ["dt50_soil", "koc", "bcf"]:
                tp_ad = tp_f.get(endpoint_key, {}).get("ad_status", "unknown")
                min_conf_score = min(min_conf_score, map_ad_to_confidence(tp_ad))
            
            # Compare persistent/bioaccumulative/mobile/toxicity deltas vs parent
            liabilities = []
            
            # 1. Persistence DT50
            p_dt50 = p_fate.get("dt50_soil", {}).get("value")
            tp_dt50 = tp_f.get("dt50_soil", {}).get("value")
            if p_dt50 is not None and tp_dt50 is not None:
                if tp_dt50 > p_dt50 * 1.5 or tp_dt50 > 90:
                    liabilities.append(f"Persistence (DT50: {tp_dt50:.0f}d vs parent {p_dt50:.0f}d)")
                    
            # 2. Mobility Koc
            p_koc = p_fate.get("koc", {}).get("value")
            tp_koc = tp_f.get("koc", {}).get("value")
            if p_koc is not None and tp_koc is not None:
                if tp_koc < p_koc / 1.5 or tp_koc < 75:
                    liabilities.append(f"Mobility (Koc: {tp_koc:.0f} vs parent {p_koc:.0f})")
                    
            # 3. Bioaccumulation BCF
            p_bcf = p_fate.get("bcf", {}).get("value")
            tp_bcf = tp_f.get("bcf", {}).get("value")
            if p_bcf is not None and tp_bcf is not None:
                if tp_bcf > p_bcf * 1.5 or tp_bcf > 2000:
                    liabilities.append(f"Bioaccumulation (BCF: {tp_bcf:.0f} vs parent {p_bcf:.0f})")
                    
            # 4. Toxicity
            p_min_sel = p_sel.get("min_selectivity", 10.0)
            tp_min_sel = tp_s.get("min_selectivity", 10.0)
            if tp_min_sel < p_min_sel / 1.5:
                liabilities.append(f"Selectivity margin drop ({tp_min_sel:.1f} vs parent {p_min_sel:.1f})")
                
            if liabilities:
                flagged_tps.append({
                    "smiles": tp_smiles,
                    "probability": tp_prob,
                    "route": tp_route,
                    "rule": tp_rule,
                    "liabilities": liabilities,
                    "severity": len(liabilities) * tp_prob
                })
                
        # Sort flagged TPs by severity
        flagged_tps.sort(key=lambda x: x["severity"], reverse=True)
        
        # Resolve confidence from AD status of all TP predictions used
        # TPs are inherently speculative; never claim high confidence if
        # any underlying prediction was out-of-domain
        confidence = resolve_confidence_label(min_conf_score)
        if not valid_tps:
            # No TPs were generated — confidence is about the TP generation
            # step itself, not the predictions, so moderate is appropriate
            confidence = "moderate"
        
        if flagged_tps:
            band = "parent-OK-TP-liability"
            driver = "metabolite liabilities detected"
            rationale = f"Parent compound cleared basic checkpoints, but {len(flagged_tps)} transformation product(s) introduce elevated liabilities."
        else:
            band = "clean"
            driver = "no major TP liabilities"
            rationale = "No transformation products exceeded parent liabilities on persistency, mobility, bioaccumulation or toxicity."
            
        if confidence == "low":
            warnings.append(f"Low confidence for TP assessment of '{parent_name}' due to out-of-domain predictions on transformation products.")
            
        per_compound_results.append({
            "name": parent_name,
            "smiles": parent_smiles,
            "verdict": {
                "band": band,
                "driver": driver,
                "confidence": confidence,
                "rationale": rationale
            },
            "flagged_tps": flagged_tps,
            "total_tps": len(valid_tps)
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
        "summary": "Transformation product liability sweep showing parent compounds and their associated metabolites with degradation routes and liability deltas.",
        "disclaimer": "IN-SILICO SCREENING ONLY — These results are computational triage signals based on predicted endpoints and structural pattern matching. They are NOT regulatory determinations and cannot replace experimental studies or expert regulatory assessment."
    }
    
    return WorkflowResult(
        workflow_id="tp_liability",
        per_compound=per_compound_results,
        overall=overall_verdict,
        sections=sections,
        warnings=list(set(warnings)),
        provenance={}
    )

W3_SPEC = WorkflowSpec(
    id="tp_liability",
    name="Transformation-Product Liability Sweep",
    persona="Env. fate / Reg.",
    input_kind="single",
    default_params={
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
        Step(name="tp_fate", method="environmental_fate", applies_to="each_tp", params={"smiles": "$tp_standardize.canonical"}),
        Step(name="tp_selectivity", method="selectivity", applies_to="each_tp", params={"compounds": "$tp_fate"}),
    ],
    aggregator=w3_aggregator,
    report_template="w3_tp_report"
)
