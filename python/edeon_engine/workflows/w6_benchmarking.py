from typing import Any, List, Dict
from .contracts import WorkflowSpec, Step, WorkflowResult, Verdict
from edeon_engine.reference.reference_library import reference_lookup

def compare_values(cand_val: float, ref_val: float, axis: str) -> str:
    """
    Compares candidate value to reference value for a given axis.
    Returns: "better" | "comparable" | "worse"
    """
    if cand_val is None or ref_val is None:
        return "comparable"
        
    # Lower is better for persistence (soil_dt50)
    if axis in ["soil_dt50", "dt50_soil"]:
        if cand_val < ref_val / 1.5:
            return "better"
        elif cand_val > ref_val * 1.5:
            return "worse"
        else:
            return "comparable"
            
    # Higher is better for toxicity endpoints (safety margins or LD50/LC50 values)
    elif "ld50" in axis or "lc50" in axis or "ec50" in axis or "selectivity" in axis:
        if cand_val > ref_val * 1.5:
            return "better"
        elif cand_val < ref_val / 1.5:
            return "worse"
        else:
            return "comparable"
            
    # Higher Koc means more sorption, less leaching (safer)
    elif axis in ["soil_koc", "koc"]:
        if cand_val > ref_val * 1.5:
            return "better"
        elif cand_val < ref_val / 1.5:
            return "worse"
        else:
            return "comparable"
            
    # Default comparison
    if abs(cand_val - ref_val) < 0.1 * ref_val:
        return "comparable"
    elif cand_val < ref_val:
        return "better" if axis == "logp" else "worse"
    else:
        return "worse" if axis == "logp" else "better"

def w6_aggregator(step_outputs: dict, params: dict) -> WorkflowResult:
    # 1. Fetch step outputs
    std_out = step_outputs.get("standardize", [])
    if not isinstance(std_out, list):
        std_out = [std_out]
        
    sel_out = step_outputs.get("selectivity", [])
    fate_out = step_outputs.get("environmental_fate", [])
    reg_risk_out = step_outputs.get("registration_risk", [])
    
    # 2. Query reference actives
    ref_by = params.get("reference_by", "use_class")
    ref_query = params.get("reference_query", "Herbicide")
    ref_limit = int(params.get("reference_limit", 5))
    
    ref_actives = reference_lookup(by=ref_by, query=ref_query, limit=ref_limit)
    
    warnings = []
    per_compound_results = []
    
    for idx, std in enumerate(std_out):
        if not std or not std.get("valid"):
            continue
        name = std.get("name") or f"Compound {idx+1}"
        smiles = std.get("canonical")
        
        # Get candidate predicted profile
        cand_sel = sel_out[idx] if idx < len(sel_out) else {}
        cand_fate = fate_out[idx] if idx < len(fate_out) else {}
        cand_risk = reg_risk_out[idx] if idx < len(reg_risk_out) else {}
        
        # Unpack lists if needed
        if isinstance(cand_sel, list) and len(cand_sel) > 0:
            cand_sel = cand_sel[0]
        if isinstance(cand_fate, list) and len(cand_fate) > 0:
            cand_fate = cand_fate[0]
        if isinstance(cand_risk, list) and len(cand_risk) > 0:
            cand_risk = cand_risk[0]
            
        # Build flat candidate profile with AD tagging
        # Axis mapping: axis_name -> {value, source_type: "predicted", ad_status: "in"|"out"}
        # IMPORTANT: Profile axes must use the same metric as reference actives
        # (raw LD50/LC50/EC50 values, NOT selectivity indices)
        cand_profile = {}
        
        # Ecotox raw values from selectivity profiles
        # Reference actives store raw LD50/LC50/EC50 values, so we extract
        # those from selectivity profiles rather than using the selectivity index
        if cand_sel and "profiles" in cand_sel:
            # Map organism names to reference axis names
            org_to_axis = {
                "Honeybee": [("bee_oral_ld50", "oral"), ("bee_contact_ld50", "contact")],
                "Fish": [("fish_lc50", None)],
                "Daphnia": [("daphnia_ec50", None)],
            }
            for p in cand_sel["profiles"]:
                org = p.get("organism", "")
                ad_status = p.get("ad_status", "in")
                # Use predicted_value (raw ecotox value) if available,
                # falling back to selectivity_index as last resort
                raw_val = p.get("predicted_value") or p.get("value")
                if raw_val is not None and org in org_to_axis:
                    for axis_name, route in org_to_axis[org]:
                        cand_profile[axis_name] = {
                            "value": float(raw_val),
                            "source_type": "predicted",
                            "ad_status": ad_status,
                            "source_ref": "edeon_engine_v1.0"
                        }
                
        # Fate values
        if cand_fate:
            # soil_dt50
            dt50_env = cand_fate.get("dt50_soil", {})
            if isinstance(dt50_env, dict):
                dt50_val = dt50_env.get("value", {})
                dt50_numeric = dt50_val.get("numeric") if isinstance(dt50_val, dict) else dt50_val
                if dt50_numeric is not None:
                    cand_profile["soil_dt50"] = {
                        "value": float(dt50_numeric),
                        "source_type": "predicted",
                        "ad_status": dt50_env.get("ad_status", "in"),
                        "source_ref": "edeon_engine_v1.0"
                    }
                else:
                    warnings.append(f"Soil DT50 prediction unavailable for candidate '{name}'.")
            # soil_koc
            koc_env = cand_fate.get("koc", {})
            if isinstance(koc_env, dict):
                koc_val = koc_env.get("value", {})
                koc_numeric = koc_val.get("numeric") if isinstance(koc_val, dict) else koc_val
                if koc_numeric is not None:
                    cand_profile["soil_koc"] = {
                        "value": float(koc_numeric),
                        "source_type": "predicted",
                        "ad_status": koc_env.get("ad_status", "in"),
                        "source_ref": "edeon_engine_v1.0"
                    }
                else:
                    warnings.append(f"Soil Koc prediction unavailable for candidate '{name}'.")
            # logp
            logp_env = cand_fate.get("log_kow", {})
            if isinstance(logp_env, dict):
                logp_val = logp_env.get("value", {})
                logp_numeric = logp_val.get("numeric") if isinstance(logp_val, dict) else logp_val
                if logp_numeric is not None:
                    cand_profile["logp"] = {
                        "value": float(logp_numeric),
                        "source_type": "predicted",
                        "ad_status": logp_env.get("ad_status", "in"),
                        "source_ref": "edeon_engine_v1.0"
                    }
                else:
                    warnings.append(f"LogP prediction unavailable for candidate '{name}'.")

        # Compare vs each reference active
        comparisons = []
        for ref in ref_actives:
            ref_meta = ref["active"]
            ref_prof_list = ref["profile"]
            
            ref_vals = {p["axis"]: p for p in ref_prof_list}
            
            ref_comparison_axes = {}
            better_count = 0
            worse_count = 0
            
            # Like-for-like axis comparison:
            # candidate and reference both use the same raw metric
            for cand_axis, ref_axis in [
                ("logp", "logp"),
                ("soil_dt50", "soil_dt50"),
                ("soil_koc", "soil_koc"),
                ("bee_oral_ld50", "bee_oral_ld50"),
                ("bee_contact_ld50", "bee_contact_ld50"),
                ("fish_lc50", "fish_lc50"),
                ("daphnia_ec50", "daphnia_ec50")
            ]:
                if cand_axis in cand_profile and ref_axis in ref_vals:
                    c_data = cand_profile[cand_axis]
                    r_data = ref_vals[ref_axis]
                    
                    c_val = c_data["value"]
                    r_val = r_data["value"]
                    
                    pos = compare_values(c_val, r_val, cand_axis)
                    if pos == "better":
                        better_count += 1
                    elif pos == "worse":
                        worse_count += 1
                        
                    ref_comparison_axes[cand_axis] = {
                        "candidate_value": c_val,
                        "candidate_source": "predicted",
                        "candidate_ad": c_data["ad_status"],
                        "reference_value": r_val,
                        "reference_source": r_data["source_type"],
                        "reference_ref": r_data["source_ref"],
                        "comparison": pos # "better" | "comparable" | "worse"
                    }
                    
                    if c_data["ad_status"] in ["out", "out_of_domain"]:
                        warnings.append(f"Comparison on axis '{cand_axis}' is low confidence due to candidate being out of domain.")
            
            comparisons.append({
                "reference_id": ref_meta["id"],
                "reference_name": ref_meta["name"],
                "reference_smiles": ref_meta["smiles"],
                "reference_moa": ref_meta["moa_group"],
                "axes": ref_comparison_axes,
                "better_count": better_count,
                "worse_count": worse_count
            })

        # Generate narrative summary
        better_actives = [c["reference_name"] for c in comparisons if c["better_count"] > c["worse_count"]]
        worse_actives = [c["reference_name"] for c in comparisons if c["worse_count"] > c["better_count"]]
        
        if better_actives:
            narrative = f"Candidate '{name}' demonstrates an improved safety profile compared to marketed active standards: {', '.join(better_actives)}."
        elif worse_actives:
            narrative = f"Candidate '{name}' exhibits liabilities compared to reference standard: {', '.join(worse_actives)}."
        else:
            narrative = f"Candidate '{name}' shows comparable performance and safety profiles to standard reference actives."
            
        per_compound_results.append({
            "name": name,
            "smiles": smiles,
            "candidate_profile": cand_profile,
            "comparisons": comparisons,
            "narrative": narrative,
            "verdict": {
                "band": "GO" if len(better_actives) > 0 else "CONDITIONAL" if len(worse_actives) == 0 else "NO_GO",
                "driver": "Competitive Benchmarking Position",
                "confidence": "low" if any("out" in c["candidate_ad"] for comp in comparisons for c in comp["axes"].values()) else "high",
                "rationale": narrative
            }
        })

    overall = None
    if per_compound_results:
        top_res = per_compound_results[0]
        overall = Verdict(
            band=top_res["verdict"]["band"],
            driver=top_res["verdict"]["driver"],
            confidence=top_res["verdict"]["confidence"],
            rationale=top_res["verdict"]["rationale"]
        )

    sections = {
        "summary": "Comparative Benchmarking dossier aligning candidate structures against curated reference-active databases on fate, persistence, and ecotoxicity axes.",
        "reference_actives_queried": [r["active"]["name"] for r in ref_actives],
        "disclaimer": "IN-SILICO SCREENING ONLY — These results are computational triage signals based on predicted endpoints and structural pattern matching. They are NOT regulatory determinations and cannot replace experimental studies or expert regulatory assessment."
    }

    return WorkflowResult(
        workflow_id="comparative_benchmarking",
        per_compound=per_compound_results,
        overall=overall,
        sections=sections,
        warnings=list(set(warnings)),
        provenance={}
    )

W6_SPEC = WorkflowSpec(
    id="comparative_benchmarking",
    name="Comparative Benchmarking",
    persona="Management / competitive",
    input_kind="single",
    default_params={
        "reference_by": "use_class",
        "reference_query": "Herbicide",
        "reference_limit": 3
    },
    steps=[
        Step(name="standardize", method="standardize", applies_to="parent", params={"smiles": "$input.smiles"}),
        Step(name="environmental_fate", method="environmental_fate", applies_to="each_compound", params={"smiles": ["$standardize.canonical"]}),
        Step(name="selectivity", method="selectivity", applies_to="each_compound", params={"compounds": [{"smiles": "$standardize.canonical"}]}),
        Step(name="registration_risk", method="registration_risk", applies_to="each_compound", params={"smiles": "$standardize.canonical"})
    ],
    aggregator=w6_aggregator,
    report_template="w6_comparison"
)
