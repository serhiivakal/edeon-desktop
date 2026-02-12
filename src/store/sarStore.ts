import { create } from 'zustand';
import { invoke } from '@tauri-apps/api/core';

export interface MatchedPair {
  mol1: string;
  mol2: string;
  core: string;
  r1: string;
  r2: string;
  delta_potency: number;
  delta_off_target: number;
  delta_selectivity: number;
  transform: string;
}

export interface SelectivityTransform {
  transform: string;
  r1: string;
  r2: string;
  count: number;
  mean_delta_selectivity: number;
  mean_delta_potency: number;
  mean_delta_off_target: number;
  confidence: 'high' | 'medium' | 'low';
}

export interface SubstituentCoef {
  substituent: string;
  coefficient: number;
}

export interface FreeWilsonPrediction {
  smiles: string;
  observed: number;
  predicted: number;
  residual: number;
}

export interface FreeWilsonResult {
  ok: boolean;
  endpoint: string;
  dominant_core: string;
  intercept_mu: number;
  r2_score: number;
  substituent_coefficients: SubstituentCoef[];
  predictions: FreeWilsonPrediction[];
  n_samples: number;
  error?: string;
}

interface SarState {
  pairs: MatchedPair[];
  transforms: SelectivityTransform[];
  freeWilsonResult: FreeWilsonResult | null;
  loading: boolean;
  error: string | null;

  // Actions
  indexMatchedPairs: (compounds: Array<{ id: string; smiles: string; potency?: number; off_target?: number }>) => Promise<MatchedPair[]>;
  suggestSelectivityTransforms: (compounds: Array<{ id: string; smiles: string; potency?: number; off_target?: number }>) => Promise<SelectivityTransform[]>;
  fitFreeWilson: (compounds: Array<{ id: string; smiles: string; potency?: number }>, endpoint?: string) => Promise<FreeWilsonResult>;
}

export const useSarStore = create<SarState>((set) => ({
  pairs: [],
  transforms: [],
  freeWilsonResult: null,
  loading: false,
  error: null,

  indexMatchedPairs: async (compounds) => {
    set({ loading: true, error: null });
    try {
      const res = await invoke<{ ok: boolean; pairs: MatchedPair[] }>('sar_mmp_index', { compounds });
      set({ pairs: res.pairs, loading: false });
      return res.pairs;
    } catch (e) {
      set({ error: String(e), loading: false });
      throw e;
    }
  },

  suggestSelectivityTransforms: async (compounds) => {
    set({ loading: true, error: null });
    try {
      const res = await invoke<{ ok: boolean; transforms: SelectivityTransform[] }>('sar_mmp_suggest_transforms', { compounds, topK: 20 });
      set({ transforms: res.transforms, loading: false });
      return res.transforms;
    } catch (e) {
      set({ error: String(e), loading: false });
      throw e;
    }
  },

  fitFreeWilson: async (compounds, endpoint = 'potency') => {
    set({ loading: true, error: null });
    try {
      const res = await invoke<FreeWilsonResult>('sar_free_wilson_fit', { compounds, endpoint });
      set({ freeWilsonResult: res, loading: false });
      return res;
    } catch (e) {
      set({ error: String(e), loading: false });
      throw e;
    }
  },
}));
