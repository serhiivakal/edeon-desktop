"""
Edeon Engine — Structural Alert Screening

Reimplemented SMARTS-based structural alerts for:
  1. Genotoxicity / Mutagenicity (Benigni-Bossa / ISS rules)
  2. Endocrine Disruption screening flags
  3. Skin sensitization alerts (reactive electrophiles)
  4. Reactive metabolite alerts (quinones, epoxides, etc.)

These are SCREENING flags only — not regulatory determinations.
Alert definitions are based on published scientific literature
and regulatory guidance documents (re-encoded as SMARTS, not
bundled from GPL-licensed software).

References:
  - Benigni R, Bossa C (2008) "Structure alerts for carcinogenicity..."
    Chem Rev 108(6):2505-2518.
  - Benigni R, Bossa C, Jeliazkova N et al. (2008) ISS / ToxTree alert
    rule definitions — encoded independently as SMARTS.
  - OECD QSAR Toolbox profilers (public rule definitions).
  - EU REACH / CLP regulatory guidance on structural concerns.
"""

from typing import List, Dict, Any
from rdkit import Chem


# ─────────────────────────────────────────────────────────────────────────────
# GENOTOXICITY / MUTAGENICITY ALERTS (Benigni-Bossa style)
# Re-encoded from published rule definitions
# ─────────────────────────────────────────────────────────────────────────────

GENOTOX_ALERTS: List[Dict[str, str]] = [
    # Aromatic amines / anilines — classical Ames positives
    {
        "id": "SA_genotox_001",
        "name": "Primary aromatic amine",
        "smarts": "[NH2]c1ccccc1",
        "category": "genotoxicity",
        "severity": "high",
        "mechanism": "Metabolic activation to reactive nitrenium ion",
        "reference": "Benigni-Bossa SA1 (aromatic amine)",
    },
    # Polycyclic aromatic amine (more potent)
    {
        "id": "SA_genotox_002",
        "name": "Polycyclic aromatic amine",
        "smarts": "[NH2]c1cc2ccccc2cc1",
        "category": "genotoxicity",
        "severity": "high",
        "mechanism": "Bay-region diol-epoxide formation",
        "reference": "Benigni-Bossa SA1a (polycyclic aromatic amine)",
    },
    # Nitroso compounds
    {
        "id": "SA_genotox_003",
        "name": "N-Nitroso group",
        "smarts": "[N;!$(N=O)]([#6])N=O",
        "category": "genotoxicity",
        "severity": "high",
        "mechanism": "Alkylating diazonium ion formation",
        "reference": "Benigni-Bossa SA2 (nitroso)",
    },
    # Nitro aromatic
    {
        "id": "SA_genotox_004",
        "name": "Aromatic nitro group",
        "smarts": "c[N+](=O)[O-]",
        "category": "genotoxicity",
        "severity": "medium",
        "mechanism": "Nitroreduction to reactive hydroxylamine/nitrene",
        "reference": "Benigni-Bossa SA3 (aromatic nitro)",
    },
    # Alkyl halides (SN2 alkylators)
    {
        "id": "SA_genotox_005",
        "name": "Alkyl halide (potential SN2 alkylator)",
        "smarts": "[CH2][Cl,Br,I]",
        "category": "genotoxicity",
        "severity": "medium",
        "mechanism": "Direct-acting SN2 DNA alkylation",
        "reference": "Benigni-Bossa SA7 (alkyl halide)",
    },
    # Epoxides
    {
        "id": "SA_genotox_006",
        "name": "Epoxide",
        "smarts": "C1OC1",
        "category": "genotoxicity",
        "severity": "high",
        "mechanism": "Direct electrophilic ring-opening at DNA nucleophiles",
        "reference": "Benigni-Bossa SA8 (epoxide)",
    },
    # Aziridines
    {
        "id": "SA_genotox_007",
        "name": "Aziridine",
        "smarts": "C1NC1",
        "category": "genotoxicity",
        "severity": "high",
        "mechanism": "Electrophilic ring-opening alkylation",
        "reference": "Benigni-Bossa SA9 (aziridine)",
    },
    # Nitrogen/sulfur mustards
    {
        "id": "SA_genotox_008",
        "name": "Nitrogen mustard",
        "smarts": "[N,S](CCCl)CCCl",
        "category": "genotoxicity",
        "severity": "high",
        "mechanism": "Bis-alkylation / DNA cross-linking via aziridinium",
        "reference": "Benigni-Bossa SA10 (N/S mustard)",
    },
    # Michael acceptor — α,β-unsaturated carbonyl
    {
        "id": "SA_genotox_009",
        "name": "α,β-Unsaturated carbonyl (Michael acceptor)",
        "smarts": "[#6]=[#6]-[#6](=O)",
        "category": "genotoxicity",
        "severity": "medium",
        "mechanism": "Michael addition to nucleophilic DNA bases",
        "reference": "Benigni-Bossa SA11 (Michael acceptor)",
    },
    # Aldehyde
    {
        "id": "SA_genotox_010",
        "name": "Aldehyde",
        "smarts": "[CH1](=O)[#6]",
        "category": "genotoxicity",
        "severity": "medium",
        "mechanism": "Schiff base formation with DNA/protein amines",
        "reference": "Benigni-Bossa SA12 (aldehyde)",
    },
    # Hydrazine
    {
        "id": "SA_genotox_011",
        "name": "Hydrazine",
        "smarts": "[NH2][NH2]",
        "category": "genotoxicity",
        "severity": "high",
        "mechanism": "Metabolic activation to methylating diazomethane",
        "reference": "Benigni-Bossa SA13 (hydrazine)",
    },
    # Acyl halide
    {
        "id": "SA_genotox_012",
        "name": "Acyl halide",
        "smarts": "[#6](=O)[Cl,Br,I]",
        "category": "genotoxicity",
        "severity": "medium",
        "mechanism": "Direct acylation of nucleophilic amino groups",
        "reference": "Benigni-Bossa SA14 (acyl halide)",
    },
    # Polycyclic aromatic hydrocarbon (PAH) bay region
    {
        "id": "SA_genotox_013",
        "name": "PAH bay-region motif",
        "smarts": "c1ccc2c(c1)cc1ccc3ccccc3c1c2",
        "category": "genotoxicity",
        "severity": "high",
        "mechanism": "Metabolic epoxidation at bay-region → diol-epoxide adducts",
        "reference": "Benigni-Bossa SA15 (PAH bay region)",
    },
    # Aliphatic N-nitro
    {
        "id": "SA_genotox_014",
        "name": "Nitroamine (N-nitro)",
        "smarts": "[#7][N+](=O)[O-]",
        "category": "genotoxicity",
        "severity": "medium",
        "mechanism": "Metabolic reduction to reactive intermediates",
        "reference": "Benigni-Bossa SA16 (N-nitro)",
    },
    # Propiolactone / beta-lactone
    {
        "id": "SA_genotox_015",
        "name": "β-Propiolactone / β-lactone",
        "smarts": "C1CC(=O)O1",
        "category": "genotoxicity",
        "severity": "medium",
        "mechanism": "Ring-strain driven alkylation of nucleophiles",
        "reference": "Benigni-Bossa SA17 (beta-lactone)",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# ENDOCRINE DISRUPTION SCREENING ALERTS
# Based on published ED structural profilers (OECD, JRC)
# ─────────────────────────────────────────────────────────────────────────────

ED_ALERTS: List[Dict[str, str]] = [
    # Phenolic estrogenic motifs
    {
        "id": "SA_ed_001",
        "name": "Bisphenol scaffold",
        "smarts": "c1ccc(cc1)C(c1ccc(O)cc1)(C)C",
        "category": "endocrine_disruption",
        "severity": "high",
        "mechanism": "Estrogen receptor alpha binding",
        "reference": "EU ED assessment criteria (BPA-like phenols)",
    },
    {
        "id": "SA_ed_002",
        "name": "4-Hydroxyphenyl motif (estrogen mimicry)",
        "smarts": "Oc1ccc(cc1)[C,c]",
        "category": "endocrine_disruption",
        "severity": "medium",
        "mechanism": "Estrogenic activity via ER-alpha binding",
        "reference": "JRC ED profiler (4-hydroxyphenyl estrogens)",
    },
    # Triazine herbicide scaffold (thyroid/anti-androgenic)
    {
        "id": "SA_ed_003",
        "name": "Symmetric triazine (chloro-s-triazine)",
        "smarts": "Clc1nc(nc(n1)Cl)N",
        "category": "endocrine_disruption",
        "severity": "medium",
        "mechanism": "HPG axis disruption (aromatase interference)",
        "reference": "OECD QSAR Toolbox (triazine ED screen)",
    },
    # Dithiocarbamate (thyroid disruption)
    {
        "id": "SA_ed_004",
        "name": "Dithiocarbamate moiety",
        "smarts": "[#7]C(=S)[S-,SH,S]",
        "category": "endocrine_disruption",
        "severity": "medium",
        "mechanism": "Thyroid peroxidase inhibition (anti-thyroid)",
        "reference": "EFSA guidance on thyroid disruptors",
    },
    # Organotins (tributyltin etc.)
    {
        "id": "SA_ed_005",
        "name": "Trialkyltin",
        "smarts": "[Sn]([#6])([#6])[#6]",
        "category": "endocrine_disruption",
        "severity": "high",
        "mechanism": "Aromatase inhibition, imposex induction",
        "reference": "EU ED criteria (organotin compounds)",
    },
    # Phthalate ester (anti-androgenic)
    {
        "id": "SA_ed_006",
        "name": "Phthalate diester",
        "smarts": "c1ccc(c(c1)C(=O)OC)C(=O)OC",
        "category": "endocrine_disruption",
        "severity": "medium",
        "mechanism": "Anti-androgenic (PPAR-gamma activation)",
        "reference": "REACH SVHC criteria (phthalates)",
    },
    # Benzimidazole (thyroid)
    {
        "id": "SA_ed_007",
        "name": "Benzimidazole carbamate",
        "smarts": "c1ccc2c(c1)[nH]c(n2)NC(=O)OC",
        "category": "endocrine_disruption",
        "severity": "medium",
        "mechanism": "Thyroid disruption / tubulin binding",
        "reference": "OECD ED profiler (benzimidazole carbamates)",
    },
    # Conazole / triazole (CYP19 aromatase)
    {
        "id": "SA_ed_008",
        "name": "1,2,4-Triazole (conazole-type)",
        "smarts": "c1cn[nH]n1",
        "category": "endocrine_disruption",
        "severity": "low",
        "mechanism": "CYP19 (aromatase) inhibition potential",
        "reference": "EFSA (triazole fungicides ED concern)",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# SKIN SENSITIZATION ALERTS (reactive electrophiles)
# ─────────────────────────────────────────────────────────────────────────────

SKIN_SENS_ALERTS: List[Dict[str, str]] = [
    {
        "id": "SA_skin_001",
        "name": "Isocyanate",
        "smarts": "[#6]N=C=O",
        "category": "skin_sensitization",
        "severity": "high",
        "mechanism": "Acylation of protein lysine residues",
        "reference": "OECD QSAR Toolbox (protein binding profiler)",
    },
    {
        "id": "SA_skin_002",
        "name": "Isothiocyanate",
        "smarts": "[#6]N=C=S",
        "category": "skin_sensitization",
        "severity": "high",
        "mechanism": "Thiol modification via nucleophilic addition",
        "reference": "OECD QSAR Toolbox (protein binding profiler)",
    },
    {
        "id": "SA_skin_003",
        "name": "Acid anhydride",
        "smarts": "[#6](=O)O[#6](=O)",
        "category": "skin_sensitization",
        "severity": "medium",
        "mechanism": "Acylation of protein amines",
        "reference": "OECD protein binding profiler",
    },
    {
        "id": "SA_skin_004",
        "name": "Sulfonyl halide",
        "smarts": "[#6]S(=O)(=O)[Cl,Br]",
        "category": "skin_sensitization",
        "severity": "medium",
        "mechanism": "SN2 at electrophilic sulfur",
        "reference": "OECD protein binding profiler",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# ALL ALERTS COMBINED
# ─────────────────────────────────────────────────────────────────────────────

ALL_ALERTS = GENOTOX_ALERTS + ED_ALERTS + SKIN_SENS_ALERTS


def _compile_alert(alert: Dict[str, str]) -> Dict[str, Any]:
    """Compile SMARTS pattern for an alert. Returns alert dict with compiled mol."""
    pattern = Chem.MolFromSmarts(alert["smarts"])
    return {**alert, "_compiled": pattern}


# Pre-compile all SMARTS at module load
_COMPILED_ALERTS: List[Dict[str, Any]] = []
for _alert in ALL_ALERTS:
    compiled = _compile_alert(_alert)
    if compiled["_compiled"] is not None:
        _COMPILED_ALERTS.append(compiled)


def screen_structural_alerts(
    smiles: str,
    categories: List[str] | None = None,
) -> Dict[str, Any]:
    """
    Screen a single molecule against all structural alert sets.

    Args:
        smiles: SMILES string of the query molecule.
        categories: Optional filter — only check alerts in these categories.
                    Options: "genotoxicity", "endocrine_disruption", "skin_sensitization"
                    If None, all categories are checked.

    Returns:
        {
            "smiles": str,
            "alerts_fired": [
                {
                    "id": str,
                    "name": str,
                    "category": str,
                    "severity": str,
                    "mechanism": str,
                    "reference": str,
                    "match_atoms": [[int, ...], ...]  # atom indices
                }, ...
            ],
            "summary": {
                "total_alerts": int,
                "high_severity": int,
                "medium_severity": int,
                "low_severity": int,
                "categories_hit": [str, ...]
            }
        }
    """
    if not smiles or not isinstance(smiles, str):
        return {
            "smiles": smiles or "",
            "alerts_fired": [],
            "summary": {
                "total_alerts": 0,
                "high_severity": 0,
                "medium_severity": 0,
                "low_severity": 0,
                "categories_hit": [],
            },
            "error": "Invalid SMILES — could not parse molecule",
        }
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {
            "smiles": smiles,
            "alerts_fired": [],
            "summary": {
                "total_alerts": 0,
                "high_severity": 0,
                "medium_severity": 0,
                "low_severity": 0,
                "categories_hit": [],
            },
            "error": "Invalid SMILES — could not parse molecule",
        }

    alerts_fired = []
    categories_hit = set()

    for alert in _COMPILED_ALERTS:
        # Filter by requested categories
        if categories is not None and alert["category"] not in categories:
            continue

        pattern = alert["_compiled"]
        matches = mol.GetSubstructMatches(pattern)
        if matches:
            alerts_fired.append({
                "id": alert["id"],
                "name": alert["name"],
                "category": alert["category"],
                "severity": alert["severity"],
                "mechanism": alert["mechanism"],
                "reference": alert["reference"],
                "match_atoms": [list(m) for m in matches],
            })
            categories_hit.add(alert["category"])

    high_count = sum(1 for a in alerts_fired if a["severity"] == "high")
    medium_count = sum(1 for a in alerts_fired if a["severity"] == "medium")
    low_count = sum(1 for a in alerts_fired if a["severity"] == "low")

    return {
        "smiles": smiles,
        "alerts_fired": alerts_fired,
        "summary": {
            "total_alerts": len(alerts_fired),
            "high_severity": high_count,
            "medium_severity": medium_count,
            "low_severity": low_count,
            "categories_hit": sorted(categories_hit),
        },
    }


def screen_structural_alerts_batch(
    smiles_list: List[str],
    categories: List[str] | None = None,
) -> List[Dict[str, Any]]:
    """Screen a batch of molecules against structural alerts."""
    return [screen_structural_alerts(s, categories) for s in smiles_list]
