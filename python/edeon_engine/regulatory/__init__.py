"""
Edeon Engine — Registration Risk Assessment Package

Provides structural alerts (genotoxicity, endocrine disruption),
numeric regulatory cut-offs (PBT/vPvB, groundwater, CLP aquatic hazard),
and a combined per-criterion scorecard for agrochemical registration risk.

This is an IN-SILICO SCREENING tool — results are triage signals,
NOT regulatory determinations.
"""

from .alerts import screen_structural_alerts
from .cutoffs import evaluate_regulatory_cutoffs
from .scorecard import assess_registration_risk

__all__ = [
    "screen_structural_alerts",
    "evaluate_regulatory_cutoffs",
    "assess_registration_risk",
]
