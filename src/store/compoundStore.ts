/* ==========================================================
   Edeon Desktop — Compound Store
   Zustand store synced with Tauri backend for compound management.
   ========================================================== */

import { create } from 'zustand';
import { invoke } from '@tauri-apps/api/core';
import type { CompoundRecord, CompoundPage, PropertyFilters } from '../types';

interface CompoundState {
  compounds: CompoundRecord[];
  total: number;
  page: number;
  pageSize: number;
  sortBy: string;
  sortDir: 'asc' | 'desc';
  searchQuery: string;
  filters: PropertyFilters;
  loading: boolean;
  error: string | null;

  // Actions
  fetchCompounds: (projectId: string) => Promise<void>;
  setPage: (page: number, projectId: string) => Promise<void>;
  setSort: (column: string, projectId: string) => Promise<void>;
  setSearch: (query: string, projectId: string) => Promise<void>;
  setFilters: (filters: PropertyFilters, projectId: string) => Promise<void>;
  importCSV: (projectId: string, filePath: string) => Promise<number>;
  importSDF: (projectId: string, filePath: string) => Promise<number>;
  addCompound: (projectId: string, name: string, smiles: string) => Promise<void>;
  deleteCompounds: (projectId: string, ids: string[]) => Promise<void>;
  reset: () => void;
}

export const useCompoundStore = create<CompoundState>((set, get) => ({
  compounds: [],
  total: 0,
  page: 1,
  pageSize: 25,
  sortBy: 'name',
  sortDir: 'asc',
  searchQuery: '',
  filters: {},
  loading: false,
  error: null,

  fetchCompounds: async (projectId: string) => {
    const { page, pageSize, sortBy, sortDir, searchQuery, filters } = get();
    set({ loading: true, error: null });
    try {
      const result = await invoke<CompoundPage>('list_compounds', {
        projectId,
        page,
        pageSize,
        sortBy,
        sortDir,
        search: searchQuery || null,
        filters: Object.keys(filters).length > 0 ? filters : null,
      });
      set({
        compounds: result.compounds,
        total: result.total,
        page: result.page,
        loading: false,
      });
    } catch (e) {
      set({ error: String(e), loading: false });
    }
  },

  setPage: async (page: number, projectId: string) => {
    set({ page });
    await get().fetchCompounds(projectId);
  },

  setSort: async (column: string, projectId: string) => {
    const { sortBy, sortDir } = get();
    const newDir = sortBy === column && sortDir === 'asc' ? 'desc' : 'asc';
    set({ sortBy: column, sortDir: newDir, page: 1 });
    await get().fetchCompounds(projectId);
  },

  setSearch: async (query: string, projectId: string) => {
    set({ searchQuery: query, page: 1 });
    await get().fetchCompounds(projectId);
  },

  setFilters: async (filters: PropertyFilters, projectId: string) => {
    set({ filters, page: 1 });
    await get().fetchCompounds(projectId);
  },

  importCSV: async (projectId: string, filePath: string) => {
    const imported = await invoke<number>('import_compounds_csv', {
      projectId,
      filePath,
    });
    // Refresh compound list after import
    set({ page: 1 });
    await get().fetchCompounds(projectId);
    return imported;
  },

  importSDF: async (projectId: string, filePath: string) => {
    const imported = await invoke<number>('import_compounds_sdf', {
      projectId,
      filePath,
    });
    // Refresh compound list after import
    set({ page: 1 });
    await get().fetchCompounds(projectId);
    return imported;
  },

  addCompound: async (projectId: string, name: string, smiles: string) => {
    await invoke('add_compound', { projectId, name, smiles });
    // Refresh to show the new compound
    await get().fetchCompounds(projectId);
  },

  deleteCompounds: async (projectId: string, ids: string[]) => {
    await invoke('delete_compounds', { projectId, compoundIds: ids });
    await get().fetchCompounds(projectId);
  },

  reset: () => {
    set({
      compounds: [],
      total: 0,
      page: 1,
      searchQuery: '',
      filters: {},
      loading: false,
      error: null,
    });
  },
}));
