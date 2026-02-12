import { create } from 'zustand';
import { invoke } from '@tauri-apps/api/core';

export interface AlSuggestedCandidate {
  rank: number;
  smiles: string;
  predicted_mean: number;
  predicted_std: number;
  acquisition_score: number;
  metadata?: Record<string, any>;
}

export interface AlBatchResult {
  ok: boolean;
  acquisition_method: string;
  suggested_batch: AlSuggestedCandidate[];
  model_metrics: {
    r2_score: number;
    f_best: number;
    n_train: number;
    n_candidates: number;
  };
  error?: string;
}

interface ActiveLearningState {
  acquisition: 'ei' | 'ucb' | 'ts';
  batchSize: number;
  endpoint: string;
  batchResult: AlBatchResult | null;
  loading: boolean;
  error: string | null;

  // Actions
  setAcquisition: (acq: 'ei' | 'ucb' | 'ts') => void;
  setBatchSize: (size: number) => void;
  setEndpoint: (endpoint: string) => void;
  suggestNextBatch: (
    labeledPool: Array<{ id: string; smiles: string; [key: string]: any }>,
    candidatePool: Array<{ id: string; smiles: string; [key: string]: any }>
  ) => Promise<AlBatchResult>;
}

export const useActiveLearningStore = create<ActiveLearningState>((set, get) => ({
  acquisition: 'ei',
  batchSize: 10,
  endpoint: 'potency',
  batchResult: null,
  loading: false,
  error: null,

  setAcquisition: (acq) => set({ acquisition: acq }),
  setBatchSize: (size) => set({ batchSize: size }),
  setEndpoint: (endpoint) => set({ endpoint }),

  suggestNextBatch: async (labeledPool, candidatePool) => {
    set({ loading: true, error: null });
    try {
      const { acquisition, batchSize, endpoint } = get();
      const res = await invoke<AlBatchResult>('al_suggest_next_batch', {
        labeledPool,
        candidatePool,
        acquisition,
        batchSize,
        endpoint,
      });
      set({ batchResult: res, loading: false });
      return res;
    } catch (e) {
      set({ error: String(e), loading: false });
      throw e;
    }
  },
}));
