"""
Edeon Bottleneck Analyzer — Desirability Curves

Maps raw endpoint predictions to desirability scores d ∈ [0,1] via
piecewise-linear curves. Curve types:
  - higher_better: more is better (e.g. LC50)
  - lower_better: less is better (e.g. DT50)
  - target_window: optimal range in the middle (e.g. Koc)
  - step: binary pass/fail (e.g. skin sensitization)

Breakpoints and desirability levels are loaded from profile JSON files
in data/desirability/. The regulatory thresholds in cutoffs.py are the
natural breakpoints for agrochem endpoints.
"""

import json
import os
from typing import Optional
from pathlib import Path

# Profile cache
_PROFILE_CACHE: dict[str, dict] = {}

# Default profiles directory
_PROFILES_DIR = Path(__file__).parent.parent.parent / "data" / "desirability"


def _find_profiles_dir() -> Path:
    """Locate the desirability profiles directory."""
    # Try relative to this file first
    if _PROFILES_DIR.exists():
        return _PROFILES_DIR
    # Try relative to CWD
    cwd_path = Path.cwd() / "data" / "desirability"
    if cwd_path.exists():
        return cwd_path
    return _PROFILES_DIR


def load_profile(profile_id: str) -> dict:
    """Load a desirability profile by ID (filename without .json)."""
    if profile_id in _PROFILE_CACHE:
        return _PROFILE_CACHE[profile_id]

    profiles_dir = _find_profiles_dir()
    path = profiles_dir / f"{profile_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Desirability profile not found: {path}")

    with open(path, "r") as f:
        profile = json.load(f)

    _PROFILE_CACHE[profile_id] = profile
    return profile


def list_profiles() -> list[dict]:
    """List all available desirability profiles."""
    profiles_dir = _find_profiles_dir()
    results = []
    if profiles_dir.exists():
        for f in sorted(profiles_dir.glob("*.json")):
            try:
                with open(f, "r") as fh:
                    data = json.load(fh)
                results.append({
                    "id": f.stem,
                    "name": data.get("name", f.stem),
                    "n_endpoints": len(data.get("endpoints", {})),
                })
            except (json.JSONDecodeError, KeyError):
                continue
    return results


def _interpolate(x: float, breakpoints: list[float], desirability: list[float]) -> float:
    """Piecewise-linear interpolation.

    breakpoints has N elements, desirability has N+1 elements.
    desirability[0] is the value for x <= breakpoints[0],
    desirability[-1] is the value for x >= breakpoints[-1].
    """
    if not breakpoints:
        return desirability[0] if desirability else 0.5

    if x <= breakpoints[0]:
        return desirability[0]
    if x >= breakpoints[-1]:
        return desirability[-1]

    for i in range(len(breakpoints) - 1):
        if breakpoints[i] <= x <= breakpoints[i + 1]:
            t = (x - breakpoints[i]) / (breakpoints[i + 1] - breakpoints[i])
            return desirability[i + 1] * t + desirability[i] * (1.0 - t)

    return desirability[-1]


def compute_desirability(
    value: float,
    endpoint_config: dict,
) -> float:
    """Compute desirability d ∈ [0,1] for a single value and endpoint config.

    Args:
        value: raw prediction value
        endpoint_config: dict with curve_type, breakpoints, desirability
    """
    if value is None:
        return 0.5  # unknown → neutral

    curve_type = endpoint_config.get("curve_type", "higher_better")
    breakpoints = endpoint_config.get("breakpoints", [])
    desr = endpoint_config.get("desirability", [])

    if curve_type == "step":
        # Binary: value below threshold → desirability[0], above → desirability[1]
        if not breakpoints or len(desr) < 2:
            return 0.5
        return desr[0] if value < breakpoints[0] else desr[1]

    return _interpolate(value, breakpoints, desr)


def compute_desirability_vector(
    endpoint_values: dict[str, Optional[float]],
    profile: dict,
) -> dict[str, float]:
    """Compute desirability for all endpoints in a profile.

    Args:
        endpoint_values: {endpoint_name: raw_value_or_None}
        profile: loaded profile dict

    Returns:
        {endpoint_name: desirability_score}
    """
    endpoints_config = profile.get("endpoints", {})
    result = {}
    for ep_name, ep_config in endpoints_config.items():
        raw = endpoint_values.get(ep_name)
        if raw is not None:
            result[ep_name] = compute_desirability(raw, ep_config)
        else:
            result[ep_name] = 0.5  # missing → neutral
    return result


def get_endpoint_weights(
    profile: dict,
    user_weights: Optional[dict[str, float]] = None,
) -> dict[str, float]:
    """Get normalized endpoint weights from profile + optional user overrides.

    Returns weights summing to 1.0.
    """
    endpoints_config = profile.get("endpoints", {})
    weights = {}
    for ep_name, ep_config in endpoints_config.items():
        w = ep_config.get("default_weight", 1.0)
        if user_weights and ep_name in user_weights:
            w = user_weights[ep_name]
        weights[ep_name] = max(0.0, float(w))

    total = sum(weights.values())
    if total == 0:
        n = len(weights)
        return {k: 1.0 / n for k in weights} if n > 0 else {}
    return {k: v / total for k, v in weights.items()}
