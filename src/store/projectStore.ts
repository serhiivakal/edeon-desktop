/* ==========================================================
   Edeon Desktop — Project Store
   Zustand store synced with Tauri backend for project CRUD.
   ========================================================== */

import { create } from 'zustand';
import { invoke } from '@tauri-apps/api/core';
import type { ProjectRecord } from '../types';

interface ProjectState {
  projects: ProjectRecord[];
  activeProjectId: string | null;
  loading: boolean;
  error: string | null;

  // Actions
  fetchProjects: () => Promise<void>;
  createProject: (name: string) => Promise<ProjectRecord>;
  renameProject: (id: string, newName: string) => Promise<void>;
  deleteProject: (id: string) => Promise<void>;
  setActiveProject: (id: string) => Promise<void>;
  loadActiveProjectId: () => Promise<void>;
}

export const useProjectStore = create<ProjectState>((set, get) => ({
  projects: [],
  activeProjectId: null,
  loading: false,
  error: null,

  fetchProjects: async () => {
    set({ loading: true, error: null });
    try {
      const projects = await invoke<ProjectRecord[]>('list_projects');
      set({ projects, loading: false });
    } catch (e) {
      set({ error: String(e), loading: false });
    }
  },

  createProject: async (name: string) => {
    const project = await invoke<ProjectRecord>('create_project', { name });
    set((s) => ({ projects: [project, ...s.projects] }));
    // Auto-activate the new project
    await get().setActiveProject(project.id);
    return project;
  },

  renameProject: async (id: string, newName: string) => {
    const updated = await invoke<ProjectRecord>('rename_project', { id, newName });
    set((s) => ({
      projects: s.projects.map((p) => (p.id === id ? updated : p)),
    }));
  },

  deleteProject: async (id: string) => {
    await invoke('delete_project', { id });
    const state = get();
    const remaining = state.projects.filter((p) => p.id !== id);
    const newActive =
      state.activeProjectId === id
        ? remaining.length > 0
          ? remaining[0].id
          : null
        : state.activeProjectId;

    set({ projects: remaining, activeProjectId: newActive });
    if (newActive && state.activeProjectId === id) {
      await invoke('set_active_project', { id: newActive });
    }
  },

  setActiveProject: async (id: string) => {
    await invoke('set_active_project', { id });
    set({ activeProjectId: id });
  },

  loadActiveProjectId: async () => {
    try {
      const id = await invoke<string | null>('get_active_project_id');
      if (id) {
        set({ activeProjectId: id });
      }
    } catch {
      // No active project set yet — that's fine
    }
  },
}));
