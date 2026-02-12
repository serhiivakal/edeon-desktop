try:
    from enum import StrEnum
except ImportError:
    from enum import Enum
    class StrEnum(str, Enum):
        pass

class Endpoint(StrEnum):
    BEE_ACUTE_ORAL_LD50 = "bee_acute_oral_ld50"
    BEE_ACUTE_CONTACT_LD50 = "bee_acute_contact_ld50"
    FISH_ACUTE_LC50 = "fish_acute_lc50"
    DAPHNIA_ACUTE_EC50 = "daphnia_acute_ec50"
    ALGAE_GROWTH_EC50 = "algae_growth_ec50"
    EARTHWORM_ACUTE_LC50 = "earthworm_acute_lc50"
    BIRD_ACUTE_ORAL_LD50 = "bird_acute_oral_ld50"
    RAT_ACUTE_ORAL_LD50 = "rat_acute_oral_ld50"
    SKIN_SENSITIZATION = "skin_sensitization"
    EYE_IRRITATION = "eye_irritation"
    SOIL_KOC = "soil_koc"
    SOIL_DT50 = "soil_dt50"
    GUS_INDEX = "gus_index"
    BCF = "bcf"
    PHOTOSTABILITY_CLASS = "photostability_class"
    PESTICIDE_LIKENESS_TICE = "pesticide_likeness_tice"
    LOGP = "logp"
    PKA = "pka"
    SOLUBILITY = "solubility"
    HENRYS_LAW = "henrys_law"

def endpoint_metadata(ep: Endpoint) -> dict:
    """Returns metadata (description, units, direction) for the canonical endpoint."""
    metadata = {
        Endpoint.BEE_ACUTE_ORAL_LD50: {
            "description": "Honeybee acute oral LD50",
            "units": "µg/bee",
            "direction": "Lower = more toxic"
        },
        Endpoint.BEE_ACUTE_CONTACT_LD50: {
            "description": "Honeybee acute contact LD50",
            "units": "µg/bee",
            "direction": "Lower = more toxic"
        },
        Endpoint.FISH_ACUTE_LC50: {
            "description": "Fish acute LC50 (multispecies, default rainbow trout)",
            "units": "mg/L",
            "direction": "Lower = more toxic"
        },
        Endpoint.DAPHNIA_ACUTE_EC50: {
            "description": "Daphnia magna 48h acute EC50",
            "units": "mg/L",
            "direction": "Lower = more toxic"
        },
        Endpoint.ALGAE_GROWTH_EC50: {
            "description": "Algae 72h growth EC50 (Raphidocelis)",
            "units": "mg/L",
            "direction": "Lower = more toxic"
        },
        Endpoint.EARTHWORM_ACUTE_LC50: {
            "description": "Earthworm 14d LC50 (E. fetida)",
            "units": "mg/kg soil",
            "direction": "Lower = more toxic"
        },
        Endpoint.BIRD_ACUTE_ORAL_LD50: {
            "description": "Bird acute oral LD50 (default bobwhite quail)",
            "units": "mg/kg bw",
            "direction": "Lower = more toxic"
        },
        Endpoint.RAT_ACUTE_ORAL_LD50: {
            "description": "Rat acute oral LD50",
            "units": "mg/kg bw",
            "direction": "Lower = more toxic"
        },
        Endpoint.SKIN_SENSITIZATION: {
            "description": "Skin sensitization (binary or 4-class GHS)",
            "units": "category",
            "direction": "Higher = more concern"
        },
        Endpoint.EYE_IRRITATION: {
            "description": "Eye irritation (3-class GHS)",
            "units": "category",
            "direction": "Higher = more concern"
        },
        Endpoint.SOIL_KOC: {
            "description": "Soil organic carbon partition coefficient",
            "units": "L/kg",
            "direction": "Higher = more sorbed"
        },
        Endpoint.SOIL_DT50: {
            "description": "Soil degradation half-life",
            "units": "days",
            "direction": "Higher = more persistent"
        },
        Endpoint.GUS_INDEX: {
            "description": "Gustafson groundwater ubiquity score",
            "units": "unitless",
            "direction": "Higher = more leaching risk"
        },
        Endpoint.BCF: {
            "description": "Bioconcentration factor",
            "units": "L/kg",
            "direction": "Higher = more bioaccumulative"
        },
        Endpoint.PHOTOSTABILITY_CLASS: {
            "description": "Qualitative photostability category",
            "units": "category",
            "direction": "—"
        },
        Endpoint.PESTICIDE_LIKENESS_TICE: {
            "description": "Tice rule violations count",
            "units": "integer",
            "direction": "Lower = more pesticide-like"
        },
        Endpoint.LOGP: {
            "description": "Octanol-water partition coefficient",
            "units": "unitless",
            "direction": "—"
        },
        Endpoint.PKA: {
            "description": "Acidic and basic dissociation constants",
            "units": "pH units",
            "direction": "—"
        },
        Endpoint.SOLUBILITY: {
            "description": "Water solubility",
            "units": "mg/L",
            "direction": "Lower = less soluble"
        },
        Endpoint.HENRYS_LAW: {
            "description": "Henry's Law constant",
            "units": "atm-m³/mol",
            "direction": "—"
        }
    }
    
    # Allow passing string representations as well
    resolved_ep = Endpoint(ep)
    if resolved_ep in metadata:
        return metadata[resolved_ep]
    raise ValueError(f"Unknown endpoint: {ep}")
