"""
Edeon Engine — Speciation JSON-RPC Handlers
"""

from typing import Dict, Any
from .enumerate import enumerate_protonation_states
from .pka import estimate_pka
from .microspecies import calculate_fractional_populations
from .cache import read_speciation_cache, write_speciation_cache, get_inchikey


def handle_speciation_enumerate(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for speciation.enumerate.

    params: { "smiles": str, "ph_min": float, "ph_max": float, "ph_target": float, "max_variants": int, "db_path": str }
    """
    smiles = params.get("smiles", "")
    ph_min = float(params.get("ph_min", 4.0))
    ph_max = float(params.get("ph_max", 8.0))
    ph_target = float(params.get("ph_target", 6.5))
    max_variants = int(params.get("max_variants", 8))
    db_path = params.get("db_path", "")

    cached = read_speciation_cache(db_path, smiles, ph_target)
    if cached:
        return cached

    variants, method = enumerate_protonation_states(
        smiles, ph_min=ph_min, ph_max=ph_max, max_variants=max_variants
    )
    pka_values = estimate_pka(smiles)
    microspecies = calculate_fractional_populations(variants, ph_target, pka_values)

    result = {
        "ok": True,
        "input_inchikey": get_inchikey(smiles),
        "microspecies": microspecies,
        "pka_values": pka_values,
        "method": method,
    }

    if db_path:
        write_speciation_cache(db_path, smiles, ph_target, result)

    return result


def handle_speciation_dominant_at_ph(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for speciation.dominant_at_ph.

    params: { "smiles": str, "ph": float }
    """
    smiles = params.get("smiles", "")
    ph = float(params.get("ph", 6.5))

    enum_res = handle_speciation_enumerate({
        "smiles": smiles,
        "ph_min": max(1.0, ph - 2.0),
        "ph_max": min(14.0, ph + 2.0),
        "ph_target": ph,
    })

    microspecies = enum_res.get("microspecies", [])
    dom = next((m for m in microspecies if m.get("dominant")), None)
    if not dom and microspecies:
        dom = microspecies[0]

    return {
        "ok": True,
        "smiles": dom.get("smiles", smiles) if dom else smiles,
        "charge": dom.get("charge", 0) if dom else 0,
        "fraction": dom.get("fraction_at_target", 1.0) if dom else 1.0,
    }


def handle_speciation_profile_curve(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for speciation.profile_curve.

    params: { "smiles": str, "ph_min": float, "ph_max": float, "steps": int }
    """
    smiles = params.get("smiles", "")
    ph_min = float(params.get("ph_min", 4.0))
    ph_max = float(params.get("ph_max", 9.0))
    steps = int(params.get("steps", 26))

    step_size = (ph_max - ph_min) / max(1, steps - 1)
    variants, _ = enumerate_protonation_states(smiles, ph_min=ph_min, ph_max=ph_max)
    pka_values = estimate_pka(smiles)

    series = []
    for i in range(steps):
        ph = round(ph_min + i * step_size, 2)
        micro = calculate_fractional_populations(variants, ph, pka_values)
        series.append({
            "ph": ph,
            "species": [
                {"smiles": m["smiles"], "fraction": m["fraction_at_target"]}
                for m in micro
            ]
        })

    return {
        "ok": True,
        "series": series,
    }
