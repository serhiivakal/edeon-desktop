"""
Edeon Engine — Retrosynthesis & Synthesizability JSON-RPC Handlers
"""

from typing import Dict, Any, List
from .sascore import calculate_sascore, calculate_sascore_batch
from .aizynth_runner import run_aizynth_route_search
from .feasibility import compute_feasibility
from .stock import get_stock_manager


def handle_retro_sascore(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for retro.sascore (batch fast BR-SAScore).

    params: { "smiles": [str] }
    """
    smiles_list = params.get("smiles", [])
    if isinstance(smiles_list, str):
        smiles_list = [smiles_list]

    scores = calculate_sascore_batch(smiles_list)
    return {
        "ok": True,
        "scores": scores
    }


def handle_retro_route_search(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for retro.route_search.

    params: { "smiles": str, "time_limit_s": int, "max_routes": int, "stock_id": str }
    """
    smiles = params.get("smiles", "")
    time_limit_s = int(params.get("time_limit_s", 30))
    max_routes = int(params.get("max_routes", 5))
    stock_id = params.get("stock_id", "agrochem_default")

    sa_score = calculate_sascore(smiles)
    route_res = run_aizynth_route_search(
        smiles, time_limit_s=time_limit_s, max_routes=max_routes, stock_id=stock_id
    )

    if not route_res.get("ok"):
        return route_res

    feasibility_score, tier = compute_feasibility(
        sa_score,
        route_res.get("solved", False),
        route_res.get("leaves_in_stock_frac", 0.0),
        route_res.get("n_steps", 1)
    )

    return {
        "ok": True,
        "smiles": smiles,
        "sa_score": sa_score,
        "solved": route_res.get("solved", False),
        "feasibility_score": feasibility_score,
        "tier": tier,
        "n_steps": route_res.get("n_steps", 0),
        "route_depth": route_res.get("route_depth", 0),
        "leaves_in_stock_frac": route_res.get("leaves_in_stock_frac", 0.0),
        "route_tree": route_res.get("route_tree", {}),
        "building_blocks": route_res.get("building_blocks", []),
        "engine_used": route_res.get("engine_used", "unknown")
    }


def handle_retro_gate_batch(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for retro.gate_batch.

    params: { "smiles": [str], "sa_threshold": float, "route_search_top_k": int, "stock_id": str }
    """
    smiles_list = params.get("smiles", [])
    sa_threshold = float(params.get("sa_threshold", 0.4))
    route_search_top_k = int(params.get("route_search_top_k", 5))
    stock_id = params.get("stock_id", "agrochem_default")

    results = []
    for idx, s in enumerate(smiles_list):
        sa = calculate_sascore(s)
        if idx < route_search_top_k or sa >= sa_threshold:
            full_res = handle_retro_route_search({"smiles": s, "stock_id": stock_id})
            results.append({
                "smiles": s,
                "sa_score": sa,
                "feasibility_score": full_res.get("feasibility_score", sa),
                "tier": full_res.get("tier", "amber"),
                "solved": full_res.get("solved", False),
            })
        else:
            feasibility_score, tier = compute_feasibility(sa, False, 0.0, 1)
            results.append({
                "smiles": s,
                "sa_score": sa,
                "feasibility_score": feasibility_score,
                "tier": tier,
                "solved": False,
            })

    return {
        "ok": True,
        "results": results
    }


def handle_retro_import_stock(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for retro.import_stock.

    params: { "path": str, "name": str }
    """
    path = params.get("path", "")
    name = params.get("name", "user_stock")

    mgr = get_stock_manager()
    n_blocks = mgr.import_stock_file(path, name)

    return {
        "ok": True,
        "stock_id": name,
        "n_blocks": n_blocks
    }
