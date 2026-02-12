import os
import json
from pathlib import Path
from datetime import datetime

from edeon_data.schema import (
    DataCard,
    SourceMetadata,
    StandardisationMetadata,
    ActivityMetadata,
    CurationSummary,
    SplitsMetadata,
    ScaffoldSplitMetadata,
    RandomSplitMetadata,
    TimeSplitMetadata
)
from edeon_data.shared.io import write_data_card, write_manifest, get_file_sha256

def run_card(endpoint: str = None) -> None:
    """Compiles the structured DataCard YAML and generates the release manifest for rat LD50."""
    endpoint = "rat_acute_oral_ld50"
    curated_dir = Path(f"/home/svakal/Projects/Edeon/data/curated/{endpoint}/v1.0")
    
    # 1. Load curation stats
    stats_path = curated_dir / "curation_stats.json"
    if not stats_path.exists():
        raise FileNotFoundError(f"Curation stats not found at {stats_path}. Run curate first.")
    with open(stats_path) as f:
        stats = json.load(f)
        
    # 2. Load splits metadata
    splits_path = curated_dir / "splits_metadata.json"
    if not splits_path.exists():
        raise FileNotFoundError(f"Splits metadata not found at {splits_path}. Run split first.")
    with open(splits_path) as f:
        splits_meta = json.load(f)
        
    # Calculate curated.parquet hash
    pq_path = curated_dir / "curated.parquet"
    curated_hash = get_file_sha256(pq_path)
    
    # Compile SHA-256 dict
    hashes_dict = splits_meta["hashes"].copy()
    hashes_dict["curated_parquet"] = curated_hash
    
    # Build Pydantic models for DataCard
    source_info = SourceMetadata(
        name="NICEATM ICE / CATMoS",
        citation="Mansouri K, et al. (2021). Environ Health Perspect 129:47013.",
        doi="10.1289/EHP8495",
        url="https://doi.org/10.1289/EHP8495",
        license="Public Domain (US Government)",
        access_date="2026-05-30",
        raw_records=stats["raw_records"]
    )
    
    std_info = StandardisationMetadata(
        tool="chembl_structure_pipeline",
        version="1.2.4",
        tautomer="rdkit-canonical",
        atom_allowlist=["H", "B", "C", "N", "O", "F", "Si", "P", "S", "Cl", "Se", "Br", "I"],
        mw_range=[50.0, 1500.0]
    )
    
    act_info = ActivityMetadata(
        units_canonical="mg/kg bw",
        log_transform="log10_molar",
        aggregation="geometric_mean",
        censored_handling="flagged_kept"
    )
    
    summary_info = CurationSummary(
        raw_records=stats["raw_records"],
        after_parse=stats["after_parse"],
        after_standardisation=stats["after_standardisation"],
        after_filter=stats["after_filter"],
        after_aggregation=stats["after_aggregation"],
        rejection_rate=stats["rejection_rate"]
    )
    
    splits_info = SplitsMetadata(
        scaffold=ScaffoldSplitMetadata(
            train=splits_meta["scaffold"]["train"],
            cal=splits_meta["scaffold"]["cal"],
            test=splits_meta["scaffold"]["test"],
            test_to_train_nn_tanimoto_mean=splits_meta["scaffold"]["test_to_train_nn_tanimoto_mean"]
        ),
        random=RandomSplitMetadata(
            train=splits_meta["random"]["train"],
            cal=splits_meta["random"]["cal"],
            test=splits_meta["random"]["test"],
            seed=splits_meta["random"]["seed"]
        ),
        time=TimeSplitMetadata(
            train=0,
            cal=0,
            test=0,
            status="not_available"
        )
    )
    
    inclusion = [
        "In vivo rat acute oral toxicity records only (LD50)",
        "NICEATM ICE / CATMoS compiled inventory"
    ]
    
    exclusion = [
        "Mixtures, formulations, or records with missing structures",
        "Non-positive numeric values (cannot log-transform)",
        "Compounds containing atoms outside default organic allowlist"
    ]
    
    biases = [
        "Over-represents industrial chemicals and legacy pesticide compounds relative to modern pesticide discovery chemistry."
    ]
    
    not_intended = [
        "Direct regulatory dossier submission without supplementary dossier review",
        "Quantitative human risk assessment"
    ]
    
    card = DataCard(
        dataset_id=f"edeon-{endpoint.replace('_', '-')}-v1.0",
        endpoint=endpoint,
        version="1.0.0",
        created=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        created_by="edeon-data-pipeline",
        sources=[source_info],
        inclusion_criteria=inclusion,
        exclusion_criteria=exclusion,
        standardisation=std_info,
        activity=act_info,
        curation_summary=summary_info,
        splits=splits_info,
        known_biases=biases,
        intended_use="Training and benchmarking Tier-1 QSAR rat acute oral LD50 prediction models.",
        not_intended_for=not_intended,
        sha256=hashes_dict
    )
    
    # Save Data Card
    write_data_card(card, curated_dir / "data_card.yaml")
    
    # Generate final manifest.json
    write_manifest(curated_dir)
    print(f"DataCard and release manifest constructed for '{endpoint}'.")
