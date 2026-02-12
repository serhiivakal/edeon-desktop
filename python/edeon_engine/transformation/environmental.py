"""
Edeon Engine — Metabolite Ecotox & Environmental Rescoring Engine
Rescores transformation products and sets liability flags.
"""

from typing import Dict, Any, List
from ..fate.parent_fate import environmental_fate_batch
from ..toxicity import toxicity_batch


def rescore_metabolite_nodes(nodes: List[Dict[str, Any]], parent_smiles: str) -> List[Dict[str, Any]]:
    """Rescore transformation product nodes against parent benchmarks and assign liability_flag."""
    if not nodes:
        return []

    all_smiles = [parent_smiles] + [n["smiles"] for n in nodes]
    try:
        fate_res = environmental_fate_batch(all_smiles)
        parent_fate = fate_res[0]
        nodes_fate = fate_res[1:]
    except Exception:
        parent_fate = None
        nodes_fate = [None] * len(nodes)

    try:
        tox_res = toxicity_batch([{"smiles": s} for s in all_smiles])
        parent_tox = tox_res[0]
        nodes_tox = tox_res[1:]
    except Exception:
        parent_tox = None
        nodes_tox = [None] * len(nodes)

    parent_dt50 = 60.0
    if parent_fate and hasattr(parent_fate, 'dt50_soil') and parent_fate.dt50_soil.value.kind == 'numeric':
        parent_dt50 = parent_fate.dt50_soil.value.numeric or 60.0

    rescored_nodes = []
    for idx, node in enumerate(nodes):
        f = nodes_fate[idx] if idx < len(nodes_fate) else None
        t = nodes_tox[idx] if idx < len(nodes_tox) else None

        node_dt50 = 60.0
        if f and hasattr(f, 'dt50_soil') and f.dt50_soil.value.kind == 'numeric':
            node_dt50 = f.dt50_soil.value.numeric or 60.0

        # Liability evaluation
        liability_flag = False

        # 1. Persistence liability (metabolite DT50 > 1.2 * parent DT50)
        if node_dt50 > (parent_dt50 * 1.2):
            liability_flag = True

        # 2. Aquatic ecotox liability
        if t and parent_tox:
            parent_level = getattr(parent_tox, 'overall_level', 'Low')
            node_level = getattr(t, 'overall_level', 'Low')
            level_ranks = {'Low': 1, 'Med': 2, 'High': 3}
            if level_ranks.get(node_level, 1) > level_ranks.get(parent_level, 1):
                liability_flag = True

        node["liability_flag"] = liability_flag
        node["rescored"] = {
            "dt50_soil": node_dt50,
            "overall_tox": getattr(t, 'overall_level', 'Low') if t else 'Low'
        }

        rescored_nodes.append(node)

    return rescored_nodes
