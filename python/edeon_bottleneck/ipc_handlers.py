"""
Edeon Bottleneck Analyzer — JSON-RPC Handler Implementations

Five handlers registered in __main__.py's dispatch:
  - bottleneck.analyze       → full portfolio analysis
  - bottleneck.compound      → per-compound weakest-link
  - bottleneck.attrition     → gate-attrition from workflow data
  - bottleneck.suggest_weights → K10 objective seeding
  - bottleneck.list_profiles → available desirability profiles
"""

import hashlib
import json
import uuid

from .desirability import (
    load_profile, list_profiles, compute_desirability,
    compute_desirability_vector, get_endpoint_weights,
)
from .leverage import (
    compute_achievable_targets, compute_leverage, rank_by_leverage,
)
from .uncertainty import (
    count_in_ad, assess_reliability, mc_rank_stability,
    bootstrap_ci, check_ambiguity,
)
from .classify import classify_bottleneck
from .antagonism import compute_tradeoff_matrix
from .attrition import compute_gate_attrition
from .weights import suggest_weights
from .schema import (
    EndpointResult, BottleneckAnalysis,
    CompoundBottleneck, AttritionResult,
)


def _compute_params_hash(params: dict) -> str:
    """Deterministic hash of analysis parameters for caching."""
    canonical = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _desirability_fn_factory(profile: dict):
    """Create a desirability function bound to a profile."""
    endpoints_config = profile.get("endpoints", {})

    def d_fn(value, endpoint):
        config = endpoints_config.get(endpoint, {})
        if not config:
            return 0.5
        return compute_desirability(value, config)

    return d_fn


def handle_analyze(params: dict) -> dict:
    """Full bottleneck analysis for a compound portfolio.

    Params:
        compounds: list of dicts with:
            - id: compound identifier
            - endpoints: {endpoint: {value, interval?, ad_status?}}
        profile: str — profile ID (default "agrochem_default")
        project_id: str
        user_weights: optional {endpoint: weight} overrides
        n_mc: optional MC draws (default 500)
    """
    compounds = params.get("compounds", [])
    profile_id = params.get("profile", "agrochem_default")
    project_id = params.get("project_id", "")
    user_weights = params.get("user_weights")
    n_mc = int(params.get("n_mc", 500))

    profile = load_profile(profile_id)
    endpoints_config = profile.get("endpoints", {})
    endpoint_names = list(endpoints_config.keys())

    weights = get_endpoint_weights(profile, user_weights)
    d_fn = _desirability_fn_factory(profile)

    # Compute desirabilities for each compound
    compounds_desirabilities = []
    compounds_ad_status = []

    for c in compounds:
        ep_data = c.get("endpoints", {})
        d_vec = {}
        ad_vec = {}
        for ep in endpoint_names:
            info = ep_data.get(ep, {})
            val = info.get("value")
            ad = info.get("ad_status", "in")
            d_vec[ep] = d_fn(val, ep) if val is not None else 0.5
            ad_vec[ep] = ad
        compounds_desirabilities.append(d_vec)
        compounds_ad_status.append(ad_vec)

    # Compute achievable targets
    achievable_targets = compute_achievable_targets(
        compounds_desirabilities, compounds_ad_status, endpoint_names,
        method="spread",
    )

    # Compute leverage
    leverage_results = compute_leverage(
        compounds_desirabilities, endpoint_names,
        weights, achievable_targets,
    )

    # MC uncertainty propagation
    def leverage_fn(desirs, eps, w, targets):
        return compute_leverage(desirs, eps, w, targets)

    mc_results = mc_rank_stability(
        compounds, endpoint_names, weights,
        d_fn, leverage_fn, achievable_targets,
        n_mc=n_mc,
    )

    # Build ranked endpoint results
    ranked = rank_by_leverage(leverage_results)
    endpoint_results = []

    for rank_idx, (ep, lev_data) in enumerate(ranked):
        n_ad = count_in_ad(compounds, ep)
        reliability = assess_reliability(n_ad)

        mc_data = mc_results.get(ep, {})
        leverage_samples = mc_data.get("leverage_samples", [])
        rank_stability = mc_data.get("rank_stability", 0.0)

        if len(leverage_samples) > 1:
            ci = bootstrap_ci(leverage_samples)
        else:
            ci = (lev_data["leverage"], lev_data["leverage"])

        n_compounds_total = len(compounds)
        n_out_ad = n_compounds_total - n_ad
        frac_out = n_out_ad / n_compounds_total if n_compounds_total > 0 else 0.0

        classification = classify_bottleneck(
            ep,
            leverage=lev_data["leverage"],
            headroom=lev_data["headroom"],
            mean_desirability=lev_data["mean_desirability"],
            reliability=reliability,
            rank_stability=rank_stability,
            leverage_ci=ci,
            n_in_ad=n_ad,
            fraction_out_of_ad=frac_out,
        )

        display_name = endpoints_config.get(ep, {}).get("display_name", ep)

        endpoint_results.append(EndpointResult(
            endpoint=ep,
            display_name=display_name,
            leverage=round(lev_data["leverage"], 6),
            leverage_ci=(round(ci[0], 6), round(ci[1], 6)),
            headroom=round(lev_data["headroom"], 4),
            mean_desirability=round(lev_data["mean_desirability"], 4),
            achievable_target=round(achievable_targets.get(ep, 0.5), 4),
            rank=rank_idx + 1,
            rank_stability=round(rank_stability, 4),
            kind=classification["kind"],
            recommended_action=classification["recommended_action"],
            reason=classification["reason"],
            reliability=reliability,
            n_in_ad=n_ad,
            weight=round(weights.get(ep, 0.0), 4),
        ))

    # Tradeoff matrix
    tradeoff = compute_tradeoff_matrix(compounds_desirabilities, endpoint_names)

    # Check ambiguity between top-2
    top_endpoint = endpoint_results[0].endpoint if endpoint_results else None
    top_kind = endpoint_results[0].kind if endpoint_results else None
    bottleneck_ambiguous = False

    if len(endpoint_results) >= 2:
        bottleneck_ambiguous = check_ambiguity(
            endpoint_results[0].leverage_ci,
            endpoint_results[1].leverage_ci,
        )

    # Overall reliability
    reliabilities = [er.reliability for er in endpoint_results]
    if all(r == "insufficient_data" for r in reliabilities):
        overall_reliability = "insufficient_data"
    elif any(r == "insufficient_data" for r in reliabilities):
        overall_reliability = "low"
    elif any(r == "low" for r in reliabilities):
        overall_reliability = "low"
    else:
        overall_reliability = "ok"

    params_hash = _compute_params_hash({
        "profile": profile_id,
        "n_compounds": len(compounds),
        "compound_ids": [c.get("id", "") for c in compounds],
        "user_weights": user_weights,
    })

    analysis_id = str(uuid.uuid4())

    # Build journal payload for Rust to persist
    journal_payload = None
    if top_endpoint:
        from edeon_engine.journal_payload import (
            build_journal_payload, build_rationale, build_provenance,
        )
        journal_payload = build_journal_payload(
            decision_kind="bottleneck_identified",
            subject_type="analysis",
            subject_id=analysis_id,
            summary_kwargs={
                "top_endpoint": top_endpoint,
                "kind": top_kind or "unknown",
                "leverage": endpoint_results[0].leverage if endpoint_results else 0.0,
            },
            provenance=build_provenance(params_hash=params_hash),
            rationale=build_rationale(
                drivers=[{"factor": er.endpoint, "value": er.leverage, "contribution": er.weight}
                         for er in endpoint_results[:5]],
                scores={"n_compounds": len(compounds), "n_endpoints": len(endpoint_names)},
            ),
        )

    result = BottleneckAnalysis(
        analysis_id=analysis_id,
        project_id=project_id,
        profile=profile_id,
        n_compounds=len(compounds),
        endpoints=endpoint_results,
        top_endpoint=top_endpoint,
        top_kind=top_kind,
        bottleneck_ambiguous=bottleneck_ambiguous,
        tradeoff_matrix=tradeoff,
        overall_reliability=overall_reliability,
        params_hash=params_hash,
        journal_payload=journal_payload,
    )

    return result.to_dict()


def handle_compound(params: dict) -> dict:
    """Per-compound weakest-link analysis.

    Params:
        compound: dict with id, endpoints: {endpoint: {value, ad_status?}}
        profile: str
    """
    compound = params.get("compound", {})
    profile_id = params.get("profile", "agrochem_default")

    profile = load_profile(profile_id)
    endpoints_config = profile.get("endpoints", {})
    d_fn = _desirability_fn_factory(profile)
    weights = get_endpoint_weights(profile)

    ep_data = compound.get("endpoints", {})
    d_vec = {}

    for ep in endpoints_config:
        info = ep_data.get(ep, {})
        val = info.get("value")
        d_vec[ep] = d_fn(val, ep) if val is not None else 0.5

    # Find weakest link (lowest weighted desirability)
    weakest_ep = None
    weakest_d = 1.0
    overall_d = 0.0

    for ep, d in d_vec.items():
        w = weights.get(ep, 0.0)
        overall_d += w * d
        if d < weakest_d:
            weakest_d = d
            weakest_ep = ep

    # Classify weakest
    ad_status = ep_data.get(weakest_ep, {}).get("ad_status", "in") if weakest_ep else "in"
    if ad_status == "out":
        kind = "epistemic"
        reason = f"Out of applicability domain for {weakest_ep}"
    elif weakest_d < 0.3:
        kind = "chemical"
        reason = f"Low desirability ({weakest_d:.3f}) for {weakest_ep}"
    else:
        kind = "distractor"
        reason = f"No severe bottleneck (weakest d={weakest_d:.3f})"

    result = CompoundBottleneck(
        compound_id=compound.get("id", ""),
        weakest_endpoint=weakest_ep or "",
        weakest_desirability=round(weakest_d, 4),
        overall_desirability=round(overall_d, 4),
        kind=kind,
        reason=reason,
    )

    return result.to_dict()


def handle_attrition(params: dict) -> dict:
    """Gate-attrition bottleneck from workflow data.

    Params:
        gate_results: list of {gate_name, n_input, n_passed}
    """
    gate_results = params.get("gate_results", [])
    result = compute_gate_attrition(gate_results)
    return result


def handle_suggest_weights(params: dict) -> dict:
    """Suggest K10 objective weights from leverage profile.

    Params:
        leverage_results: list of {endpoint, leverage, kind}
        n_top: optional (default 5)
    """
    leverage_results = params.get("leverage_results", [])
    n_top = int(params.get("n_top", 5))
    return suggest_weights(leverage_results, n_top=n_top)


def handle_list_profiles(params: dict) -> list[dict]:
    """List available desirability profiles."""
    return list_profiles()
