"""
Edeon Engine — Systemic Mobility Classifier & Domain Assessment
"""

from typing import Dict, Any
from rdkit import Chem
from rdkit.Chem import Descriptors, Crippen

from .kleier import calculate_kleier_indices
from .bromilow import calculate_bromilow_cf
from ..speciation.pka import estimate_pka
from ..speciation.enumerate import enumerate_protonation_states


def classify_systemic_mobility(
    smiles: str,
    ph_apoplast: float = 5.5,
    ph_phloem: float = 8.0
) -> Dict[str, Any]:
    """Calculate systemic mobility classification, concentration factor, and driver analysis.

    Returns dict matching IPC schema.
    """
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {
            "ok": False,
            "error": "Invalid SMILES string"
        }

    log_kow = round(float(Crippen.MolLogP(mol)), 2)
    mw = round(float(Descriptors.MolWt(mol)), 1)
    pka_values = estimate_pka(smiles)

    primary_pka = min(pka_values) if pka_values else None
    log_pm, xylem_index, phloem_index = calculate_kleier_indices(log_kow, mw, primary_pka)
    phloem_cf = calculate_bromilow_cf(pka_values, ph_apoplast, ph_phloem)

    # Determine dominant charge in apoplast (pH 5.5)
    variants, _ = enumerate_protonation_states(smiles, ph_min=ph_apoplast, ph_max=ph_apoplast)
    dominant_charge_apo = variants[0]["charge"] if variants else 0

    # Classification logic
    if phloem_cf > 2.5 and -0.5 <= log_kow <= 3.5:
        if xylem_index > 0.4:
            mobility_class = "ambimobile"
        else:
            mobility_class = "phloem"
    elif xylem_index > 0.5 and log_kow <= 2.5:
        mobility_class = "xylem"
    elif log_kow > 4.0 or log_kow < -2.0:
        mobility_class = "immobile"
    elif phloem_index > 0.8:
        mobility_class = "phloem"
    else:
        mobility_class = "immobile"

    # Confidence assessment
    if -1.0 <= log_kow <= 4.0 and 150 <= mw <= 500:
        confidence = "in_domain"
    elif -2.0 <= log_kow <= 5.0 and 100 <= mw <= 700:
        confidence = "edge"
    else:
        confidence = "out_of_domain"

    return {
        "ok": True,
        "class": mobility_class,
        "phloem_concentration_factor": phloem_cf,
        "xylem_index": xylem_index,
        "phloem_index": phloem_index,
        "log_pm": log_pm,
        "drivers": {
            "logkow": log_kow,
            "mw": mw,
            "pka": pka_values,
            "dominant_charge_apoplast": dominant_charge_apo
        },
        "confidence": confidence
    }
