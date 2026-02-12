"""
Edeon Engine — Multi-Parameter Optimization (MPO) Scoring

Computes a composite lead optimization score (0–10) that integrates:
  1. Pesticide-likeness (Tice rules)
  2. Cross-species selectivity
  3. Resistance risk
  4. Toxicity prediction
  5. Environmental safety (leaching & ecotox safety)

The MPO score ranks compounds for lead optimization priority.
Weights are user-configurable (0–100 per stage) and are normalized internally.
"""

import math

# Default equal weights (relative — will be normalized to sum=1)
DEFAULT_WEIGHTS = {
    "pesticide_likeness": 1.0,
    "selectivity":        1.0,
    "resistance":         1.0,
    "toxicity":           1.0,
    "environmental_safety": 1.0,
}


def _normalize_weights(weights: dict | None) -> dict:
    """Normalize raw user weights (0–100) to fractions summing to 1."""
    # Handle both snake_case and camelCase keys from frontend
    mapped = {}
    if weights:
        for k, v in weights.items():
            # map frontend slider names to backend names
            key = k.lower().replace("-", "_")
            if "pesticide" in key or "likeness" in key:
                mapped["pesticide_likeness"] = float(v)
            elif "selectivity" in key:
                mapped["selectivity"] = float(v)
            elif "resistance" in key:
                mapped["resistance"] = float(v)
            elif "toxicity" in key:
                mapped["toxicity"] = float(v)
            elif "environmental" in key or "safety" in key or "fate" in key:
                mapped["environmental_safety"] = float(v)

    w = {**DEFAULT_WEIGHTS, **mapped}
    total = sum(max(0.0, v) for v in w.values())
    if total == 0:
        return {k: 1.0 / len(w) for k in w}
    return {k: max(0.0, v) / total for k, v in w.items()}


def compute_mpo_score(
    properties: dict,
    tice_result: dict,
    selectivity_result: dict,
    resistance_result: dict,
    toxicity_result: dict | None = None,
    weights: dict | None = None,
) -> dict:
    """Compute MPO composite score for a single compound.

    Args:
        properties: mol_weight, logp, tpsa, hbd, hba, rotatable_bonds
        tice_result: level, violations
        selectivity_result: min_selectivity, overall_level, profiles
        resistance_result: level, risk_score, factors
        toxicity_result: predictions, overall_level, applicability_domain (optional)
        weights: optional dict with keys matching component names, values 0–100

    Returns:
        dict with:
            score: 0–10 composite score
            breakdown: per-component scores
            rank_category: "Lead", "Candidate", "Deprioritize"
    """
    if properties is None:
        properties = {}
    if tice_result is None:
        tice_result = {}
    if selectivity_result is None:
        selectivity_result = {}
    if resistance_result is None:
        resistance_result = {}

    breakdown = {}
    w = _normalize_weights(weights)


    TOTAL_MAX = 10.0

    # ── 1. Pesticide-likeness component (raw 0–2.0) ────────────
    tice_level = tice_result.get("level", "Low")
    if tice_level == "High":
        tice_raw = 2.0
    elif tice_level == "Med":
        tice_raw = 1.2
    else:
        tice_raw = 0.4
    breakdown["pesticide_likeness"] = round(tice_raw, 1)

    # ── 2. Selectivity component (raw 0–2.5) ──────────────────
    min_si = selectivity_result.get("min_selectivity", 5.0)
    overall = selectivity_result.get("overall_level", "moderate")
    if overall == "safe" and min_si >= 10:
        sel_raw = 2.5
    elif overall == "safe":
        sel_raw = 2.0
    elif overall == "moderate":
        sel_raw = 0.8 + min(1.2, min_si * 0.12)
    else:
        sel_raw = max(0, min_si * 0.08)
    breakdown["selectivity"] = round(sel_raw, 1)

    # ── 3. Resistance component (raw 0–1.5) ───────────────────
    res_level = resistance_result.get("level", "Med")
    res_risk = resistance_result.get("risk_score", 5.0)
    if res_level == "Low":
        res_raw = 1.5
    elif res_level == "Med":
        res_raw = 0.8
    else:
        res_raw = max(0, 1.5 - res_risk * 0.15)
    breakdown["resistance"] = round(res_raw, 1)

    # ── 4. Toxicity component (raw 0–2.0) ─────────────────────
    tox_raw = 1.0
    if toxicity_result:
        tox_level = toxicity_result.get("overall_level", "Med")
        ad = toxicity_result.get("applicability_domain", {})
        ad_confidence = ad.get("confidence", 0.5)
        if tox_level == "Low":
            tox_raw = 2.0
        elif tox_level == "Med":
            tox_raw = 1.0
        else:
            tox_raw = 0.2
        tox_raw *= min(1.0, ad_confidence + 0.2)
    breakdown["toxicity"] = round(tox_raw, 1)

    # ── 5. Environmental safety component (raw 0–2.0) ──────────
    # Combines Groundwater Ubiquity Score (GUS leaching) and honeybee ecotox safety
    logp_val = properties.get("logp", 2.0)
    if logp_val is None:
        logp_val = 2.0
    tpsa_val = properties.get("tpsa", 60) or 60
    mw_val = properties.get("mol_weight", 300) or 300

    # Soil sorption Koc log Koc = 0.47 * LogP + 1.09
    log_koc = max(0.0, min(6.0, 0.47 * logp_val + 1.09))
    
    # Degradation half life DT50 in soil
    dt50 = 20.0 * (1.0 + 0.3 * max(0.0, logp_val)) * (1.0 + 0.2 * max(0.0, (mw_val - 200.0) / 100.0)) * math.exp(-tpsa_val / 150.0)
    dt50 = max(2.0, min(365.0, dt50))
    
    # GUS = log10(DT50) * (4.0 - logKoc)
    gus = math.log10(dt50) * (4.0 - log_koc) if log_koc < 4.0 else 0.0

    # Honeybee LD50 Contact
    bee_ld50 = 10 ** (2.5 - 0.5 * logp_val)

    # Base env safety score
    env_raw = 2.0
    if gus > 2.8:  # High leaching risk
        env_raw -= 0.8
    elif gus > 1.8:  # Borderline leaching
        env_raw -= 0.3

    if bee_ld50 < 1.0:  # High bee risk
        env_raw -= 0.8
    elif bee_ld50 < 10.0:  # Moderate bee risk
        env_raw -= 0.4

    env_raw = max(0.2, env_raw)
    breakdown["environmental_safety"] = round(env_raw, 1)

    # ── Weighted composite ─────────────────────────────────────
    component_maxes = {
        "pesticide_likeness":  2.0,
        "selectivity":         2.5,
        "resistance":          1.5,
        "toxicity":            2.0,
        "environmental_safety": 2.0,
    }
    raw_vals = {
        "pesticide_likeness":  tice_raw,
        "selectivity":         sel_raw,
        "resistance":          res_raw,
        "toxicity":            tox_raw,
        "environmental_safety": env_raw,
    }

    total = 0.0
    for key, wt in w.items():
        normalized = raw_vals.get(key, 0.0) / component_maxes.get(key, 1.0)
        total += wt * normalized * TOTAL_MAX

    total = round(min(10.0, max(0.0, total)), 1)

    if total >= 7.0:
        rank = "Lead"
    elif total >= 4.5:
        rank = "Candidate"
    else:
        rank = "Deprioritize"

    return {
        "score": total,
        "breakdown": breakdown,
        "rank_category": rank,
        "weights_applied": {k: round(v, 3) for k, v in w.items()},
    }


def mpo_score_batch(
    properties_list: list[dict],
    tice_results: list[dict],
    selectivity_results: list[dict],
    resistance_results: list[dict],
    toxicity_results: list[dict] | None = None,
    weights: dict | None = None,
) -> list[dict]:
    """Compute MPO scores for a batch of compounds."""
    results = []
    if not properties_list:
        return []
    for i in range(len(properties_list)):
        prop = properties_list[i] if properties_list and i < len(properties_list) else None
        tice = tice_results[i] if tice_results and i < len(tice_results) else None
        sel = selectivity_results[i] if selectivity_results and i < len(selectivity_results) else None
        res_item = resistance_results[i] if resistance_results and i < len(resistance_results) else None
        tox = toxicity_results[i] if toxicity_results and i < len(toxicity_results) else None
        
        result = compute_mpo_score(
            prop,
            tice,
            sel,
            res_item,
            tox,
            weights,
        )
        results.append(result)
    return results



class QSARModelHandle:
    """Standard handle representing a trained QSAR model."""
    def __init__(self, estimator, featurizer_selections: list, ad):
        self.estimator = estimator
        self.featurizer_selections = featurizer_selections
        self.ad = ad


def _confidence_from_status(status: str) -> float:
    """Map AD status string to confidence value between 0.0 and 1.0."""
    if status == "in":
        return 1.0
    elif status == "borderline":
        return 0.6
    elif status == "out":
        return 0.2
    else:  # invalid
        return 0.0


def predict(model_handle: QSARModelHandle, smiles_list: list[str]) -> list[dict]:
    """Computes predictions and checks applicability domain for a list of SMILES.
    
    Returns a list of dicts with keys:
      - smiles: input structure
      - prediction: continuous or binary predicted value
      - ad_status: 'in' | 'borderline' | 'out' | 'invalid'
      - ad_confidence: float mapping status to desirability multiplier
      - tanimoto_distance: mean k-NN similarity distance
      - leverage: leverage score (if leverage AD is available)
    """
    from edeon_engine.models.featurizers import run_featurizers
    from edeon_engine.applicability import score_query
    
    # 1. Compute descriptors/fingerprints
    X, _ = run_featurizers(smiles_list, model_handle.featurizer_selections)
    
    # 2. Estimate model prediction
    raw_pred = model_handle.estimator.predict(X)
    
    # 3. Score Applicability Domain
    ad_scores = score_query(model_handle.ad, smiles_list, X)
    
    # 4. Map and build return records
    out = []
    n = len(smiles_list)
    lev_list = ad_scores["leverage"].get("leverage") if ad_scores["leverage"].get("available") else [None] * n
    if lev_list is None:
        lev_list = [None] * n
        
    for s, p, status, td, lev_ok in zip(
            smiles_list, raw_pred, ad_scores["overall_status"],
            ad_scores["tanimoto"]["mean_knn_distance"],
            lev_list):
        out.append({
            "smiles": s,
            "prediction": float(p),
            "ad_status": status,
            "ad_confidence": _confidence_from_status(status),
            "tanimoto_distance": float(td) if td is not None else None,
            "leverage": float(lev_ok) if lev_ok is not None else None,
        })
    return out

