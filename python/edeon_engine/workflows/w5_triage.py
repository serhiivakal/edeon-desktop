from typing import Any, List, Dict
from .contracts import WorkflowSpec, Step, WorkflowResult, Verdict
from .presets import MPO_PRESETS
from edeon_engine.workflows.objectives import get_bemis_murcko_scaffold

def w5_aggregator(step_outputs: dict, params: dict) -> WorkflowResult:
    # 1. Fetch step outputs
    std_out = step_outputs.get("standardize", [])
    if not isinstance(std_out, list):
        std_out = [std_out]
        
    prop_out = step_outputs.get("compute_properties", [])
    tice_out = step_outputs.get("pesticide_likeness") or []
    pains_out = step_outputs.get("filter_pains") or []
    selectivity_out = step_outputs.get("selectivity") or []
    mpo_out = step_outputs.get("mpo_score") or []
    div_indices = step_outputs.get("diversity_select") or []


    # Map survivors list in index order to resolve diversity indices back to original indices
    survivors = []
    for idx, std in enumerate(std_out):
        if not std or not std.get("valid"):
            continue
        # Check if the compound survived both gates (i.e. did not get filtered to None downstream)
        # Note: both tice_out and pains_out have values for survivors, and expensive steps like selectivity run only on them.
        is_survivor = True
        if idx < len(tice_out) and (tice_out[idx] is None or (isinstance(tice_out[idx], dict) and tice_out[idx].get("level") == "Low")):
            is_survivor = False
        if idx < len(pains_out) and (pains_out[idx] is None or (isinstance(pains_out[idx], dict) and (pains_out[idx].get("pains") or pains_out[idx].get("reactive")))):
            is_survivor = False
            
        if is_survivor:
            survivors.append({"index": idx, "smiles": std["canonical"]})

    # Map diversity indices (relative to survivors) to original indices
    selected_original_indices = set()
    for div_i in div_indices:
        if div_i < len(survivors):
            selected_original_indices.add(survivors[div_i]["index"])

    warnings = []
    per_compound_results = []
    scaffolds_in_shortlist = set()

    for idx, std in enumerate(std_out):
        name = std.get("name") if std else f"Compound {idx+1}"
        smiles = std.get("canonical") if std else ""
        
        # Get intermediate values
        tice_res = tice_out[idx] if idx < len(tice_out) else None
        pains_res = pains_out[idx] if idx < len(pains_out) else None
        sel_res = selectivity_out[idx] if idx < len(selectivity_out) else None
        mpo_res = mpo_out[idx] if idx < len(mpo_out) else None
        
        # Safe unwrapping of lists
        if isinstance(tice_res, list) and len(tice_res) > 0:
            tice_res = tice_res[0]
        if isinstance(pains_res, list) and len(pains_res) > 0:
            pains_res = pains_res[0]
        if isinstance(sel_res, list) and len(sel_res) > 0:
            sel_res = sel_res[0]
        if isinstance(mpo_res, list) and len(mpo_res) > 0:
            mpo_res = mpo_res[0]

        # Determine if it is a survivor
        is_survivor = any(s["index"] == idx for s in survivors)
        is_selected_diversity = idx in selected_original_indices
        
        # MPO score and properties
        mpo_score = mpo_res.get("score", 0.0) if mpo_res else 0.0
        mpo_category = mpo_res.get("rank_category", "Deprioritize") if mpo_res else "Deprioritize"
        
        # Chemical properties
        p_props = prop_out[idx] if idx < len(prop_out) else {}
        mw = p_props.get("mol_weight", 0.0) if p_props else 0.0
        logp = p_props.get("logp", 0.0) if p_props else 0.0
        
        # Scaffold
        scf = get_bemis_murcko_scaffold(smiles) if smiles else ""

        # Flags & Alerts
        pains_flagged = False
        reactive_flagged = False
        if pains_res:
            pains_flagged = pains_res.get("pains", False)
            reactive_flagged = pains_res.get("reactive", False)
            
        tice_level = tice_res.get("level", "Low") if tice_res else "Low"
        min_sel = sel_res.get("min_selectivity", 0.0) if sel_res else 0.0
        
        # Determine Tiering
        # - Priority: Survivor + Diversity Selected + MPO >= 6.0
        # - Consider: Survivor + (Diversity Selected or MPO >= 4.5)
        # - Deprioritized: Dropped by gates or low MPO
        if not is_survivor:
            tier = "deprioritized"
            if tice_level == "Low":
                verdict_band = "NO_GO"
                verdict_driver = "Low pesticide likeness (Tice violations)"
                verdict_rationale = f"Compound violated pesticide-likeness rules: {', '.join(tice_res.get('violations', [])) if tice_res else ''}"
            else:
                verdict_band = "NO_GO"
                verdict_driver = "Structural alerts flagged"
                alerts = []
                if pains_flagged: alerts.append("PAINS")
                if reactive_flagged: alerts.append("reactive alert")
                verdict_rationale = f"Compound flagged for structural alerts: {', '.join(alerts)}"
        else:
            if is_selected_diversity and mpo_score >= 6.0:
                tier = "priority"
                verdict_band = "GO"
                verdict_driver = "Priority Candidate"
                verdict_rationale = f"Highly diverse scaffold representation and excellent MPO profile (Score: {mpo_score})."
                if scf: scaffolds_in_shortlist.add(scf)
            elif is_selected_diversity or mpo_score >= 4.5:
                tier = "consider"
                verdict_band = "CONDITIONAL"
                verdict_driver = "Consider Candidate"
                verdict_rationale = f"Moderate MPO profile (Score: {mpo_score}) or represented in diverse structural down-sampling."
                if scf: scaffolds_in_shortlist.add(scf)
            else:
                tier = "deprioritized"
                verdict_band = "NO_GO"
                verdict_driver = "Low MPO Score"
                verdict_rationale = f"MPO profile score of {mpo_score} is below the threshold for discovery advancement."

        per_compound_results.append({
            "name": name,
            "smiles": smiles,
            "mol_weight": mw,
            "logp": logp,
            "mpo_score": mpo_score,
            "pesticide_likeness": tice_level,
            "pains_flagged": pains_flagged or reactive_flagged,
            "min_selectivity": min_sel,
            "scaffold": scf,
            "tier": tier,
            "verdict": {
                "band": verdict_band,
                "driver": verdict_driver,
                "confidence": "high",
                "rationale": verdict_rationale
            }
        })

    # Sort results: priority -> consider -> deprioritized, and by MPO score descending
    tier_weights = {"priority": 3, "consider": 2, "deprioritized": 1}
    per_compound_results.sort(key=lambda x: (tier_weights.get(x["tier"], 0), x["mpo_score"]), reverse=True)

    # Composite Verdict
    overall = None
    if per_compound_results:
        top_comp = per_compound_results[0]
        overall = Verdict(
            band=top_comp["verdict"]["band"],
            driver=top_comp["verdict"]["driver"],
            confidence=top_comp["verdict"]["confidence"],
            rationale=top_comp["verdict"]["rationale"]
        )

    # Diversity statistics
    sections = {
        "summary": "Hit-to-Shortlist Triage report down-sampling raw hits into a diverse, de-risked shortlist utilizing pesticide-likeness and PAINS gates.",
        "shortlist_size": len([c for c in per_compound_results if c["tier"] in ["priority", "consider"]]),
        "unique_scaffolds_count": len(scaffolds_in_shortlist),
        "disclaimer": "IN-SILICO SCREENING ONLY — These results are computational triage signals based on predicted endpoints and structural pattern matching. They are NOT regulatory determinations and cannot replace experimental studies or expert regulatory assessment."
    }

    return WorkflowResult(
        workflow_id="hit_triage",
        per_compound=per_compound_results,
        overall=overall,
        sections=sections,
        warnings=list(set(warnings)),
        provenance={}
    )

W5_SPEC = WorkflowSpec(
    id="hit_triage",
    name="Hit-to-Shortlist Triage",
    persona="Discovery (high-frequency)",
    input_kind="library",
    default_params={
        "pest_class": "Herbicide",
        "shortlist_size": 50,
        "weights": MPO_PRESETS["Herbicide"]["weights"]
    },
    steps=[
        Step(name="standardize", method="standardize", applies_to="parent", params={"smiles": "$input.smiles"}),
        Step(name="compute_properties", method="compute_properties", applies_to="parent", params={"smiles": "$standardize.canonical"}),
        Step(name="pesticide_likeness", method="pesticide_likeness", applies_to="each_compound", gate=True, params={"compounds": ["$compute_properties"]}),
        Step(name="filter_pains", method="filter_pains", applies_to="each_compound", gate=True, params={"smiles": ["$standardize.canonical"]}),
        Step(name="selectivity", method="selectivity", applies_to="each_compound", expensive=True, params={"compounds": [{"smiles": "$standardize.canonical"}]}),
        Step(name="diversity_select", method="diversity_select", applies_to="parent", params={"smiles": "$survivors.smiles", "target_size": "$params.shortlist_size", "algorithm": "bemis_murcko"}),
        Step(name="mpo_score", method="mpo_score", applies_to="parent", params={
            "properties": "$compute_properties",
            "tice_results": "$pesticide_likeness",
            "selectivity_results": "$selectivity",
            "weights": "$params.weights"
        })
    ],
    aggregator=w5_aggregator,
    report_template="w5_shortlist"
)
