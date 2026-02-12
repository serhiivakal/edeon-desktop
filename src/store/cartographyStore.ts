import { create } from 'zustand';
import { invoke } from '@tauri-apps/api/core';

export interface TmapNode {
  idx: number;
  smiles: string;
  x: number;
  y: number;
  metadata?: Record<string, any>;
}

export interface TmapEdge {
  source: number;
  target: number;
}

export interface TmapLayoutResult {
  ok: boolean;
  method: string;
  nodes: TmapNode[];
  edges: TmapEdge[];
  n_compounds: number;
  error?: string;
}

interface CartographyState {
  currentLayout: TmapLayoutResult | null;
  selectedNodeIdx: number | null;
  hoveredNodeIdx: number | null;
  activePropertyOverlay: string;
  loading: boolean;
  error: string | null;

  // Actions
  setSelectedNodeIdx: (idx: number | null) => void;
  setHoveredNodeIdx: (idx: number | null) => void;
  setActivePropertyOverlay: (prop: string) => void;
  computeTmapLayout: (compounds: Array<{ id: string; smiles: string; [key: string]: any }>) => Promise<TmapLayoutResult>;
}

export const useCartographyStore = create<CartographyState>((set) => ({
  currentLayout: null,
  selectedNodeIdx: null,
  hoveredNodeIdx: null,
  activePropertyOverlay: 'none',
  loading: false,
  error: null,

  setSelectedNodeIdx: (idx) => set({ selectedNodeIdx: idx }),
  setHoveredNodeIdx: (idx) => set({ hoveredNodeIdx: idx }),
  setActivePropertyOverlay: (prop) => set({ activePropertyOverlay: prop }),

  computeTmapLayout: async (compounds) => {
    set({ loading: true, error: null });
    try {
      const res = await invoke<TmapLayoutResult>('cartography_compute_tmap', { compounds });
      set({ currentLayout: res, loading: false });
      return res;
    } catch (e) {
      set({ error: String(e), loading: false });
      throw e;
    }
  },
}));
