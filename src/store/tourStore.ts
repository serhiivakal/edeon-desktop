import { create } from 'zustand';
import { invoke } from '@tauri-apps/api/core';

interface TourState {
  isFirstLaunch: boolean;
  tourActive: boolean;
  loading: boolean;
  checkFirstLaunch: () => Promise<void>;
  startTour: () => void;
  endTour: () => Promise<void>;
}

export const useTourStore = create<TourState>((set) => ({
  isFirstLaunch: false,
  tourActive: false,
  loading: true,

  checkFirstLaunch: async () => {
    try {
      const state = await invoke<{ has_completed: boolean }>('app_meta_get_first_launch_state');
      set({
        isFirstLaunch: !state.has_completed,
        tourActive: !state.has_completed,
        loading: false,
      });
    } catch (e) {
      console.error('[ERROR] Failed to check first launch state:', e);
      set({ loading: false });
    }
  },

  startTour: () => {
    set({ tourActive: true });
  },

  endTour: async () => {
    set({ tourActive: false, isFirstLaunch: false });
    try {
      await invoke('app_meta_mark_first_launch_complete');
    } catch (e) {
      console.error('[ERROR] Failed to mark first launch complete:', e);
    }
  },
}));
