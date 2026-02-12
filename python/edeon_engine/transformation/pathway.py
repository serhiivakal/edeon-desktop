import sys
import os
import sygma
from rdkit import Chem
from edeon_engine.fate.parent_fate import predict_compound_fate
from edeon_engine.properties import compute_properties_single
from edeon_engine.toxicity import predict_toxicity
from edeon_engine.transformation.rules import RULES_TXT_PATH

def check_risk_increase(parent_fate: dict, parent_tox: dict, tp_fate: dict, tp_tox: dict) -> bool:
    """Check if the transformation product (TP) has a higher risk profile than its parent.
    
    A TP is considered higher risk if:
      - It is more persistent (higher Soil DT50 by > 10%)
      - It is more bioaccumulative (higher BCF by > 10%)
      - It is more mobile/leachable (higher GUS leaching score by > 10%)
      - It is more toxic overall (e.g. Low -> Med, Med -> High)
    """
    try:
        # Check persistence (DT50)
        p_dt50 = parent_fate.get("dt50_soil", {}).get("value")
        t_dt50 = tp_fate.get("dt50_soil", {}).get("value")
        if p_dt50 is not None and t_dt50 is not None and t_dt50 > p_dt50 * 1.1:
            return True
            
        # Check bioaccumulation (BCF)
        p_bcf = parent_fate.get("bcf", {}).get("value")
        t_bcf = tp_fate.get("bcf", {}).get("value")
        if p_bcf is not None and t_bcf is not None and t_bcf > p_bcf * 1.1:
            return True
            
        # Check mobility (GUS index)
        p_gus = parent_fate.get("gus", {}).get("value")
        t_gus = tp_fate.get("gus", {}).get("value")
        if p_gus is not None and t_gus is not None and t_gus > p_gus * 1.1:
            return True

        # Check toxicity level
        tox_levels = {"Low": 0, "Med": 1, "High": 2}
        p_level = tox_levels.get(parent_tox.get("overall_level", "Low"), 0)
        t_level = tox_levels.get(tp_tox.get("overall_level", "Low"), 0)
        if t_level > p_level:
            return True
    except Exception:
        pass
    return False

def predict_transformation_pathway(
    smiles: str,
    routes: list[str],
    max_depth: int = 2,
    sources: list[str] = None,
    ph: float = 6.5
) -> dict:
    """Predict transformation products and compile their DAG.
    
    Returns a dictionary with:
        - nodes: list of dicts with id, smiles, parent_id, rule, source, probability, fate, tox, risk_flag, liability_flag
        - edges: list of dicts with source, target, rule, probability
    """
    # 1. Parse parent mol
    parent_mol = Chem.MolFromSmiles(smiles)
    if parent_mol is None:
        raise ValueError("Invalid parent SMILES.")
        
    # 2. Build scenario steps based on requested routes & environmental sources
    scenario_steps = []
    if "abiotic" in routes or (sources and any(s in sources for s in ["hydrolysis", "abiotic"])):
        scenario_steps.append([RULES_TXT_PATH, 1])
    if "metabolic" in routes or (sources and "soil_microbial" in sources):
        scenario_steps.append([sygma.ruleset['phase1'], 1])
        if max_depth >= 2:
            scenario_steps.append([sygma.ruleset['phase2'], 1])
            
    if not scenario_steps:
        scenario_steps.append([RULES_TXT_PATH, 1])

    # 3. Run scenario
    sc = sygma.Scenario(scenario_steps)
    tree = sc.run(parent_mol)
    tree.calc_scores()

    # 4. Extract parent key
    parent_key = tree.parentkey
    parent_node = tree.nodes.get(parent_key)
    if not parent_node:
        raise ValueError("Failed to find parent node in SyGMa tree.")

    # 5. Precompute parent properties, fate, and toxicity
    parent_smiles = Chem.MolToSmiles(parent_node.mol)
    parent_props = compute_properties_single(parent_smiles)
    parent_fate = predict_compound_fate(parent_smiles)
    parent_tox = predict_toxicity(parent_props)

    # 6. Convert tree nodes to output nodes list and rescore
    nodes_out = []
    edges_out = []
    
    kept_keys = {parent_key}
    for ikey, node in tree.nodes.items():
        if node.score is not None and node.score >= 0.08:
            kept_keys.add(ikey)
            
    for ikey in sorted(kept_keys):
        node = tree.nodes[ikey]
        node_smiles = Chem.MolToSmiles(node.mol)
        
        node_props = compute_properties_single(node_smiles)
        node_fate = predict_compound_fate(node_smiles)
        node_tox = predict_toxicity(node_props)
        
        is_parent = (ikey == parent_key)
        
        primary_parent = None
        rule_name = None
        
        parents_filtered = {k: v for k, v in node.parents.items() if k and k != "" and k in kept_keys}
        if parents_filtered:
            first_parent_key = sorted(parents_filtered.keys())[0]
            primary_parent = first_parent_key
            rule_name = parents_filtered[first_parent_key].rulename if parents_filtered[first_parent_key] else "unknown"
        else:
            rule_name = "parent" if is_parent else "unknown"

        risk_flag = False
        liability_flag = False
        if not is_parent:
            risk_flag = check_risk_increase(parent_fate, parent_tox, node_fate, node_tox)
            liability_flag = risk_flag

        rule_source = "sygma"
        if is_parent:
            rule_source = "parent"
        elif any(w in rule_name.lower() for w in ["hydrolysis", "ester", "nitrile", "carbamate"]):
            rule_source = "hydrolysis"
        elif any(w in rule_name.lower() for w in ["dealkylation", "demethylation", "hydroxylation", "nitro"]):
            rule_source = "soil_microbial"

        nodes_out.append({
            "id": ikey,
            "smiles": node_smiles,
            "parent_id": primary_parent,
            "rule": rule_name,
            "source": rule_source,
            "probability": float(node.score) if node.score is not None else 1.0,
            "fate": node_fate,
            "tox": node_tox,
            "risk_flag": risk_flag,
            "liability_flag": liability_flag
        })
        
        for p_key, rule in node.parents.items():
            if p_key and p_key != "" and p_key in kept_keys:
                edges_out.append({
                    "source": p_key,
                    "target": ikey,
                    "rule": rule.rulename if rule else "unknown",
                    "probability": float(rule.probability) if rule else 1.0
                })

    return {
        "nodes": nodes_out,
        "edges": edges_out,
        "result": nodes_out
    }
