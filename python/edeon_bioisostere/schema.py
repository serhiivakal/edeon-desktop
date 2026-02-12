from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Literal, List, Dict, Any

class TransformationRule(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule_id: str = Field(..., description="Stable identifier (e.g. 'sbs_00042')")
    pattern_smarts: str = Field(..., description="SMARTS to match in query molecule")
    replacement_smarts: str = Field(..., description="SMARTS describing the substitution")
    reaction_smarts: str = Field(..., description="Full RDKit reaction SMARTS (pattern>>product)")
    source: Literal["swissbioisostere", "mmpdb_chembl_approved", "manual_curation"] = "swissbioisostere"
    source_reference: Optional[str] = Field(None, description="DOI, URL, or citation")
    context: Optional[str] = Field(None, description="Activity context if known (e.g. 'kinase inhibitors')")
    occurrence_frequency: int = Field(..., description="Count of occurrences in source database")
    occurrence_in_marketed_drugs: Optional[int] = Field(None, description="Count among approved drugs subset")
    direction_notes: Optional[str] = Field(None, description="Free-text directional notes if any")
    synthetic_complexity_delta: Optional[float] = Field(None, description="Expected change in SA score, if known")

class PredictionValue(BaseModel):
    value: float
    ci_lower: Optional[float] = None
    ci_upper: Optional[float] = None
    ad_status: str  # "IN", "OUT", etc.

class EndpointDelta(BaseModel):
    endpoint: str
    original_value: float
    original_ci_lower: Optional[float] = None
    original_ci_upper: Optional[float] = None
    original_ad_status: str
    transformed_value: float
    transformed_ci_lower: Optional[float] = None
    transformed_ci_upper: Optional[float] = None
    transformed_ad_status: str
    delta: float
    ad_warning: bool

class BioisostereSuggestion(BaseModel):
    rule: TransformationRule
    original_smiles: str
    transformed_smiles: str
    composite_score: float
    deltas: List[EndpointDelta]
