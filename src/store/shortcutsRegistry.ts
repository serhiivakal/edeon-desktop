import { create } from 'zustand';
import { useUIStore } from './uiStore';
import { useSettingsStore } from './settingsStore';
import { useTourStore } from './tourStore';

export interface CommandItem {
  id: string;
  label: string;
  hint?: string;
  keywords?: string[];
  category: 'navigation' | 'action' | 'workflow' | 'help' | 'settings';
  shortcut?: string;
  enabled?: () => boolean;
  execute: () => void | Promise<void>;
}

interface CommandRegistryState {
  commands: CommandItem[];
  recentIds: string[];
  registerCommand: (command: CommandItem) => void;
  unregisterCommand: (id: string) => void;
  trackExecution: (id: string) => void;
  getCommands: () => CommandItem[];
}

export const useCommandRegistryStore = create<CommandRegistryState>((set, get) => {
  // Built-in commands registered by default
  const defaultCommands: CommandItem[] = [
    // Navigation
    { id: 'nav.viewer3d', label: 'Open 3D Viewer / Docking Workbench', category: 'navigation', shortcut: 'Cmd+1', execute: () => useUIStore.getState().setActiveView('viewer3d') },
    { id: 'nav.library', label: 'Open Library', category: 'navigation', shortcut: 'Cmd+2', execute: () => useUIStore.getState().setActiveView('library') },
    { id: 'nav.workflows', label: 'Open Workflows Gallery', category: 'navigation', shortcut: 'Cmd+3', execute: () => useUIStore.getState().setActiveView('workflows') },
    { id: 'nav.generation', label: 'Open De Novo Design Workbench', category: 'navigation', shortcut: 'Cmd+4', execute: () => useUIStore.getState().setActiveView('generation') },
    { id: 'nav.fate', label: 'Open Environmental Fate', category: 'navigation', shortcut: 'Cmd+5', execute: () => useUIStore.getState().setActiveView('fate') },
    { id: 'nav.knowledge', label: 'Open Knowledge Hub', category: 'navigation', shortcut: 'Cmd+6', execute: () => useUIStore.getState().setActiveView('knowledge') },
    { id: 'nav.models', label: 'Open Model Cards', category: 'navigation', shortcut: 'Cmd+7', execute: () => useUIStore.getState().setActiveView('models') },
    { id: 'nav.reports', label: 'Open Reports Dossiers', category: 'navigation', shortcut: 'Cmd+8', execute: () => useUIStore.getState().setActiveView('reports') },
    { id: 'nav.settings', label: 'Open App Settings', category: 'navigation', shortcut: 'Cmd+,', execute: () => useUIStore.getState().setActiveView('settings') },

    // Actions
    {
      id: 'settings.theme.toggle',
      label: 'Toggle Dark Mode / Light Mode',
      category: 'settings',
      shortcut: 'Cmd+Shift+L',
      execute: () => {
        const theme = useSettingsStore.getState().theme;
        useSettingsStore.getState().setTheme(theme === 'dark' ? 'light' : 'dark');
      }
    },
    {
      id: 'settings.density.compact',
      label: 'Set UI Density to Compact',
      category: 'settings',
      execute: () => useSettingsStore.getState().setDensity('compact')
    },
    {
      id: 'settings.density.default',
      label: 'Set UI Density to Default',
      category: 'settings',
      execute: () => useSettingsStore.getState().setDensity('default')
    },
    {
      id: 'settings.density.comfortable',
      label: 'Set UI Density to Comfortable',
      category: 'settings',
      execute: () => useSettingsStore.getState().setDensity('comfortable')
    },

    // Help
    {
      id: 'help.tour',
      label: 'Restart Guided Onboarding Tour',
      category: 'help',
      execute: () => useTourStore.getState().startTour()
    },
    {
      id: 'help.about',
      label: 'About Edeon Desktop',
      category: 'help',
      execute: () => useUIStore.getState().setShowAboutModal(true)
    },
  ];


  return {
    commands: defaultCommands,
    recentIds: [],

    registerCommand: (cmd) => set((state) => {
      if (state.commands.some((c) => c.id === cmd.id)) return state;
      return { commands: [...state.commands, cmd] };
    }),

    unregisterCommand: (id) => set((state) => ({
      commands: state.commands.filter((c) => c.id !== id),
    })),

    trackExecution: (id) => set((state) => {
      const filtered = state.recentIds.filter((x) => x !== id);
      return { recentIds: [id, ...filtered].slice(0, 10) };
    }),

    getCommands: () => get().commands,
  };
});
