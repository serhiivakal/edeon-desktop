import { create } from 'zustand';
import { invoke } from '@tauri-apps/api/core';

export type BottleneckKind = 'chemical' | 'epistemic' | 'distractor';
export type RecommendedAction =
  | 'redesign_structure'
  | 'measure_endpoint'
  | 'improve_model'
  | 'deprioritize_weight'
  | 'no_action';

export type Reliability = 'ok' | 'low' | 'insufficient_data';

export interface EndpointResult {
  endpoint: string;
  display_name: string;
  leverage: number;
  leverage_ci: [number, number];
  headroom: number;
  mean_desirability: number;
  achievable_target: number;
  rank: number;
  rank_stability: number;
  kind: BottleneckKind;
  recommended_action: RecommendedAction;
  reason: string;
  reliability: Reliability;
  n_in_ad: number;
  weight: number;
}

export interface BottleneckAnalysis {
  analysis_id: string;
  project_id: string;
  profile: string;
  n_compounds: number;
  endpoints: EndpointResult[];
  top_endpoint: string | null;
  top_kind: BottleneckKind | null;
  bottleneck_ambiguous: boolean;
  tradeoff_matrix: {
    matrix: Record<string, Record<string, number>>;
    p_values: Record<string, Record<string, number>>;
    antagonistic_pairs: Array<[string, string, number, number]>;
    n: number;
  };
  overall_reliability: Reliability;
  params_hash: string;
}

export interface CompoundBottleneck {
  compound_id: string;
  weakest_endpoint: string;
  weakest_desirability: number;
  overall_desirability: number;
  kind: BottleneckKind;
  reason: string;
}

export interface GateAttrition {
  gate_name: string;
  n_input: number;
  n_passed: number;
  n_failed: number;
  attrition_rate: number;
  cumulative_survival: number;
}

export interface AttritionResult {
  gates: GateAttrition[];
  dominant_gate: string | null;
  dominant_attrition: number;
  total_input: number;
  total_output: number;
  overall_attrition: number;
}

export interface DesirabilityProfileInfo {
  id: string;
  name: string;
  n_endpoints: number;
}

interface BottleneckState {
  analysis: BottleneckAnalysis | null;
  compoundBottleneck: CompoundBottleneck | null;
  attrition: AttritionResult | null;
  suggestedWeights: Record<string, number> | null;
  profiles: DesirabilityProfileInfo[];
  isLoading: boolean;
  error: string | null;

  analyze: (
    projectId: string,
    compounds: any[],
    profile?: string,
    userWeights?: Record<string, number>
  ) => Promise<BottleneckAnalysis>;
  analyzeCompound: (compound: any, profile?: string) => Promise<CompoundBottleneck>;
  analyzeAttrition: (gateResults: any[]) => Promise<AttritionResult>;
  suggestWeights: (leverageResults: any[], nTop?: number) => Promise<Record<string, number>>;
  listProfiles: () => Promise<DesirabilityProfileInfo[]>;
  clear: () => void;
}

export const useBottleneckStore = create<BottleneckState>((set) => ({
  analysis: null,
  compoundBottleneck: null,
  attrition: null,
  suggestedWeights: null,
  profiles: [],
  isLoading: false,
  error: null,

  analyze: async (projectId, compounds, profile, userWeights) => {
    set({ isLoading: true, error: null });
    try {
      const result = await invoke<BottleneckAnalysis>('bottleneck_analyze', {
        projectId,
        compounds,
        profile,
        userWeights,
      });
      set({ analysis: result, isLoading: false });
      return result;
    } catch (e) {
      const errorMsg = String(e);
      set({ error: errorMsg, isLoading: false });
      throw e;
    }
  },

  analyzeCompound: async (compound, profile) => {
    try {
      const result = await invoke<CompoundBottleneck>('bottleneck_compound', {
        compound,
        profile,
      });
      set({ compoundBottleneck: result });
      return result;
    } catch (e) {
      set({ error: String(e) });
      throw e;
    }
  },

  analyzeAttrition: async (gateResults) => {
    try {
      const result = await invoke<AttritionResult>('bottleneck_attrition', {
        gateResults,
      });
      set({ attrition: result });
      return result;
    } catch (e) {
      set({ error: String(e) });
      throw e;
    }
  },

  suggestWeights: async (leverageResults, nTop) => {
    try {
      const res = await invoke<{ weights: Record<string, number> }>('bottleneck_suggest_weights', {
        leverageResults,
        nTop,
      });
      set({ suggestedWeights: res.weights });
      return res.weights;
    } catch (e) {
      set({ error: String(e) });
      throw e;
    }
  },

  listProfiles: async () => {
    try {
      const res = await invoke<DesirabilityProfileInfo[]>('bottleneck_list_profiles');
      set({ profiles: res });
      return res;
    } catch (e) {
      set({ error: String(e) });
      return [];
    }
  },

  clear: () => {
    set({
      analysis: null,
      compoundBottleneck: null,
      attrition: null,
      suggestedWeights: null,
      error: null,
      isLoading: false,
    });
  },
}));
