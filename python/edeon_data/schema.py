from __future__ import annotations
from typing import Optional, Literal, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class CuratedRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    # Identity
    inchikey: str = Field(..., description="Canonical InChIKey (14-block) of curated structure")
    smiles_canonical: str = Field(..., description="Canonical SMILES after standardisation")
    smiles_original: Optional[str] = Field(None, description="Original SMILES from source")
    cas: Optional[str] = None
    name: Optional[str] = None
    chembl_id: Optional[str] = None  # If aligned to ChEMBL

    # Endpoint
    endpoint: str = Field(..., description="Canonical Endpoint enum value")
    value: float = Field(..., description="Numeric value (regression) or class index (classification)")
    value_units: str = Field(..., description="Original units before transformation")
    value_log: Optional[float] = Field(
        None,
        description="log10-transformed value where applicable (e.g. pLC50 = -log10(LC50_molar))"
    )
    value_class: Optional[str] = Field(
        None,
        description="Categorical class label for classification endpoints"
    )

    # Test context (ecotox / tox endpoints)
    species: Optional[str] = None
    species_taxonomy: Optional[str] = None  # e.g. "Animalia;Arthropoda;Insecta;Hymenoptera"
    test_type: Optional[str] = None  # OECD guideline if known
    exposure_route: Optional[str] = None  # "oral", "contact", "inhalation"
    exposure_duration_h: Optional[float] = None
    effect: Optional[str] = None  # "mortality", "growth_inhibition"

    # Provenance
    source: str = Field(..., description="Source dataset identifier, e.g. 'ApisTox-v1.0'")
    source_ref: Optional[str] = Field(None, description="DOI or URL for source")
    source_record_id: Optional[str] = None  # ID in source database
    year_reported: Optional[int] = Field(None, description="Year of original measurement; used for time-split")

    # Aggregation
    aggregation_n: int = Field(1, description="Number of raw records aggregated into this row")
    aggregation_method: Optional[Literal["mean", "median", "geomean", "majority_vote", "single"]] = "single"
    aggregation_cv: Optional[float] = Field(None, description="Coefficient of variation across aggregated records")

    # Quality
    quality_flags: List[str] = Field(default_factory=list, description="Curation warnings for this record")


class SourceMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    citation: str
    doi: Optional[str] = None
    url: Optional[str] = None
    license: Optional[str] = None
    access_date: Optional[str] = None
    raw_records: Optional[int] = None


class StandardisationMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)
    tool: str = "chembl_structure_pipeline"
    version: str
    tautomer: str = "rdkit-canonical"
    atom_allowlist: List[str] = Field(default_factory=list)
    mw_range: List[float] = Field(default_factory=list)


class ActivityMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)
    units_canonical: str
    log_transform: Optional[str] = None
    aggregation: Optional[str] = None
    censored_handling: Optional[str] = None


class CurationSummary(BaseModel):
    model_config = ConfigDict(frozen=True)
    raw_records: int
    after_parse: int
    after_standardisation: int
    after_filter: int
    after_aggregation: int
    rejection_rate: float


class ScaffoldSplitMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)
    train: int
    cal: int
    test: int
    test_to_train_nn_tanimoto_mean: Optional[float] = None


class RandomSplitMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)
    train: int
    cal: int
    test: int
    seed: int = 42


class TimeSplitMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)
    train: int
    cal: int
    test: int
    train_year_max: Optional[int] = None
    cal_year_range: Optional[List[int]] = None
    test_year_range: Optional[List[int]] = None
    status: Optional[str] = None


class SplitsMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)
    scaffold: ScaffoldSplitMetadata
    random: RandomSplitMetadata
    time: Optional[TimeSplitMetadata] = None


class DataCard(BaseModel):
    model_config = ConfigDict(frozen=True)
    dataset_id: str
    endpoint: str
    version: str
    created: str
    created_by: str = "edeon-data-pipeline"
    sources: List[SourceMetadata] = Field(default_factory=list)
    inclusion_criteria: List[str] = Field(default_factory=list)
    exclusion_criteria: List[str] = Field(default_factory=list)
    standardisation: StandardisationMetadata
    activity: ActivityMetadata
    curation_summary: CurationSummary
    splits: SplitsMetadata
    known_biases: List[str] = Field(default_factory=list)
    intended_use: str
    not_intended_for: List[str] = Field(default_factory=list)
    sha256: Dict[str, str] = Field(default_factory=dict)
