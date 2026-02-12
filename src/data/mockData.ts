/* ==========================================================
   Edeon Desktop — Mock Data
   All data matches the SVG mockup scenario exactly:
   "Resistance-Aware Lead Optimization" workflow running on
   "Glyphosate Analogs Q1" project
   ========================================================== */

import type {
  Project,
  PipelineStage,
  CompoundResult,
  CompoundDetail,
  RecentWorkflow,
  WorkflowState,
} from '../types';

// ── Projects ────────────────────────────────────────────────
export const mockProjects: Project[] = [
  { id: 'p1', name: 'Glyphosate analogs Q1', compoundCount: 12, isActive: true },
  { id: 'p2', name: 'Bee-safe insecticides', compoundCount: 8, isActive: false },
  { id: 'p3', name: 'Fungicide library 2026', compoundCount: 31, isActive: false },
  { id: 'p4', name: 'DEL hits batch 14', compoundCount: 1242, isActive: false },
];

// ── Workflow State ──────────────────────────────────────────
export const mockWorkflow: WorkflowState = {
  name: 'Resistance-Aware Lead Optimization',
  status: 'running',
  progressPercent: 42,
  stagesComplete: 3,
  totalStages: 6,
  compoundsActive: 247,
  startedAgo: '8 min ago',
};

// ── Pipeline Stages ─────────────────────────────────────────
export const mockStages: PipelineStage[] = [
  {
    id: 1,
    name: 'Standardize',
    description: 'Salts, tautomers',
    status: 'done',
    compoundCount: 1000,
    compoundLabel: 'compounds',
  },
  {
    id: 2,
    name: 'Pesticide-likeness',
    description: 'Tice rules filter',
    status: 'done',
    compoundCount: 247,
    compoundLabel: 'passed',
  },
  {
    id: 3,
    name: 'Cross-species',
    description: 'Selectivity scoring',
    status: 'done',
    compoundCount: 247,
    compoundLabel: 'scored',
  },
  {
    id: 4,
    name: 'Resistance',
    description: 'Hotspot analysis',
    status: 'running',
    progressPercent: 42,
    progressLabel: '42% · 104/247',
  },
  {
    id: 5,
    name: 'MPO scoring',
    description: 'Multi-parameter',
    status: 'waiting',
  },
  {
    id: 6,
    name: 'Final ranking',
    description: 'Top candidates',
    status: 'waiting',
  },
];

// ── Compound Results ────────────────────────────────────────
export const mockCompounds: CompoundResult[] = [
  {
    id: 'c1', name: 'GLY-247', subtitle: 'Selected',
    smiles: 'OC(=O)CN(F)CP(=O)(O)O',
    pesticideLikeness: 'High', selectivity: '12.4×',
    resistance: 'Low', score: 8.9, isSelected: true,
  },
  {
    id: 'c2', name: 'GLY-189', subtitle: 'Glyphosate F-3 analog',
    smiles: 'OC(=O)CNCP(F)(=O)O',
    pesticideLikeness: 'High', selectivity: '9.7×',
    resistance: 'Med', score: 8.2,
  },
  {
    id: 'c3', name: 'GLY-203', subtitle: 'Cl substitution',
    smiles: 'OC(=O)CNCP(=O)(Cl)O',
    pesticideLikeness: 'High', selectivity: '8.1×',
    resistance: 'Low', score: 7.8,
  },
  {
    id: 'c4', name: 'GLY-142', subtitle: 'Methylated derivative',
    smiles: 'OC(=O)CN(C)CP(=O)(O)O',
    pesticideLikeness: 'Med', selectivity: '7.3×',
    resistance: 'Low', score: 7.5,
  },
  {
    id: 'c5', name: 'GLY-077', subtitle: 'Phosphate ester',
    smiles: 'OC(=O)CNCP(=O)(OC)OC',
    pesticideLikeness: 'High', selectivity: '6.8×',
    resistance: 'Med', score: 6.9,
  },
  {
    id: 'c6', name: 'GLY-118', subtitle: 'N-ethyl variant',
    smiles: 'OC(=O)CN(CC)CP(=O)(O)O',
    pesticideLikeness: 'Med', selectivity: '6.2×',
    resistance: 'High', score: 5.4,
  },
];

// ── Selected Compound Detail (GLY-247) ──────────────────────
export const mockSelectedCompound: CompoundDetail = {
  name: 'GLY-247',
  smiles: 'OC(=O)CN(F)CP(=O)(O)O',
  properties: [
    { label: 'MW', value: '187.05 g/mol' },
    { label: 'LogP', value: '-2.04' },
    { label: 'TPSA', value: '112.5 Å²' },
    { label: 'H-bond donors', value: '3' },
  ],
  selectivity: [
    { organism: 'Target weed', value: 'IC50 4 nM', detail: '98% conserved', level: 'safe' },
    { organism: 'Crop (wheat)', value: 'Safe', detail: 'Target absent', level: 'safe' },
    { organism: 'Honey bee', value: 'LD50 25 μg', detail: 'Moderate risk', level: 'moderate' },
    { organism: 'Mammal', value: 'LD50 5600', detail: 'Low risk', level: 'safe' },
  ],
  resistance: [
    { label: 'EPSPS hotspots', value: '2 of 7' },
    { label: 'Cross-resistance', value: 'Low (HRAC G)' },
    { label: 'Predicted persistence', value: '~5 generations' },
  ],
};

// ── Recent Workflows ────────────────────────────────────────
export const mockRecentWorkflows: RecentWorkflow[] = [
  { name: 'DEL hit triage', meta: '2h ago · 1000 cmpds' },
  { name: 'Regulatory check', meta: 'Yesterday · 247 cmpds' },
  { name: 'Bee toxicity panel', meta: '3d ago · 48 cmpds' },
];
