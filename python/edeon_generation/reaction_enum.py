"""
Edeon Engine — Reaction-Based Combinatorial Enumeration
"""

import os
import json
from typing import List, Dict, Any, Optional
from rdkit import Chem
from rdkit.Chem import AllChem

from edeon_data.pains_filter import filter_pains_batch
from edeon_engine.tice_rules import pesticide_likeness_batch
from edeon_retro.ipc_handlers import handle_retro_gate_batch


_TEMPLATES_CACHE: Optional[List[Dict[str, Any]]] = None


def load_reaction_templates() -> List[Dict[str, Any]]:
    """Load reaction templates from data/reactions.json."""
    global _TEMPLATES_CACHE
    if _TEMPLATES_CACHE is not None:
        return _TEMPLATES_CACHE

    json_path = os.path.join(os.path.dirname(__file__), "data", "reactions.json")
    if not os.path.exists(json_path):
        return []

    with open(json_path, "r", encoding="utf-8") as f:
        _TEMPLATES_CACHE = json.load(f)

    return _TEMPLATES_CACHE or []


def enumerate_reaction_products(
    template_id: str,
    core_smiles: Optional[str] = None,
    reagents: Optional[List[str]] = None,
    max_products: int = 500,
    apply_filters: Optional[Dict[str, bool]] = None,
    retro_gate: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Combinatorially enumerate reaction products for a chosen reaction template.

    Args:
        template_id: Reaction template ID (e.g. 'amide_coupling', 'suzuki_coupling')
        core_smiles: Optional query core SMILES
        reagents: Optional custom building block reagent list
        max_products: Maximum number of products to generate
        apply_filters: {"tice": bool, "pains": bool}
        retro_gate: {"enabled": bool, "sa_threshold": float}

    Returns:
        Dict matching IPC schema.
    """
    templates = load_reaction_templates()
    tmpl = next((t for t in templates if t["id"] == template_id), None)
    if not tmpl:
        return {
            "ok": False,
            "error": f"Reaction template '{template_id}' not found"
        }

    try:
        rxn = AllChem.ReactionFromSmarts(tmpl["smarts"])
    except Exception as e:
        return {"ok": False, "error": f"Failed to compile reaction SMARTS: {str(e)}"}

    building_blocks = reagents if reagents and len(reagents) > 0 else tmpl.get("default_reagents", [])
    if core_smiles and core_smiles not in building_blocks:
        building_blocks = [core_smiles] + building_blocks

    valid_mols = []
    for b in building_blocks:
        m = Chem.MolFromSmiles(b)
        if m:
            valid_mols.append(m)

    if not valid_mols:
        return {"ok": False, "error": "No valid reactant molecules available"}

    product_smiles_set = set()

    # Combinatorial reactant matching: 2-component reaction
    for m1 in valid_mols:
        for m2 in valid_mols:
            if len(product_smiles_set) >= max_products:
                break
            try:
                ps = rxn.RunReactants((m1, m2))
                for p_tuple in ps:
                    for p in p_tuple:
                        try:
                            Chem.SanitizeMol(p)
                            p_smi = Chem.MolToSmiles(p, canonical=True)
                            if p_smi and len(p_smi) > 3:
                                product_smiles_set.add(p_smi)
                        except Exception:
                            pass
            except Exception:
                continue

    raw_products = list(product_smiles_set)[:max_products]
    n_generated = len(raw_products)

    if n_generated == 0:
        return {
            "ok": True,
            "products": [],
            "n_generated": 0,
            "n_passed": 0
        }

    # Filters
    filtered_smiles = raw_products
    filters = apply_filters or {"tice": True, "pains": True}

    if filters.get("pains"):
        pains_res = filter_pains_batch(filtered_smiles)
        filtered_smiles = [
            filtered_smiles[i]
            for i in range(len(pains_res))
            if pains_res[i].get("valid") and not pains_res[i].get("pains")
        ]

    if filters.get("tice"):
        compounds = [{"smiles": s} for s in filtered_smiles]
        tice_res = pesticide_likeness_batch(compounds)
        filtered_smiles = [
            filtered_smiles[i]
            for i in range(len(tice_res))
            if tice_res[i].get("passed", True) or tice_res[i].get("verdict") != "Disqualified"
        ]

    # Retrosynthesis synthesizability gating (G1 integration)
    retro_enabled = retro_gate.get("enabled", True) if retro_gate else True
    sa_threshold = float(retro_gate.get("sa_threshold", 0.4)) if retro_gate else 0.4

    if retro_enabled and filtered_smiles:
        gate_res = handle_retro_gate_batch({
            "smiles": filtered_smiles,
            "sa_threshold": sa_threshold,
            "route_search_top_k": min(10, len(filtered_smiles))
        })
        gating_map = {item["smiles"]: item for item in gate_res.get("results", [])}
    else:
        gating_map = {}

    products = []
    for s in filtered_smiles:
        gate_info = gating_map.get(s, {})
        products.append({
            "smiles": s,
            "passed_filters": True,
            "sa_score": gate_info.get("sa_score"),
            "feasibility_score": gate_info.get("feasibility_score"),
            "tier": gate_info.get("tier", "amber"),
            "solved": gate_info.get("solved", False)
        })

    return {
        "ok": True,
        "template_id": template_id,
        "products": products,
        "n_generated": n_generated,
        "n_passed": len(products)
    }
