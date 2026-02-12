# Pesticide presets and MPO weights for Edeon workflows
# Profiles configured for different agrochemical use classes

MPO_PRESETS = {
    "Herbicide": {
        "weights": {
            "pesticide_likeness": 2.0,
            "selectivity": 2.0,
            "resistance": 1.0,
            "toxicity": 2.0
        },
        "tice_class": "herbicide"
    },
    "Insecticide": {
        "weights": {
            "pesticide_likeness": 1.5,
            "selectivity": 3.0,
            "resistance": 1.0,
            "toxicity": 2.0
        },
        "tice_class": "insecticide"
    },
    "Fungicide": {
        "weights": {
            "pesticide_likeness": 1.5,
            "selectivity": 2.0,
            "resistance": 2.0,
            "toxicity": 2.0
        },
        "tice_class": "fungicide"
    }
}
