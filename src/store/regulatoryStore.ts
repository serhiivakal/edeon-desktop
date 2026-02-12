import { create } from 'zustand';
import { invoke } from '@tauri-apps/api/core';

// ─── Types ───────────────────────────────────────────────────────────────────

export type RiskStatus = 'pass' | 'watch' | 'likely_showstopper';
export type OverallRisk = 'low' | 'medium' | 'high' | 'showstopper';

export interface CriterionResult {
  criterion: string;
  status: RiskStatus;
  evidence: string[];
  confidence: number;
  source_ref: string;
  verdict?: string;
}

export interface RegistrationRiskResult {
  smiles: string;
  criteria: CriterionResult[];
  overall: {
    risk: OverallRisk;
    pass_count: number;
    watch_count: number;
    showstopper_count: number;
  };
  disclaimer: string;
}

// ─── Store Interface ─────────────────────────────────────────────────────────

interface RegulatoryState {
  cache: Record<string, RegistrationRiskResult>;
  activeSmiles: string | null;
  activeScorecard: RegistrationRiskResult | null;
  isLoading: boolean;
  error: string | null;

  assessRisk: (smiles: string) => Promise<RegistrationRiskResult>;
  assessRiskBatch: (smilesList: string[]) => Promise<RegistrationRiskResult[]>;
  clearCache: () => void;
}

// ─── Store Implementation ────────────────────────────────────────────────────

export const useRegulatoryStore = create<RegulatoryState>((set, get) => ({
  cache: {},
  activeSmiles: null,
  activeScorecard: null,
  isLoading: false,
  error: null,

  assessRisk: async (smiles: string) => {
    const cached = get().cache[smiles];
    if (cached) {
      set({ activeSmiles: smiles, activeScorecard: cached, error: null });
      return cached;
    }

    set({ isLoading: true, error: null, activeSmiles: smiles });

    try {
      const result = await invoke<RegistrationRiskResult>('assess_registration_risk', {
        smiles,
      });

      set((state) => ({
        cache: { ...state.cache, [smiles]: result },
        activeScorecard: result,
        isLoading: false,
      }));

      return result;
    } catch (e) {
      const errorMsg = String(e);
      set({ error: errorMsg, isLoading: false, activeScorecard: null });
      throw e;
    }
  },

  assessRiskBatch: async (smilesList: string[]) => {
    const existing = get().cache;
    const missing = smilesList.filter((s) => !existing[s]);

    if (missing.length === 0) {
      return smilesList.map((s) => existing[s]);
    }

    set({ isLoading: true, error: null });

    try {
      const results = await invoke<RegistrationRiskResult[]>('assess_registration_risk_batch', {
        smilesList: missing,
      });

      const newCache = { ...existing };
      results.forEach((r) => {
        newCache[r.smiles] = r;
      });

      set({ cache: newCache, isLoading: false });

      return smilesList.map((s) => newCache[s]);
    } catch (e) {
      set({ error: String(e), isLoading: false });
      throw e;
    }
  },

  clearCache: () => {
    set({
      cache: {},
      activeSmiles: null,
      activeScorecard: null,
      isLoading: false,
      error: null,
    });
  },
}));
