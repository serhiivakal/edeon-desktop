use serde::{Deserialize, Serialize};
use chrono::{DateTime, Utc};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Endpoint {
    BeeAcuteOralLd50,
    BeeAcuteContactLd50,
    FishAcuteLc50,
    DaphniaAcuteEc50,
    AlgaeGrowthEc50,
    EarthwormAcuteLc50,
    BirdAcuteOralLd50,
    RatAcuteOralLd50,
    SkinSensitization,
    EyeIrritation,
    SoilKoc,
    SoilDt50,
    GusIndex,
    Bcf,
    PhotostabilityClass,
    PesticideLikenessTice,
    Logp,
    Pka,
    Solubility,
    HenrysLaw,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum AdStatus {
    In,
    Borderline,
    Out,
    Unknown,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(tag = "kind", rename_all = "lowercase")]
pub enum PredictionValue {
    Numeric { numeric: f64 },
    Categorical { categorical: String },
    Binary { binary: bool },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Prediction {
    pub smiles: String,
    pub endpoint: Endpoint,
    pub value: PredictionValue,
    pub ci_lower: Option<f64>,
    pub ci_upper: Option<f64>,
    #[serde(default = "default_ci_level")]
    pub ci_level: f64,
    pub ad_status: AdStatus,
    pub ad_score: Option<f64>,
    pub units: String,
    pub model_id: String,
    pub model_version: String,
    pub tier: u8,
    pub timestamp: DateTime<Utc>,
    #[serde(default)]
    pub provenance: serde_json::Value,
    #[serde(default)]
    pub warnings: Vec<String>,
}

fn default_ci_level() -> f64 {
    0.95
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TrainingDataInfo {
    pub n_compounds: usize,
    pub sources: Vec<String>,
    pub sha256: Option<String>,
    pub split_strategy: Option<String>,
    pub license: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PerformanceMetrics {
    pub metrics: std::collections::HashMap<String, f64>,
    pub test_set_n: Option<usize>,
    pub cv_folds: Option<usize>,
    pub calibration_coverage_95: Option<f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AdDefinition {
    pub method: String,
    pub threshold: Option<f64>,
    pub k: Option<usize>,
    pub training_set_size: Option<usize>,
    pub notes: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelCard {
    pub model_id: String,
    pub name: String,
    pub version: String,
    pub tier: u8,
    pub endpoint: Endpoint,
    pub description: String,
    pub intended_use: String,
    #[serde(default)]
    pub not_intended_for: Vec<String>,
    pub training_data: Option<TrainingDataInfo>,
    pub performance: Option<PerformanceMetrics>,
    pub applicability_domain: Option<AdDefinition>,
    pub uncertainty_method: Option<String>,
    #[serde(default)]
    pub known_failure_modes: Vec<String>,
    #[serde(default)]
    pub references: Vec<String>,
    pub license: String,
    pub created: DateTime<Utc>,
    #[serde(default)]
    pub authors: Vec<String>,
}
