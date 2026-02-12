/* ==========================================================
   Edeon Desktop — Prescriptive Design Store
   Zustand store for managing analog suggestions via MMP/bioisostere
   transforms and full-stack re-prediction.
   ========================================================== */

import { create } from 'zustand';
import { invoke } from '@tauri-apps/api/core';
import type { Prediction } from '../types';

export interface AnalogSuggestion {
  smiles: string;
  transform: string;
  deltas: Record<string, number>; // endpoint -> delta (improvement direction)
  envelopes: Record<string, Prediction>; // endpoint -> full envelope
  ad_status: 'in_domain' | 'borderline' | 'out_of_domain';
  composite_score: number;
}

export interface SuggestAnalogsResult {
  parent: {
    smiles: string;
    envelopes: Record<string, Prediction>;
  };
  suggestions: AnalogSuggestion[];
}

export interface ReactionTemplate {
  id: string;
  name: string;
  smarts: string;
  description: string;
  n_reagent_slots: number;
}

export interface EnumeratedProduct {
  smiles: string;
  passed_filters: boolean;
  sa_score?: number;
  feasibility_score?: number;
  tier: 'green' | 'amber' | 'red';
  solved: boolean;
}

export interface ReactionEnumerateResult {
  ok: boolean;
  template_id: string;
  products: EnumeratedProduct[];
  n_generated: number;
  n_passed: number;
}

interface DesignState {
  suggestions: Record<string, SuggestAnalogsResult>; // keyed by parent SMILES
  reactionTemplates: ReactionTemplate[];
  reactionResults: Record<string, ReactionEnumerateResult>;
  workbenchMode: 'crem' | 'reaction';
  loading: boolean;
  error: string | null;

  // Actions
  setWorkbenchMode: (mode: 'crem' | 'reaction') => void;
  suggestAnalogs: (
    smiles: string,
    improve: string,
    preserve?: string[],
    n?: number
  ) => Promise<SuggestAnalogsResult>;
  clearSuggestions: (smiles?: string) => void;

  listReactionTemplates: () => Promise<ReactionTemplate[]>;
  enumerateReaction: (
    templateId: string,
    coreSmiles?: string,
    reagents?: string[],
    maxProducts?: number
  ) => Promise<ReactionEnumerateResult>;
}

export const useDesignStore = create<DesignState>((set, get) => ({
  suggestions: {},
  reactionTemplates: [],
  reactionResults: {},
  workbenchMode: 'crem',
  loading: false,
  error: null,

  setWorkbenchMode: (mode: 'crem' | 'reaction') => set({ workbenchMode: mode }),

  listReactionTemplates: async () => {
    const existing = get().reactionTemplates;
    if (existing.length > 0) return existing;

    try {
      const res = await invoke<{ ok: boolean; templates: ReactionTemplate[] }>('gen_reaction_list_templates');
      set({ reactionTemplates: res.templates });
      return res.templates;
    } catch (e) {
      console.error('Failed to list reaction templates:', e);
      return [];
    }
  },

  enumerateReaction: async (templateId: string, coreSmiles?: string, reagents?: string[], maxProducts: number = 200) => {
    set({ loading: true, error: null });
    try {
      const res = await invoke<ReactionEnumerateResult>('gen_reaction_enumerate', {
        templateId,
        coreSmiles,
        reagentCatalogs: reagents,
        maxProducts,
      });
      set(state => ({
        reactionResults: {
          ...state.reactionResults,
          [`${templateId}_${coreSmiles || 'default'}`]: res,
        },
        loading: false,
      }));
      return res;
    } catch (e) {
      set({ error: String(e), loading: false });
      throw e;
    }
  },

  suggestAnalogs: async (
    smiles: string,
    improve: string,
    preserve: string[] = [],
    n: number = 20
  ) => {
    set({ loading: true, error: null });

    try {
      const result = await invoke<SuggestAnalogsResult>('suggest_analogs', {
        smiles,
        improve,
        preserve,
        n,
      });

      set((state) => ({
        suggestions: {
          ...state.suggestions,
          [smiles]: result,
        },
        loading: false,
      }));

      return result;
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      set({ error: errorMsg, loading: false });
      throw err;
    }
  },

  clearSuggestions: (smiles?: string) => {
    if (smiles) {
      set((state) => {
        const { [smiles]: _, ...rest } = state.suggestions;
        return { suggestions: rest };
      });
    } else {
      set({ suggestions: {} });
    }
  },
}));
