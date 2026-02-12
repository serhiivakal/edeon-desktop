/* ==========================================================
   Edeon Desktop — TypeScript Types
   ========================================================== */

export type RiskLevel = 'Low' | 'Med' | 'High';

export type StageStatus = 'done' | 'running' | 'waiting';

export type ViewId = 'library' | 'workflows' | 'knowledge' | 'models' | 'reports' | 'settings' | 'viewer3d' | 'fate' | 'generation' | 'verification_report' | 'journal';

export interface GenerationCompound {
  smiles: string;
  docking_score: number;
  generation: number;
  parent_in_generation: string;
  predicted_properties: Record<string, any>;
  composite_score: number;
  mpo_score: number;
  rank_category: string;
}

export interface GenerationJobHistoryEntry {
  job_id: string;
  name: string;
  mode: string;
  parent_smiles: string | null;
  receptor_id: string | null;
  receptor_display_name: string | null;
  total_generated: number;
  total_docked: number;
  elapsed_seconds: number;
  completed_at: string;
  parameters?: Record<string, any>;
  results?: {
    best_compounds: GenerationCompound[];
    iterations: Array<{ iteration: number; compounds: GenerationCompound[] }>;
    total_compounds_generated: number;
    total_compounds_docked: number;
    elapsed_seconds: number;
  };
}

export interface Project {
  id: string;
  name: string;
  compoundCount: number;
  isActive: boolean;
}

export interface PipelineStage {
  id: number;
  name: string;
  description: string;
  status: StageStatus;
  enabled?: boolean;
  compoundCount?: number;
  compoundLabel?: string;       // e.g., "compounds", "passed", "scored"
  progressPercent?: number;     // only for running stages
  progressLabel?: string;       // e.g., "42% · 104/247"
}

export interface CompoundResult {
  id: string;
  name: string;
  subtitle: string;
  smiles: string;
  pesticideLikeness: RiskLevel;
  selectivity: string;         // e.g., "12.4×"
  resistance: RiskLevel;
  score: number;
  isSelected?: boolean;
}

export interface CompoundDetail {
  name: string;
  smiles: string;
  properties: { label: string; value: string }[];
  selectivity: SelectivityProfile[];
  resistance: { label: string; value: string }[];
}

export interface SelectivityProfile {
  organism: string;
  value: string;
  detail: string;
  level: 'safe' | 'moderate' | 'danger';
}

export interface ToxicityPrediction {
  organism: string;
  organism_latin: string;
  level: 'Low' | 'Med' | 'High';
  risk_score: number;
  detail: string;
  threshold: string;
}

export interface ApplicabilityDomain {
  status: 'in_domain' | 'borderline' | 'out_of_domain';
  confidence: number;
  warnings: string[];
}

export interface ToxicityResult {
  predictions: ToxicityPrediction[];
  overall_level: 'Low' | 'Med' | 'High';
  applicability_domain: ApplicabilityDomain;
  disabled?: boolean;
}

export interface MoaClassification {
  classification: 'HRAC' | 'IRAC' | 'FRAC';
  group: string;
  group_name: string;
  confidence: 'high' | 'moderate' | 'low';
  resistance_prevalence: string;
}

export interface CrossResistance {
  level: 'Low' | 'Med' | 'High';
  detail: string;
  related_groups: string[];
}

export interface RecentWorkflow {
  name: string;
  meta: string;          // e.g., "2h ago · 1000 cmpds"
}

export interface WorkflowState {
  name: string;
  status: 'running' | 'paused' | 'complete';
  progressPercent: number;
  stagesComplete: number;
  totalStages: number;
  compoundsActive: number;
  startedAgo: string;
}

// ── Backend-Synced Types (Phase 2) ──────────────────────────
// These mirror the Rust models exactly (snake_case from serde)

export interface ProjectRecord {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  compound_count: number;
}

export interface CompoundRecord {
  id: string;
  project_id: string;
  name: string;
  smiles: string;
  mol_weight: number | null;
  logp: number | null;
  tpsa: number | null;
  hbd: number | null;
  hba: number | null;
  rotatable_bonds: number | null;
  created_at: string;
}

export interface CompoundPage {
  compounds: CompoundRecord[];
  total: number;
  page: number;
  page_size: number;
}

// ── Backend-Synced Types (Phase 3) ──────────────────────────

export interface WorkflowRecord {
  id: string;
  project_id: string;
  name: string;
  status: 'running' | 'complete' | 'failed' | 'stopped';
  stages_complete: number;
  total_stages: number;
  compounds_processed: number;
  compounds_total: number;
  current_stage: string | null;
  started_at: string;
  completed_at: string | null;
  workflow_id?: string;
}

export interface WorkflowResultRecord {
  id: string;
  name: string;
  smiles: string;
  mol_weight: number | null;
  logp: number | null;
  tpsa: number | null;
  hbd: number | null;
  hba: number | null;
  rotatable_bonds: number | null;
  pesticide_likeness: string | null;  // "High", "Med", "Low"
  pesticide_likeness_disabled?: boolean;
  tice_violations: string[] | null;
  selectivity: {
    profiles: SelectivityEntry[];
    min_selectivity: number;
    overall_level: 'safe' | 'moderate' | 'danger';
    disabled?: boolean;
  } | null;
  resistance: {
    level: string;
    risk_score: number;
    factors: { factor: string; assessment: string; detail: string }[];
    moa_classification?: MoaClassification;
    cross_resistance?: CrossResistance;
    disabled?: boolean;
  } | null;
  toxicity: ToxicityResult | null;
  mpo: {
    score: number;
    breakdown: Record<string, number>;
    rank_category: 'Lead' | 'Candidate' | 'Deprioritize';
  } | null;
  score: number | null;
  pains_alerts?: string[];
  reactive_alerts?: string[];
  uq?: UqResultMap | null;
}

export interface SelectivityEntry {
  organism: string;
  selectivity_index: number;
  level: 'safe' | 'moderate' | 'danger';
  detail: string;
  ci_lower?: number;
  ci_upper?: number;
  ad_status?: string;
  ad_score?: number | null;
}

export interface WorkflowProgress {
  workflow_id: string;
  status: string;
  current_stage: string | null;
  stages_complete: number;
  total_stages: number;
  compounds_processed: number;
  compounds_total: number;
  stage_result?: {
    stage: string;
    status: string;
    compound_count: number;
  };
}

// ── Agrochemical Knowledge Base Types (Phase 5) ──────────────────
export interface RegulatoryStatus {
  eu_status: string;
  us_epa: string;
  mrl_eu: string;
  mrl_us: string;
  approval_period: string;
  hazard_classification: string;
}

export interface EcotoxEndpoints {
  honeybee_ld50: string;
  fish_lc50: string;
  bird_ld50: string;
  mammal_ld50: string;
  daphnia_ec50: string;
}

export interface ResistanceFactors {
  risk: string;
  hrac_irac: string;
  known_mutations: string;
}

export interface KnowledgeRecord {
  id: string;
  name: string;
  cas_number: string;
  formula: string;
  smiles: string;
  class: string;
  moa: string;
  regulatory_status: RegulatoryStatus;
  ecotox_endpoints: EcotoxEndpoints;
  resistance_factors: ResistanceFactors;
  source?: string;  // "Local" | "PubChem" | "ChEMBL" | "CompTox"
}
export interface PropertyFilters {
  mw_min?: number | null;
  mw_max?: number | null;
  logp_min?: number | null;
  logp_max?: number | null;
  tpsa_min?: number | null;
  tpsa_max?: number | null;
  hbd_min?: number | null;
  hbd_max?: number | null;
}

// ── 3D Molecular Viewer Scene Graph Types (Phase 42) ───────────
export type SubEntryType = 'chain' | 'ligand' | 'water' | 'ion' | 'cofactor' | 'pharmacophore';
export type EntryType = 'protein' | 'ligand' | 'pharmacophore';
export type ReprStyle =
  | 'cartoon' | 'ball+stick' | 'licorice' | 'spacefill'
  | 'surface' | 'ribbon' | 'backbone' | 'hyperball' | 'line' | 'hidden';

export interface SceneSubEntry {
  id: string;
  type: SubEntryType;
  name: string;            // e.g., "Chain A", "ATP (3)", "HOH (212)"
  selection: string;       // valid NGL selection string
  visible: boolean;
  repr: ReprStyle;
  color: string;           // hex; '__chainid' for chain-color, '__element' for element
  count?: number;          // residue/atom count for label
}

export interface SceneEntry {
  id: string;              // uuid
  type: EntryType;
  name: string;            // e.g., "1YBH", "ImazaquinAcid"
  pdbId?: string;
  expanded: boolean;
  visible: boolean;        // master toggle for the whole entry
  stageId: 1 | 2;
  children: SceneSubEntry[];
}

// ── Mirrored Predictor Core Types (Tauri & IPC Sync) ───────────
export type PredictorEndpoint =
  | 'bee_acute_oral_ld50'
  | 'bee_acute_contact_ld50'
  | 'fish_acute_lc50'
  | 'daphnia_acute_ec50'
  | 'algae_growth_ec50'
  | 'earthworm_acute_lc50'
  | 'bird_acute_oral_ld50'
  | 'rat_acute_oral_ld50'
  | 'skin_sensitization'
  | 'eye_irritation'
  | 'soil_koc'
  | 'soil_dt50'
  | 'gus_index'
  | 'bcf'
  | 'photostability_class'
  | 'pesticide_likeness_tice'
  | 'logp'
  | 'pka'
  | 'solubility'
  | 'henrys_law';

export type PredictorAdStatus = 'in' | 'borderline' | 'out' | 'unknown';

export type PredictionValue =
  | { kind: 'numeric'; numeric: number }
  | { kind: 'categorical'; categorical: string }
  | { kind: 'binary'; binary: boolean };

export interface Prediction {
  smiles: string;
  endpoint: PredictorEndpoint;
  value: PredictionValue;
  ci_lower: number | null;
  ci_upper: number | null;
  ci_level: number;
  ad_status: PredictorAdStatus;
  ad_score: number | null;
  units: string;
  model_id: string;
  model_version: string;
  tier: 1 | 2 | 3 | 4;
  timestamp: string;
  provenance: any;
  warnings: string[];
}

export interface TrainingDataInfo {
  n_compounds: number;
  sources: string[];
  sha256?: string | null;
  split_strategy?: string | null;
  license?: string | null;
}

export interface PerformanceMetrics {
  metrics: Record<string, number>;
  test_set_n?: number | null;
  cv_folds?: number | null;
  calibration_coverage_95?: number | null;
}

export interface AdDefinition {
  method: string;
  threshold?: number | null;
  k?: number | null;
  training_set_size?: number | null;
  notes?: string | null;
}

export interface ModelCard {
  model_id: string;
  name: string;
  version: string;
  tier: 1 | 2 | 3 | 4;
  endpoint: PredictorEndpoint;
  description: string;
  intended_use: string;
  not_intended_for: string[];
  training_data: TrainingDataInfo | null;
  performance: PerformanceMetrics | null;
  applicability_domain: AdDefinition | null;
  uncertainty_method: string | null;
  known_failure_modes: string[];
  references: string[];
  license: string;
  created: string;
  authors: string[];
}
export interface UqEnvelope {
  value: number | string | null;
  lower: number | null;
  upper: number | null;
  coverage: number;
  ad_status: 'in_domain' | 'borderline' | 'out_of_domain' | 'unknown';
  ad_score: number | null;
  model_id: string;
}

export type UqResultMap = Record<string, UqEnvelope>;
