"""
Edeon Engine — AiZynthFinder Retrosynthesis Wrapper & Fallback Route Engine
"""

from typing import Dict, Any, List
from rdkit import Chem
from rdkit.Chem import AllChem

from .stock import get_stock_manager


# Standard retro reaction SMARTS for fallback template tree search
RETRO_TEMPLATES = [
    # Amide bond disconnection
    ("Amide Disconnection", AllChem.ReactionFromSmarts("[C:1](=[O:2])[N:3] >> [C:1](=[O:2])Cl.[N:3]")),
    # Ester bond disconnection
    ("Ester Disconnection", AllChem.ReactionFromSmarts("[C:1](=[O:2])[O:3] >> [C:1](=[O:2])Cl.[O:3]")),
    # Biaryl Suzuki disconnection
    ("Biaryl Suzuki Disconnection", AllChem.ReactionFromSmarts("[c:1]-[c:2] >> [c:1]Br.[c:2]B(O)O")),
    # Ether SNAr disconnection
    ("Ether Disconnection", AllChem.ReactionFromSmarts("[c:1]-[O:2]-[C:3] >> [c:1]F.[C:3]O")),
]


def run_aizynth_route_search(
    smiles: str,
    time_limit_s: int = 30,
    max_routes: int = 5,
    stock_id: str = "agrochem_default"
) -> Dict[str, Any]:
    """Execute retrosynthetic MCTS route search for a query compound.

    Returns dict matching IPC schema.
    """
    stock_mgr = get_stock_manager()

    # 1. Try AiZynthFinder if installed
    try:
        from aizynthfinder.finder import AiZynthFinder  # type: ignore
        finder = AiZynthFinder()
        finder.target_smiles = smiles
        finder.time_limit = time_limit_s
        finder.max_transforms = max_routes
        finder.tree_search()
        finder.build_routes()
        routes = finder.routes
        if routes:
            top_route = routes[0]
            solved = top_route.get("solved", False)
            # Extract tree and leaves
            leaves = [
                {"smiles": leaf, "in_stock": stock_mgr.is_in_stock(leaf, stock_id)}
                for leaf in top_route.get("precursors", [])
            ]
            leaves_in_stock_frac = sum(1 for l in leaves if l["in_stock"]) / max(1, len(leaves))
            return {
                "ok": True,
                "solved": solved,
                "n_steps": top_route.get("numberOfReactions", 1),
                "route_depth": top_route.get("maxDepth", 1),
                "leaves_in_stock_frac": round(leaves_in_stock_frac, 2),
                "route_tree": top_route.get("reactionTree", {}),
                "building_blocks": leaves,
                "engine_used": "aizynthfinder"
            }
    except Exception:
        pass

    # 2. Fallback Template-Based Retrosynthetic Decomposition Engine
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {
            "ok": False,
            "error": f"Invalid SMILES string: {smiles}"
        }

    # Check if compound is already in stock
    if stock_mgr.is_in_stock(smiles, stock_id):
        return {
            "ok": True,
            "solved": True,
            "n_steps": 0,
            "route_depth": 0,
            "leaves_in_stock_frac": 1.0,
            "route_tree": {"smiles": smiles, "type": "mol", "in_stock": True, "children": []},
            "building_blocks": [{"smiles": smiles, "in_stock": True}],
            "engine_used": "direct_stock"
        }

    # Apply template disconnections
    for name, rxn in RETRO_TEMPLATES:
        try:
            ps = rxn.RunReactants((mol,))
            if ps:
                reactants = ps[0]
                bb_list = []
                children_nodes = []
                all_in_stock = True

                for r in reactants:
                    r_smi = Chem.MolToSmiles(r, canonical=True)
                    in_stk = stock_mgr.is_in_stock(r_smi, stock_id)
                    bb_list.append({"smiles": r_smi, "in_stock": in_stk})
                    children_nodes.append({
                        "smiles": r_smi,
                        "type": "mol",
                        "in_stock": in_stk,
                        "children": []
                    })
                    if not in_stk:
                        all_in_stock = False

                stock_frac = sum(1 for b in bb_list if b["in_stock"]) / max(1, len(bb_list))

                route_tree = {
                    "smiles": smiles,
                    "type": "mol",
                    "in_stock": False,
                    "children": [{
                        "reaction_name": name,
                        "type": "rxn",
                        "children": children_nodes
                    }]
                }

                return {
                    "ok": True,
                    "solved": all_in_stock,
                    "n_steps": 1,
                    "route_depth": 1,
                    "leaves_in_stock_frac": round(stock_frac, 2),
                    "route_tree": route_tree,
                    "building_blocks": bb_list,
                    "engine_used": "retro_templates"
                }
        except Exception:
            continue

    # Unsolved fallback
    return {
        "ok": True,
        "solved": False,
        "n_steps": 0,
        "route_depth": 0,
        "leaves_in_stock_frac": 0.0,
        "route_tree": {"smiles": smiles, "type": "mol", "in_stock": False, "children": []},
        "building_blocks": [{"smiles": smiles, "in_stock": False}],
        "engine_used": "unsolved_fallback"
    }
