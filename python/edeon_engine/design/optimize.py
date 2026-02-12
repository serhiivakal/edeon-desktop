"""
Prescriptive design optimizer.
Enumerates analogs using MMP and Bioisosteric replacement rules,
re-predicts their full environmental fate profiles, and ranks them
by their ability to address the specified target liability.
"""

from .bioisostere import apply_bioisostere_rules
from .mmp import apply_mmp_transforms
from ..fate.parent_fate import environmental_fate_batch

def suggest_analogs(smiles: str, target_liability: str) -> list[dict]:
    """
    Suggests analogs to improve a target liability (e.g., 'persistence', 'leaching', 'toxicity', 'bioaccumulation').
    Steps:
      1. Enumerate analogs using bioisosteres and MMP transforms.
      2. Filter to analogs that target the specified liability.
      3. Compute full environmental fate predictions for the selected analogs.
      4. Rank suggestions by improvement in the target metric.
    """
    # 1. Enumerate analogs
    bio_analogs = apply_bioisostere_rules(smiles)
    mmp_analogs = apply_mmp_transforms(smiles)

    all_analogs = bio_analogs + mmp_analogs
    if not all_analogs:
        return []

    # Filter/deduplicate analogs targeting this liability
    seen_smiles = set()
    filtered_analogs = []
    for a in all_analogs:
        if a["smiles"] not in seen_smiles:
            seen_smiles.add(a["smiles"])
            filtered_analogs.append(a)

    if not filtered_analogs:
        return []

    # 2. Run predictions for all candidate analogs in a single batch
    smiles_list = [a["smiles"] for a in filtered_analogs]
    try:
        predictions = environmental_fate_batch(smiles_list)
    except Exception as e:
        print(f"Error predicting fate for analogs: {e}")
        return []

    # Map predictions back to analogs
    pred_map = {p["smiles"]: p for p in predictions}

    # 3. Score and rank suggestions
    ranked_suggestions = []
    for a in filtered_analogs:
        pred = pred_map.get(a["smiles"])
        if not pred:
            continue

        # Extract numeric values for ranking
        dt50 = pred["dt50_soil"]["value"] if pred["dt50_soil"]["value"] is not None else 999
        gus = pred["gus"]["value"] if pred["gus"]["value"] is not None else 999
        bcf = pred["bcf"]["value"] if pred["bcf"]["value"] is not None else 999


        # Calculate a score based on the target liability (lower is better for liabilities)
        score = 0
        if target_liability == "persistence":
            score = dt50  # We want lower soil half-life (less persistent)
        elif target_liability == "leaching":
            score = gus   # We want lower GUS leaching index
        elif target_liability == "bioaccumulation":
            score = bcf   # We want lower bioconcentration factor
        else:
            score = dt50 + gus + bcf

        ranked_suggestions.append({
            "smiles": a["smiles"],
            "rule_name": a["rule_name"],
            "description": a["description"],
            "target_liability": a["target_liability"],
            "fate": pred,
            "score": score
        })

    # Sort ascending (lower score/liability is better)
    ranked_suggestions.sort(key=lambda x: x["score"])

    # Remove score helper field from output
    for r in ranked_suggestions:
        del r["score"]

    return ranked_suggestions
