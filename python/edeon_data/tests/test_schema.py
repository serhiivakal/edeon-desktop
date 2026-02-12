import pytest
from edeon_data.schema import CuratedRecord, DataCard

def test_curated_record_serialization():
    record_dict = {
        "inchikey": "UFHFLCQGBAWZMQ-UHFFFAOYSA-N",
        "smiles_canonical": "CCO",
        "smiles_original": "CCO",
        "cas": "64-17-5",
        "name": "ethanol",
        "chembl_id": "CHEMBL12345",
        "endpoint": "bee_acute_oral_ld50",
        "value": 12.5,
        "value_units": "ug/bee",
        "value_log": 1.0969,
        "value_class": None,
        "species": "Apis mellifera",
        "species_taxonomy": "Animalia;Arthropoda;Insecta;Hymenoptera",
        "test_type": "OECD 213",
        "exposure_route": "oral",
        "exposure_duration_h": 48.0,
        "effect": "mortality",
        "source": "ApisTox-v1.0",
        "source_ref": "10.1038/s41597-024-04232-w",
        "source_record_id": "rec123",
        "year_reported": 2025,
        "aggregation_n": 1,
        "aggregation_method": "single",
        "aggregation_cv": None,
        "quality_flags": ["some_flag"]
    }
    
    record = CuratedRecord(**record_dict)
    
    # Verify values
    assert record.inchikey == "UFHFLCQGBAWZMQ-UHFFFAOYSA-N"
    assert record.smiles_canonical == "CCO"
    assert record.value == 12.5
    assert record.quality_flags == ["some_flag"]
    
    # Verify round-trip
    dumped = record.model_dump()
    assert dumped == record_dict

def test_data_card_serialization():
    card_dict = {
        "dataset_id": "edeon-bee-v1.0",
        "endpoint": "bee_acute_oral_ld50",
        "version": "1.0.0",
        "created": "2026-06-01T10:00:00Z",
        "created_by": "edeon-data-pipeline",
        "sources": [
            {
                "name": "ApisTox",
                "citation": "Adamczyk J, Poziemski J, Siedlecki P (2025). Sci Data 12:5.",
                "doi": "10.1038/s41597-024-04232-w",
                "url": "https://zenodo.org/records/11062076",
                "license": "CC BY 4.0",
                "access_date": "2026-05-20",
                "raw_records": 1035
            }
        ],
        "inclusion_criteria": ["inclusion 1"],
        "exclusion_criteria": ["exclusion 1"],
        "standardisation": {
            "tool": "chembl_structure_pipeline",
            "version": "1.2.0",
            "tautomer": "rdkit-canonical",
            "atom_allowlist": ["H", "C", "O"],
            "mw_range": [50.0, 1500.0]
        },
        "activity": {
            "units_canonical": "ug/bee",
            "log_transform": "log10",
            "aggregation": "geometric_mean",
            "censored_handling": "flagged_kept"
        },
        "curation_summary": {
            "raw_records": 1035,
            "after_parse": 1029,
            "after_standardisation": 1018,
            "after_filter": 1002,
            "after_aggregation": 998,
            "rejection_rate": 0.036
        },
        "splits": {
            "scaffold": {
                "train": 698,
                "cal": 150,
                "test": 150,
                "test_to_train_nn_tanimoto_mean": 0.42
            },
            "random": {
                "train": 698,
                "cal": 150,
                "test": 150,
                "seed": 42
            },
            "time": None
        },
        "known_biases": ["bias 1"],
        "intended_use": "use 1",
        "not_intended_for": ["not for 1"],
        "sha256": {
            "curated_parquet": "hash123"
        }
    }
    
    card = DataCard(**card_dict)
    assert card.dataset_id == "edeon-bee-v1.0"
    assert card.sources[0].name == "ApisTox"
    assert card.splits.scaffold.train == 698
    
    # Verify round-trip
    dumped = card.model_dump()
    assert dumped == card_dict
