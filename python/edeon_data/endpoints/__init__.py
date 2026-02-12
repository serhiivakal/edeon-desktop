"""Per-endpoint data curation pipelines."""

try:
    from edeon_models.endpoints import Endpoint
except ImportError:
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
