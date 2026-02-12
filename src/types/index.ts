/* ==========================================================
   Edeon Desktop — TypeScript Types
   ========================================================== */

export type RiskLevel = 'Low' | 'Med' | 'High';

export type StageStatus = 'done' | 'running' | 'waiting';

export type ViewId = 'library' | 'workflows' | 'knowledge' | 'models' | 'reports';

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
  violations: string | null;
  score: number | null;
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
