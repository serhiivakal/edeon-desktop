import { create } from 'zustand';
import { invoke } from '@tauri-apps/api/core';

export interface ShapeResultItem {
  smiles: string;
  shape_score: number;
  esp_score: number;
  combo_score: number;
  metadata?: Record<string, any>;
}

export interface ShapeScreenResult {
  ok: boolean;
  reference_smiles: string;
  results: ShapeResultItem[];
  n_screened: number;
  n_returned: number;
}

interface ShapeState {
  referenceSmiles: string;
  screenResult: ShapeScreenResult | null;
  loading: boolean;
  error: string | null;

  // Actions
  setReferenceSmiles: (smiles: string) => void;
  screen3d: (referenceSmiles: string, candidates: Array<{ id: string; smiles: string; [key: string]: any }>, topK?: number) => Promise<ShapeScreenResult>;
}

export const useShapeStore = create<ShapeState>((set) => ({
  referenceSmiles: '',
  screenResult: null,
  loading: false,
  error: null,

  setReferenceSmiles: (smiles) => set({ referenceSmiles: smiles }),

  screen3d: async (referenceSmiles, candidates, topK = 50) => {
    set({ loading: true, error: null, referenceSmiles });
    try {
      const res = await invoke<ShapeScreenResult>('shape_screen_3d', {
        referenceSmiles,
        candidates,
        topK,
      });
      set({ screenResult: res, loading: false });
      return res;
    } catch (e) {
      set({ error: String(e), loading: false });
      throw e;
    }
  },
}));
