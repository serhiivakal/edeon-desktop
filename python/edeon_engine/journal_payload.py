"""
Edeon Engine — Decision Journal Payload Builders

Builds structured rationale/alternatives payloads for the Decision Journal.
Python's only journal-adjacent responsibility: emit well-formed payloads
in RPC responses for Rust to persist (INV-1: Python never writes to the journal).

Summary templates are deterministic — assembled from structured fields,
never model-generated text.
"""

from typing import Any, Optional


# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY TEMPLATES (one per decision_kind)
# ─────────────────────────────────────────────────────────────────────────────

SUMMARY_TEMPLATES = {
    "workflow_verdict": "Workflow '{workflow_name}' completed: {verdict} ({n_compounds} compounds, {n_passed} passed)",
    "compound_promoted": "Compound {compound_name} promoted through {gate_name}",
    "compound_rejected": "{n_rejected} compound(s) rejected at {gate_name}: {reason}",
    "model_deployed": "Model '{model_name}' deployed for endpoint {endpoint} (tier {tier})",
    "model_selected": "Model '{model_name}' selected as Arena winner for {endpoint} (rank #{rank})",
    "bottleneck_identified": "Bottleneck analysis: {top_endpoint} identified as {kind} constraint (leverage={leverage:.3f})",
    "bo_batch_proposed": "BO campaign '{campaign_name}' iteration {iteration}: {n_proposals} proposals generated",
    "bo_proposal_accepted": "{n_accepted} BO proposal(s) accepted from iteration {iteration}",
    "bo_proposal_rejected": "{n_rejected} BO proposal(s) rejected from iteration {iteration}",
    "transform_applied": "Transform applied to {parent_name}: {transform_description}",
    "analog_registered": "Analog {product_name} registered from generative design (parent: {parent_name})",
    "tp_liability_flagged": "Transformation product {tp_name} flagged: worse than parent on {flagged_endpoints}",
    "manual_override": "User override: {action_taken} (system recommended: {system_recommendation})",
    "parameter_changed": "Parameter changed: {param_name} = {new_value} (was: {old_value})",
}


WHY_NOT_TEMPLATES = {
    "lower_score": "{label} not chosen: score {score:.2f} vs winner {winner_score:.2f}",
    "failed_gate": "{label} not chosen: failed {gate_name}",
    "out_of_ad": "{label} not chosen: out of applicability domain for {endpoint}",
    "insufficient_data": "{label} not chosen: insufficient data (n={n})",
    "user_preference": "{label} not chosen: user selected alternative",
}


def build_summary(decision_kind: str, **kwargs) -> str:
    """Build a deterministic summary string from a template and keyword args.

    Falls back to a generic format if the kind is unknown (extensible enum).
    """
    template = SUMMARY_TEMPLATES.get(decision_kind)
    if template is None:
        # Unknown kind — round-trip without loss
        parts = [f"{k}={v}" for k, v in kwargs.items() if v is not None]
        return f"{decision_kind}: {', '.join(parts)}" if parts else decision_kind
    try:
        return template.format(**kwargs)
    except (KeyError, ValueError):
        # Graceful degradation if kwargs don't match template
        parts = [f"{k}={v}" for k, v in kwargs.items() if v is not None]
        return f"{decision_kind}: {', '.join(parts)}" if parts else decision_kind


def build_why_not(reason_key: str, **kwargs) -> str:
    """Build a deterministic 'why not chosen' string for an alternative."""
    template = WHY_NOT_TEMPLATES.get(reason_key)
    if template is None:
        return f"{kwargs.get('label', 'Alternative')} not chosen: {reason_key}"
    try:
        return template.format(**kwargs)
    except (KeyError, ValueError):
        return f"{kwargs.get('label', 'Alternative')} not chosen: {reason_key}"


def build_rationale(
    drivers: Optional[list[dict]] = None,
    scores: Optional[dict[str, float]] = None,
    thresholds: Optional[dict[str, float]] = None,
) -> dict:
    """Build a structured rationale block.

    Args:
        drivers: list of {"factor": str, "value": float, "contribution": float}
        scores: named scores relevant to the decision
        thresholds: named thresholds applied
    """
    return {
        "drivers": drivers or [],
        "scores": scores or {},
        "thresholds": thresholds or {},
    }


def build_alternative(
    id: str,
    label: str,
    score: float,
    why_not: str,
) -> dict:
    """Build a single alternative entry."""
    return {
        "id": id,
        "label": label,
        "score": score,
        "why_not": why_not,
    }


def build_alternatives(alternatives: list[dict]) -> list[dict]:
    """Validate and return a list of alternative entries.

    Each entry should have: id, label, score, why_not.
    """
    result = []
    for alt in alternatives:
        result.append({
            "id": str(alt.get("id", "")),
            "label": str(alt.get("label", "")),
            "score": float(alt.get("score", 0.0)),
            "why_not": str(alt.get("why_not", "")),
        })
    return result


def build_confidence(
    uq: Optional[dict] = None,
    ad_status: Optional[str] = None,
    reliability: Optional[str] = None,
) -> dict:
    """Build a confidence block for a journal entry.

    Args:
        uq: per-endpoint UQ intervals {endpoint: {"interval": [lo, hi]}}
        ad_status: "in" | "edge" | "out"
        reliability: "ok" | "low" | "insufficient_data"
    """
    return {
        "uq": uq,
        "ad_status": ad_status,
        "reliability": reliability,
    }


def build_provenance(
    params_hash: str,
    model_versions: Optional[dict[str, str]] = None,
    code_version: str = "0.1.0",
    seed: Optional[int] = None,
) -> dict:
    """Build a provenance block linking journal entries to exact inputs."""
    return {
        "params_hash": params_hash,
        "model_versions": model_versions or {},
        "code_version": code_version,
        "seed": seed,
    }


def build_journal_payload(
    decision_kind: str,
    subject_type: str,
    subject_id: str,
    summary_kwargs: dict,
    provenance: dict,
    rationale: Optional[dict] = None,
    alternatives: Optional[list[dict]] = None,
    confidence: Optional[dict] = None,
) -> dict:
    """Build the complete journal payload dict to include in an RPC response.

    Rust deserializes this and calls journal::append inside its transaction.
    """
    return {
        "decision_kind": decision_kind,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "summary": build_summary(decision_kind, **summary_kwargs),
        "rationale": rationale,
        "alternatives": alternatives,
        "confidence": confidence,
        "provenance": provenance,
    }
