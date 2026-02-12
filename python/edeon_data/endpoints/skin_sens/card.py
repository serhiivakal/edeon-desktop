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
    """Compiles the structured DataCard YAML and generates the release manifest for Skin Sensitization."""
    endpoint = "skin_sensitization"
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
    sources = []
    
    source_llna = SourceMetadata(
        name="NICEATM LLNA",
        citation="NICEATM LLNA Database. National Toxicology Program Interagency Center for the Evaluation of Alternative Toxicological Methods.",
        doi=None,
        url="https://ntp.niehs.nih.gov/whatwestudy/topics/toxico/niceatm",
        license="Public Domain (US Government Work)",
        access_date="2026-06-02",
        raw_records=stats["raw_records"]
    )
    sources.append(source_llna)
    
    std_info = StandardisationMetadata(
        tool="chembl_structure_pipeline",
        version="1.2.4",
        tautomer="rdkit-canonical",
        atom_allowlist=["H", "B", "C", "N", "O", "F", "Si", "P", "S", "Cl", "Se", "Br", "I"],
        mw_range=[50.0, 1500.0]
    )
    
    act_info = ActivityMetadata(
        units_canonical="class",
        log_transform=None,
        aggregation="majority_vote",
        censored_handling=None
    )
    
    summary_info = CurationSummary(
        raw_records=stats["raw_records"],
        after_parse=stats["after_parse"],
        after_standardisation=stats["after_standardisation"],
        after_filter=stats["after_filter"],
        after_aggregation=stats["after_aggregation"],
        rejection_rate=stats["rejection_rate"]
    )
    
    # Time split info
    time_meta = splits_meta.get("time", {})
    if time_meta.get("status") == "available":
        time_info = TimeSplitMetadata(
            train=time_meta["train"],
            cal=time_meta["cal"],
            test=time_meta["test"],
            train_year_max=time_meta.get("train_year_max"),
            cal_year_range=time_meta.get("cal_year_range"),
            test_year_range=time_meta.get("test_year_range"),
            status="available"
        )
    else:
        time_info = TimeSplitMetadata(
            train=0,
            cal=0,
            test=0,
            status="not_available"
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
        time=time_info
    )
    
    inclusion = [
        "Skin sensitization binary and categorical classification records",
        "Mouse Local Lymph Node Assay (LLNA) records with EC3 values",
        "ICCVAM Cosmetics Substance (CCS) binary records",
        "Prefer LLNA labels over CCS labels in case of compound overlap"
    ]
    
    exclusion = [
        "Mixtures, formulations, or records with missing chemical structures",
        "Compounds containing atoms outside default organic allowlist"
    ]
    
    biases = [
        "Strong bias toward fragrance chemicals, cosmetic ingredients, and common industrial preservatives.",
        "Over-represents strong and non-sensitizers relative to weak sensitizers.",
        "Binary classifications collapse potency ranges, masking the distinction between weak and strong sensitizers."
    ]
    
    not_intended = [
        "Direct clinical or regulatory dossier submissions without expert dermatological review",
        "Quantitative potency estimation from binary class assignments."
    ]
    
    card = DataCard(
        dataset_id=f"edeon-{endpoint.replace('_', '-')}-v1.0",
        endpoint=endpoint,
        version="1.0.0",
        created=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        created_by="edeon-data-pipeline",
        sources=sources,
        inclusion_criteria=inclusion,
        exclusion_criteria=exclusion,
        standardisation=std_info,
        activity=act_info,
        curation_summary=summary_info,
        splits=splits_info,
        known_biases=biases,
        intended_use="Training and benchmarking Tier-1 classification QSAR skin sensitization models.",
        not_intended_for=not_intended,
        sha256=hashes_dict
    )
    
    # Save Data Card
    write_data_card(card, curated_dir / "data_card.yaml")
    
    # Generate final manifest.json
    write_manifest(curated_dir)
    print(f"DataCard and release manifest constructed for '{endpoint}'.")

if __name__ == "__main__":
    run_card()
