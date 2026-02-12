"""
Pluggable Analog Generator Registry.

Allows workflows (W4, W7, W8) to use different analog generation
strategies by name instead of hardcoding a single implementation.

Usage:
    from edeon_engine.design.analog_registry import get_generator
    
    generator = get_generator("default")  # bioisostere + MMP
    analogs = generator(smiles, target_liability)
"""

from typing import Callable


def _default_generator(smiles: str, target_liability: str) -> list[dict]:
    """Default analog generator: bioisostere rules + MMP transforms."""
    from .optimize import suggest_analogs
    return suggest_analogs(smiles, target_liability)


def _bioisostere_only(smiles: str, target_liability: str) -> list[dict]:
    """Generate analogs using only bioisostere replacement rules."""
    from .bioisostere import apply_bioisostere_rules
    from ..fate.parent_fate import environmental_fate_batch
    
    analogs = apply_bioisostere_rules(smiles)
    if not analogs:
        return []
    
    # Deduplicate
    seen = set()
    unique = []
    for a in analogs:
        if a["smiles"] not in seen:
            seen.add(a["smiles"])
            unique.append(a)
    
    return unique


def _mmp_only(smiles: str, target_liability: str) -> list[dict]:
    """Generate analogs using only Matched Molecular Pair transforms."""
    from .mmp import apply_mmp_transforms
    
    analogs = apply_mmp_transforms(smiles)
    if not analogs:
        return []
    
    seen = set()
    unique = []
    for a in analogs:
        if a["smiles"] not in seen:
            seen.add(a["smiles"])
            unique.append(a)
    
    return unique


# ── Registry ─────────────────────────────────────────────────────────────────

ANALOG_GENERATORS: dict[str, Callable] = {
    "default": _default_generator,
    "bioisostere_only": _bioisostere_only,
    "mmp_only": _mmp_only,
}


def get_generator(strategy: str = "default") -> Callable:
    """
    Get an analog generator function by strategy name.
    
    Args:
        strategy: One of "default", "bioisostere_only", "mmp_only".
                  Falls back to "default" if unknown.
    
    Returns:
        A callable with signature (smiles: str, target_liability: str) -> list[dict]
    """
    gen = ANALOG_GENERATORS.get(strategy)
    if gen is None:
        import logging
        logging.getLogger("edeon_workflows").warning(
            f"Unknown analog strategy '{strategy}', falling back to 'default'."
        )
        gen = ANALOG_GENERATORS["default"]
    return gen


def register_generator(name: str, func: Callable) -> None:
    """
    Register a custom analog generator.
    
    This allows third-party or experimental generators (CReM, REINVENT, etc.)
    to be plugged in at runtime.
    
    Args:
        name: Strategy name to register.
        func: Callable with signature (smiles: str, target_liability: str) -> list[dict]
    """
    ANALOG_GENERATORS[name] = func
