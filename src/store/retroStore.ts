import { create } from 'zustand';
import { invoke } from '@tauri-apps/api/core';

export interface RouteNode {
  smiles?: string;
  reaction_name?: string;
  type: 'mol' | 'rxn';
  in_stock?: boolean;
  children?: RouteNode[];
}

export interface RetroRouteResult {
  ok: boolean;
  smiles: string;
  sa_score: number;
  solved: boolean;
  feasibility_score: number;
  tier: 'green' | 'amber' | 'red';
  n_steps: number;
  route_depth: number;
  leaves_in_stock_frac: number;
  route_tree: RouteNode;
  building_blocks: Array<{ smiles: string; in_stock: boolean }>;
  engine_used: string;
}

export interface RetroGateResult {
  smiles: string;
  sa_score: number;
  feasibility_score: number;
  tier: 'green' | 'amber' | 'red';
  solved: boolean;
}

interface RetroState {
  saScores: Record<string, number>;
  routes: Record<string, RetroRouteResult>;
  gating: Record<string, RetroGateResult>;
  activeStockId: string;
  synthesizableOnly: boolean;
  loading: boolean;

  setSynthesizableOnly: (enabled: boolean) => void;
  getSaScore: (smiles: string) => Promise<number>;
  getRouteSearch: (smiles: string) => Promise<RetroRouteResult>;
  gateBatch: (smiles: string[]) => Promise<RetroGateResult[]>;
}

export const useRetroStore = create<RetroState>((set, get) => ({
  saScores: {},
  routes: {},
  gating: {},
  activeStockId: 'agrochem_default',
  synthesizableOnly: false,
  loading: false,

  setSynthesizableOnly: (enabled: boolean) => set({ synthesizableOnly: enabled }),

  getSaScore: async (smiles: string) => {
    const existing = get().saScores[smiles];
    if (existing !== undefined) return existing;

    try {
      const res = await invoke<{ ok: boolean; scores: Array<{ smiles: string; sa_score: number }> }>('retro_sascore', {
        smiles: [smiles],
      });
      const score = res.scores[0]?.sa_score ?? 0.5;
      set(state => ({
        saScores: { ...state.saScores, [smiles]: score }
      }));
      return score;
    } catch (e) {
      console.error('Failed to compute SA score:', e);
      return 0.5;
    }
  },

  getRouteSearch: async (smiles: string) => {
    const existing = get().routes[smiles];
    if (existing) return existing;

    set({ loading: true });
    try {
      const res = await invoke<RetroRouteResult>('retro_route_search', {
        smiles,
        stockId: get().activeStockId,
      });
      set(state => ({
        routes: { ...state.routes, [smiles]: res },
        saScores: { ...state.saScores, [smiles]: res.sa_score },
        loading: false,
      }));
      return res;
    } catch (e) {
      set({ loading: false });
      console.error('Route search failed:', e);
      throw e;
    }
  },

  gateBatch: async (smiles: string[]) => {
    if (smiles.length === 0) return [];

    try {
      const res = await invoke<{ ok: boolean; results: RetroGateResult[] }>('retro_gate_batch', {
        smiles,
        stockId: get().activeStockId,
      });

      const newGating = { ...get().gating };
      const newSaScores = { ...get().saScores };

      res.results.forEach(item => {
        newGating[item.smiles] = item;
        newSaScores[item.smiles] = item.sa_score;
      });

      set({ gating: newGating, saScores: newSaScores });
      return res.results;
    } catch (e) {
      console.error('Gate batch failed:', e);
      return [];
    }
  },
}));
