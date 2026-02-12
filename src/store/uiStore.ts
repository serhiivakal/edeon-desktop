import { create } from 'zustand';
import { invoke } from '@tauri-apps/api/core';
import { useSettingsStore } from './settingsStore';
import type { ViewId } from '../types';

interface McsResult {
  mcs_smarts: string | null;
  num_atoms: number;
  num_bonds: number;
  num_molecules: number;
  canceled: boolean;
}

interface UIState {
  activeView: ViewId;
  selectedCompoundId: string | null;
  theme: 'light' | 'dark';

  // MCS state
  mcsActive: boolean;
  mcsSmarts: string | null;
  mcsResult: McsResult | null;
  mcsLoading: boolean;

  setActiveView: (view: ViewId) => void;
  setSelectedCompound: (id: string | null) => void;
  toggleTheme: () => void;

  isResultsTableMaximized: boolean;
  resultsTableHeight: number;
  toggleResultsTableMaximized: () => void;
  setResultsTableHeight: (height: number) => void;

  // Detail & Compare & About & Tasks modals/panels
  showDetailModal: boolean;
  showCompareModal: boolean;
  showAboutModal: boolean;
  showTasksPanel: boolean;
  compareCompoundIds: string[];
  selectedVerificationEndpoint: string | null;
  setShowDetailModal: (show: boolean) => void;
  setShowCompareModal: (show: boolean) => void;
  setShowAboutModal: (show: boolean) => void;
  setShowTasksPanel: (show: boolean) => void;
  setCompareCompoundIds: (ids: string[]) => void;
  setSelectedVerificationEndpoint: (endpoint: string | null) => void;
  // Export to De Novo state
  exportedSmiles: string | null;
  exportToDeNovo: (smiles: string, compoundId?: string) => void;

  // MCS actions
  computeMcs: (smilesList: string[]) => Promise<void>;
  clearMcs: () => void;
}

export const useUIStore = create<UIState>((set) => ({
  activeView: 'viewer3d',
  selectedCompoundId: 'c1',
  theme: 'light',
  mcsActive: false,
  mcsSmarts: null,
  mcsResult: null,
  mcsLoading: false,
  isResultsTableMaximized: false,
  resultsTableHeight: 320,
  showDetailModal: false,
  showCompareModal: false,
  showAboutModal: false,
  showTasksPanel: false,
  compareCompoundIds: [],
  selectedVerificationEndpoint: null,
  showShortcutsHelp: false,
  exportedSmiles: null,

  setActiveView: (view) => set({ activeView: view }),
  setSelectedCompound: (id) => set({ selectedCompoundId: id }),
  exportToDeNovo: (smiles, compoundId) => {
    set({
      activeView: 'generation',
      exportedSmiles: smiles,
      ...(compoundId ? { selectedCompoundId: compoundId } : {}),
    });
  },
  toggleTheme: () => {
    const next = useUIStore.getState().theme === 'light' ? 'dark' : 'light';
    useSettingsStore.getState().setTheme(next);
    set({ theme: next });
  },
  toggleResultsTableMaximized: () => set((s) => ({ isResultsTableMaximized: !s.isResultsTableMaximized })),
  setResultsTableHeight: (height) => set({ resultsTableHeight: height }),
  setShowDetailModal: (show) => set({ showDetailModal: show }),
  setShowCompareModal: (show) => set({ showCompareModal: show }),
  setShowAboutModal: (show) => set({ showAboutModal: show }),
  setShowTasksPanel: (show) => set({ showTasksPanel: show }),

  setCompareCompoundIds: (ids) => set({ compareCompoundIds: ids }),
  setSelectedVerificationEndpoint: (endpoint) => set({ selectedVerificationEndpoint: endpoint }),
  setShowShortcutsHelp: (show) => set({ showShortcutsHelp: show }),

  computeMcs: async (smilesList: string[]) => {
    set({ mcsLoading: true, mcsActive: false, mcsSmarts: null, mcsResult: null });
    try {
      const result = await invoke<McsResult>('compute_mcs', { smiles: smilesList });
      set({
        mcsActive: !!result.mcs_smarts,
        mcsSmarts: result.mcs_smarts,
        mcsResult: result,
        mcsLoading: false,
      });
    } catch (e) {
      console.error('MCS computation failed:', e);
      set({ mcsLoading: false });
    }
  },

  clearMcs: () => set({ mcsActive: false, mcsSmarts: null, mcsResult: null }),
}));
