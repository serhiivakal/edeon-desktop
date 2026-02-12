import { create } from 'zustand';
import type { ViewId } from '../types';

interface UIState {
  activeView: ViewId;
  selectedCompoundId: string | null;
  setActiveView: (view: ViewId) => void;
  setSelectedCompound: (id: string | null) => void;
}

export const useUIStore = create<UIState>((set) => ({
  activeView: 'workflows',
  selectedCompoundId: 'c1',     // GLY-247 selected by default (matches SVG)
  setActiveView: (view) => set({ activeView: view }),
  setSelectedCompound: (id) => set({ selectedCompoundId: id }),
}));
