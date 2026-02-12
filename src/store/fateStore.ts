/* ==========================================================
   Edeon Desktop — Environmental Fate Store
   Zustand store for managing environmental fate predictions
   and transformation product pathways.
   ========================================================== */

import { create } from 'zustand';
import { invoke } from '@tauri-apps/api/core';
import type { Prediction } from '../types';

export interface EnvironmentalFateResult {
  smiles: string;
  dt50_soil: Prediction;
  koc: Prediction;
  bcf: Prediction;
  log_kow: Prediction;
  henry: Prediction;
  gus: Prediction & { class: 'leacher' | 'transition' | 'non-leacher' | 'unknown' };
  pbt: {
    p: boolean;
    vp: boolean;
    b: boolean;
    vb: boolean;
    t: boolean;
    verdict: string;
  };
}

export interface TPNode {
  id: string;
  smiles: string;
  parent_id: string | null;
  rule: string;
  source?: string;
  probability: number;
  fate: EnvironmentalFateResult;
  tox: {
    predictions: Array<{
      organism: string;
      organism_latin: string;
      level: 'Low' | 'Med' | 'High';
      risk_score: number;
      detail: string;
      threshold: string;
    }>;
    overall_level: 'Low' | 'Med' | 'High';
    applicability_domain: {
      status: string;
      confidence: number;
      warnings: string[];
    };
  };
  risk_flag: boolean;
  liability_flag?: boolean;
}

export interface TPEdge {
  source: string;
  target: string;
  rule: string;
  probability: number;
}

export interface TPGraph {
  nodes: TPNode[];
  edges: TPEdge[];
}

export interface MicrospeciesInfo {
  smiles: string;
  charge: number;
  fraction_at_target: number;
  dominant: boolean;
}

export interface SpeciationResult {
  ok: boolean;
  input_inchikey: string;
  microspecies: MicrospeciesInfo[];
  pka_values: number[] | null;
  method: string;
}

export interface SpeciationCurve {
  ok: boolean;
  series: Array<{
    ph: number;
    species: Array<{ smiles: string; fraction: number }>;
  }>;
}

export interface MobilityResult {
  ok: boolean;
  class: 'phloem' | 'xylem' | 'ambimobile' | 'immobile';
  phloem_concentration_factor: number;
  xylem_index: number;
  phloem_index: number;
  log_pm: number;
  drivers: {
    logkow: number;
    mw: number;
    pka: number[] | null;
    dominant_charge_apoplast: number;
  };
  confidence: 'in_domain' | 'edge' | 'out_of_domain';
}

interface FateState {
  predictions: Record<string, EnvironmentalFateResult>;
  loading: boolean;
  error: string | null;

  // Transformation Products
  tpGraphs: Record<string, TPGraph>;
  loadingTP: boolean;
  errorTP: string | null;

  // Speciation State
  phTarget: number;
  speciation: Record<string, SpeciationResult>;
  speciationCurves: Record<string, SpeciationCurve>;

  // Mobility State
  mobility: Record<string, MobilityResult>;

  // Actions
  computeEnvironmentalFate: (smiles: string[]) => Promise<EnvironmentalFateResult[]>;
  clearPredictions: () => void;
  predictTransformationProducts: (smiles: string, routes: string[], maxDepth: number, sources?: string[], ph?: number) => Promise<TPGraph>;

  // Speciation Actions
  setPhTarget: (ph: number) => void;
  loadSpeciation: (smiles: string) => Promise<SpeciationResult>;
  loadSpeciationCurve: (smiles: string) => Promise<SpeciationCurve>;

  // Mobility Action
  predictMobility: (smiles: string) => Promise<MobilityResult>;
}

export const useFateStore = create<FateState>((set, get) => ({
  predictions: {},
  loading: false,
  error: null,

  tpGraphs: {},
  loadingTP: false,
  errorTP: null,

  phTarget: 6.5,
  speciation: {},
  speciationCurves: {},

  mobility: {},

  setPhTarget: (ph: number) => set({ phTarget: ph }),

  predictMobility: async (smiles: string) => {
    const existing = get().mobility[smiles];
    if (existing) return existing;

    try {
      const res = await invoke<MobilityResult>('mobility_predict', {
        smiles,
        phApoplast: 5.5,
        phPhloem: 8.0,
      });
      set(state => ({
        mobility: {
          ...state.mobility,
          [smiles]: res,
        }
      }));
      return res;
    } catch (e) {
      console.error('Mobility prediction failed:', e);
      throw e;
    }
  },

  loadSpeciation: async (smiles: string) => {
    const phTarget = get().phTarget;
    const key = `${smiles}_${phTarget}`;
    const existing = get().speciation[key];
    if (existing) return existing;

    try {
      const res = await invoke<SpeciationResult>('speciation_enumerate', {
        smiles,
        phTarget,
      });
      set(state => ({
        speciation: {
          ...state.speciation,
          [key]: res,
        }
      }));
      return res;
    } catch (e) {
      console.error('Speciation enumeration failed:', e);
      throw e;
    }
  },

  loadSpeciationCurve: async (smiles: string) => {
    const existing = get().speciationCurves[smiles];
    if (existing) return existing;

    try {
      const curve = await invoke<SpeciationCurve>('speciation_profile_curve', {
        smiles,
        phMin: 4.0,
        phMax: 9.0,
        steps: 26,
      });
      set(state => ({
        speciationCurves: {
          ...state.speciationCurves,
          [smiles]: curve,
        }
      }));
      return curve;
    } catch (e) {
      console.error('Speciation curve generation failed:', e);
      throw e;
    }
  },

  computeEnvironmentalFate: async (smiles: string[]) => {
    if (smiles.length === 0) return [];
    
    const existing = get().predictions;
    const missingSmiles = smiles.filter(s => !existing[s]);

    if (missingSmiles.length === 0) {
      return smiles.map(s => existing[s]);
    }

    set({ loading: true, error: null });

    try {
      const results = await invoke<EnvironmentalFateResult[]>('compute_environmental_fate', {
        smiles: missingSmiles,
      });

      const newPredictions = { ...existing };
      results.forEach(r => {
        newPredictions[r.smiles] = r;
      });

      set({
        predictions: newPredictions,
        loading: false,
      });

      return smiles.map(s => newPredictions[s]);
    } catch (e) {
      set({ error: String(e), loading: false });
      throw e;
    }
  },

  predictTransformationProducts: async (smiles: string, routes: string[], maxDepth: number, sources?: string[], ph?: number) => {
    const srcKey = sources ? sources.join(',') : 'all';
    const phVal = ph || get().phTarget;
    const key = `${smiles}_${routes.join(',')}_${maxDepth}_${srcKey}_${phVal}`;
    const existing = get().tpGraphs[key];
    if (existing) return existing;

    set({ loadingTP: true, errorTP: null });

    try {
      const graph = await invoke<TPGraph>('predict_transformation_products', {
        smiles,
        routes,
        maxDepth,
        sources,
        ph: phVal,
      });

      set(state => ({
        tpGraphs: {
          ...state.tpGraphs,
          [key]: graph
        },
        loadingTP: false
      }));

      return graph;
    } catch (e) {
      set({ errorTP: String(e), loadingTP: false });
      throw e;
    }
  },

  clearPredictions: () => {
    set({ predictions: {}, tpGraphs: {}, speciation: {}, speciationCurves: {}, loading: false, error: null, loadingTP: false, errorTP: null });
  },
}));
