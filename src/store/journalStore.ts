import { create } from 'zustand';
import { invoke } from '@tauri-apps/api/core';

export interface JournalEntry {
  entry_id: string;
  project_id: string;
  created_at: string;
  actor: 'system' | 'user';
  decision_kind: string;
  subject_type: string;
  subject_id: string;
  summary: string;
  rationale_json: string | null;
  alternatives_json: string | null;
  confidence_json: string | null;
  provenance_json: string | null;
  override_of: string | null;
  supersedes_id: string | null;
  user_note: string | null;
}

export interface JournalListResponse {
  entries: JournalEntry[];
  total: number;
  limit: number;
  offset: number;
}

export interface LineageResponse {
  compound_id: string;
  project_id: string;
  entries: JournalEntry[];
  n_entries: number;
}

export interface OverrideAnalyticsResponse {
  by_kind: Record<string, { total: number; overridden: number; rate: number }>;
  total_decisions: number;
  total_overrides: number;
  overall_override_rate: number;
}

interface JournalState {
  entries: JournalEntry[];
  total: number;
  limit: number;
  offset: number;
  activeEntry: JournalEntry | null;
  lineage: LineageResponse | null;
  overrideAnalytics: OverrideAnalyticsResponse | null;

  filterKind: string | null;
  filterSubjectType: string | null;
  filterSubjectId: string | null;

  isLoading: boolean;
  error: string | null;

  fetchList: (
    projectId: string,
    filters?: { decisionKind?: string; subjectType?: string; subjectId?: string; limit?: number; offset?: number }
  ) => Promise<JournalListResponse>;
  fetchEntry: (entryId: string) => Promise<JournalEntry>;
  fetchLineage: (projectId: string, compoundId: string) => Promise<LineageResponse>;
  fetchOverrideAnalytics: (projectId: string) => Promise<OverrideAnalyticsResponse>;
  addNote: (entryId: string, note: string) => Promise<void>;
  recordOverride: (params: {
    projectId: string;
    overrideOf: string;
    subjectType: string;
    subjectId: string;
    actionTaken: string;
    systemRecommendation: string;
    userNote?: string;
  }) => Promise<string>;
  exportJournal: (projectId: string, format?: string) => Promise<any>;
  setFilters: (filters: { decisionKind?: string | null; subjectType?: string | null; subjectId?: string | null }) => void;
  setPage: (page: number) => void;
}

export const useJournalStore = create<JournalState>((set, get) => ({
  entries: [],
  total: 0,
  limit: 50,
  offset: 0,
  activeEntry: null,
  lineage: null,
  overrideAnalytics: null,

  filterKind: null,
  filterSubjectType: null,
  filterSubjectId: null,

  isLoading: false,
  error: null,

  fetchList: async (projectId, filters) => {
    set({ isLoading: true, error: null });
    const limit = filters?.limit ?? get().limit;
    const offset = filters?.offset ?? get().offset;
    const decisionKind = filters?.decisionKind ?? get().filterKind ?? undefined;
    const subjectType = filters?.subjectType ?? get().filterSubjectType ?? undefined;
    const subjectId = filters?.subjectId ?? get().filterSubjectId ?? undefined;

    try {
      const res = await invoke<JournalListResponse>('journal_list', {
        projectId,
        decisionKind,
        subjectType,
        subjectId,
        limit,
        offset,
      });

      set({
        entries: res.entries,
        total: res.total,
        limit: res.limit,
        offset: res.offset,
        isLoading: false,
      });

      return res;
    } catch (e) {
      const errorMsg = String(e);
      set({ error: errorMsg, isLoading: false });
      throw e;
    }
  },

  fetchEntry: async (entryId) => {
    try {
      const entry = await invoke<JournalEntry>('journal_get', { entryId });
      set({ activeEntry: entry });
      return entry;
    } catch (e) {
      set({ error: String(e) });
      throw e;
    }
  },

  fetchLineage: async (projectId, compoundId) => {
    set({ isLoading: true });
    try {
      const lin = await invoke<LineageResponse>('journal_lineage', {
        projectId,
        compoundId,
      });
      set({ lineage: lin, isLoading: false });
      return lin;
    } catch (e) {
      set({ error: String(e), isLoading: false });
      throw e;
    }
  },

  fetchOverrideAnalytics: async (projectId) => {
    try {
      const analytics = await invoke<OverrideAnalyticsResponse>('journal_override_analytics', {
        projectId,
      });
      set({ overrideAnalytics: analytics });
      return analytics;
    } catch (e) {
      set({ error: String(e) });
      throw e;
    }
  },

  addNote: async (entryId, note) => {
    try {
      await invoke('journal_add_note', { entryId, note });
      // Refresh list
      set((state) => ({
        entries: state.entries.map((e) =>
          e.entry_id === entryId ? { ...e, user_note: note } : e
        ),
      }));
    } catch (e) {
      set({ error: String(e) });
      throw e;
    }
  },

  recordOverride: async ({
    projectId,
    overrideOf,
    subjectType,
    subjectId,
    actionTaken,
    systemRecommendation,
    userNote,
  }) => {
    try {
      const res = await invoke<{ entry_id: string }>('journal_record_override', {
        projectId,
        overrideOf,
        subjectType,
        subjectId,
        actionTaken,
        systemRecommendation,
        userNote,
      });

      // Re-fetch list
      get().fetchList(projectId);
      return res.entry_id;
    } catch (e) {
      set({ error: String(e) });
      throw e;
    }
  },

  exportJournal: async (projectId, format) => {
    try {
      return await invoke('journal_export', { projectId, format });
    } catch (e) {
      set({ error: String(e) });
      throw e;
    }
  },

  setFilters: (filters) => {
    set({
      filterKind: filters.decisionKind !== undefined ? filters.decisionKind : get().filterKind,
      filterSubjectType: filters.subjectType !== undefined ? filters.subjectType : get().filterSubjectType,
      filterSubjectId: filters.subjectId !== undefined ? filters.subjectId : get().filterSubjectId,
      offset: 0,
    });
  },

  setPage: (page) => {
    const limit = get().limit;
    set({ offset: page * limit });
  },
}));
