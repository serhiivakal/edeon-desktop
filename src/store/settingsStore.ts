/* ==========================================================
   Edeon Desktop — Settings & Preferences Store
   Zustand store for settings persistence and sidecar status.
   ========================================================== */

import { create } from 'zustand';
import { invoke } from '@tauri-apps/api/core';

export interface PythonEngineInfo {
  version: string;
  rdkit_version: string;
  python_version: string;
  platform: string;
  has_lgb?: boolean;
  lgb_error?: string;
}

interface SettingsState {
  // Configured values
  theme: 'light' | 'dark';
  density: 'compact' | 'default' | 'comfortable';
  splitRatio: number;
  defaultAlgorithm: string;
  defaultDescriptorSet: string;
  databaseDir: string;
  llmProvider: string;
  anthropicApiKey: string;
  anthropicModel: string;
  localLlmEndpoint: string;
  localLlmModel: string;
  localLlmApiKey: string;

  // Diagnostics
  pythonStatus: 'active' | 'loading' | 'disconnected';
  pythonInfo: PythonEngineInfo | null;

  // Global settings loading flag
  loaded: boolean;

  // Ollama status
  ollamaStatus: 'idle' | 'downloading' | 'starting' | 'pulling' | 'ready' | 'failed';
  ollamaProgress: number;
  ollamaError: string | null;

  // Actions
  loadAllSettings: () => Promise<void>;
  setTheme: (theme: 'light' | 'dark') => Promise<void>;
  setDensity: (density: 'compact' | 'default' | 'comfortable') => Promise<void>;
  setSplitRatio: (ratio: number) => Promise<void>;
  setDefaultAlgorithm: (algo: string) => Promise<void>;
  setDefaultDescriptorSet: (set: string) => Promise<void>;
  setDatabaseDir: (dir: string) => Promise<void>;
  setLlmProvider: (val: string) => Promise<void>;
  setAnthropicApiKey: (val: string) => Promise<void>;
  setAnthropicModel: (val: string) => Promise<void>;
  setLocalLlmEndpoint: (val: string) => Promise<void>;
  setLocalLlmModel: (val: string) => Promise<void>;
  setLocalLlmApiKey: (val: string) => Promise<void>;
  checkOllamaStatus: () => Promise<void>;
  startOllamaSidecar: (modelName?: string) => Promise<void>;

  // Python management actions
  fetchPythonDiagnostics: () => Promise<void>;
  restartPython: () => Promise<void>;
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  theme: 'light',
  density: 'default',
  splitRatio: 0.8,
  defaultAlgorithm: 'Random Forest',
  defaultDescriptorSet: 'MorganFingerprints',
  databaseDir: '',
  llmProvider: 'local',
  anthropicApiKey: '',
  anthropicModel: 'claude-3-5-haiku-20241022',
  localLlmEndpoint: 'http://localhost:11434/v1',
  localLlmModel: 'qwen2.5:3b',
  localLlmApiKey: '',

  pythonStatus: 'disconnected',
  pythonInfo: null,
  loaded: false,

  ollamaStatus: 'idle',
  ollamaProgress: 0,
  ollamaError: null,

  loadAllSettings: async () => {
    try {
      const themeVal = (await invoke<string | null>('get_setting', { key: 'theme' })) || 'light';
      const densityVal = (await invoke<string | null>('get_setting', { key: 'density' })) || 'default';
      const splitVal = (await invoke<string | null>('get_setting', { key: 'split_ratio' })) || '0.8';
      const algoVal = (await invoke<string | null>('get_setting', { key: 'default_algorithm' })) || 'Random Forest';
      const descVal = (await invoke<string | null>('get_setting', { key: 'default_descriptor_set' })) || 'MorganFingerprints';
      const dbDirVal = await invoke<string>('get_database_dir');
      const providerVal = (await invoke<string | null>('get_setting', { key: 'llm_provider' })) || 'local';
      const antKeyVal = (await invoke<string | null>('get_setting', { key: 'anthropic_api_key' })) || '';
      const antModelVal = (await invoke<string | null>('get_setting', { key: 'anthropic_model' })) || 'claude-3-5-haiku-20241022';
      const locEndpointVal = (await invoke<string | null>('get_setting', { key: 'local_llm_endpoint' })) || 'http://localhost:11434/v1';
      const locModelVal = (await invoke<string | null>('get_setting', { key: 'local_llm_model' })) || 'qwen2.5:3b';
      const locKeyVal = (await invoke<string | null>('get_setting', { key: 'local_llm_api_key' })) || '';

      // Apply initial theme & density attributes
      document.documentElement.setAttribute('data-theme', themeVal);
      document.documentElement.setAttribute('data-density', densityVal);

      set({
        theme: themeVal === 'dark' ? 'dark' : 'light',
        density: densityVal as 'compact' | 'default' | 'comfortable',
        splitRatio: parseFloat(splitVal),
        defaultAlgorithm: algoVal,
        defaultDescriptorSet: descVal,
        databaseDir: dbDirVal,
        llmProvider: providerVal,
        anthropicApiKey: antKeyVal,
        anthropicModel: antModelVal,
        localLlmEndpoint: locEndpointVal,
        localLlmModel: locModelVal,
        localLlmApiKey: locKeyVal,
        loaded: true,
      });

      // Fetch Ollama status lazily
      await get().checkOllamaStatus();

      // Automatically start/download Ollama if local provider is active
      if (providerVal === 'local') {
        get().startOllamaSidecar(locModelVal);
      }

      // Lazily fetch python engine status
      await get().fetchPythonDiagnostics();
    } catch (e) {
      console.error('[ERROR] Failed to load persistent settings:', e);
      set({ loaded: true });
    }
  },

  setTheme: async (theme: 'light' | 'dark') => {
    try {
      document.documentElement.setAttribute('data-theme', theme);
      set({ theme });
      await invoke('set_setting', { key: 'theme', value: theme });
    } catch (e) {
      console.error('[ERROR] Failed to persist theme:', e);
    }
  },

  setDensity: async (density: 'compact' | 'default' | 'comfortable') => {
    try {
      document.documentElement.setAttribute('data-density', density);
      set({ density });
      await invoke('set_setting', { key: 'density', value: density });
    } catch (e) {
      console.error('[ERROR] Failed to persist density:', e);
    }
  },

  setSplitRatio: async (ratio: number) => {
    try {
      set({ splitRatio: ratio });
      await invoke('set_setting', { key: 'split_ratio', value: String(ratio) });
    } catch (e) {
      console.error('[ERROR] Failed to persist split ratio:', e);
    }
  },

  setDefaultAlgorithm: async (algo: string) => {
    try {
      set({ defaultAlgorithm: algo });
      await invoke('set_setting', { key: 'default_algorithm', value: algo });
    } catch (e) {
      console.error('[ERROR] Failed to persist default algorithm:', e);
    }
  },

  setDefaultDescriptorSet: async (descSet: string) => {
    try {
      set({ defaultDescriptorSet: descSet });
      await invoke('set_setting', { key: 'default_descriptor_set', value: descSet });
    } catch (e) {
      console.error('[ERROR] Failed to persist default descriptor set:', e);
    }
  },

  setDatabaseDir: async (dir: string) => {
    try {
      set({ databaseDir: dir });
      await invoke('set_database_dir', { dir });
    } catch (e) {
      console.error('[ERROR] Failed to set custom database directory:', e);
    }
  },

  setLlmProvider: async (val: string) => {
    try {
      set({ llmProvider: val });
      await invoke('set_setting', { key: 'llm_provider', value: val });
      
      // Auto-start Ollama sidecar if switched to local LLM
      if (val === 'local') {
        const modelName = get().localLlmModel || 'qwen2.5:3b';
        get().startOllamaSidecar(modelName);
      }
    } catch (e) {
      console.error('[ERROR] Failed to persist llm_provider:', e);
    }
  },

  setAnthropicApiKey: async (val: string) => {
    try {
      set({ anthropicApiKey: val });
      await invoke('set_setting', { key: 'anthropic_api_key', value: val });
    } catch (e) {
      console.error('[ERROR] Failed to persist anthropic_api_key:', e);
    }
  },

  setAnthropicModel: async (val: string) => {
    try {
      set({ anthropicModel: val });
      await invoke('set_setting', { key: 'anthropic_model', value: val });
    } catch (e) {
      console.error('[ERROR] Failed to persist anthropic_model:', e);
    }
  },

  setLocalLlmEndpoint: async (val: string) => {
    try {
      set({ localLlmEndpoint: val });
      await invoke('set_setting', { key: 'local_llm_endpoint', value: val });
    } catch (e) {
      console.error('[ERROR] Failed to persist local_llm_endpoint:', e);
    }
  },

  setLocalLlmModel: async (val: string) => {
    try {
      set({ localLlmModel: val });
      await invoke('set_setting', { key: 'local_llm_model', value: val });
    } catch (e) {
      console.error('[ERROR] Failed to persist local_llm_model:', e);
    }
  },

  setLocalLlmApiKey: async (val: string) => {
    try {
      set({ localLlmApiKey: val });
      await invoke('set_setting', { key: 'local_llm_api_key', value: val });
    } catch (e) {
      console.error('[ERROR] Failed to persist local_llm_api_key:', e);
    }
  },

  checkOllamaStatus: async () => {
    try {
      const res = await invoke<{
        status: 'idle' | 'downloading' | 'starting' | 'pulling' | 'ready' | 'failed';
        progress: number;
        running: boolean;
        error: string | null;
        binary_exists: boolean;
      }>('ollama_check_status');
      
      set({
        ollamaStatus: res.status,
        ollamaProgress: res.progress,
        ollamaError: res.error,
      });
    } catch (e) {
      console.error('Failed to check Ollama status:', e);
    }
  },

  startOllamaSidecar: async (modelName = 'qwen2.5:3b') => {
    set({ ollamaStatus: 'downloading', ollamaProgress: 0, ollamaError: null });
    try {
      await invoke('ollama_start_sidecar', { modelName });
      
      // Start polling status
      const poll = setInterval(async () => {
        try {
          const res = await invoke<{
            status: 'idle' | 'downloading' | 'starting' | 'pulling' | 'ready' | 'failed';
            progress: number;
            running: boolean;
            error: string | null;
            binary_exists: boolean;
          }>('ollama_check_status');
          
          set({
            ollamaStatus: res.status,
            ollamaProgress: res.progress,
            ollamaError: res.error,
          });

          if (res.status === 'ready' || res.status === 'failed') {
            clearInterval(poll);
          }
        } catch (e) {
          clearInterval(poll);
          set({ ollamaStatus: 'failed', ollamaError: String(e) });
        }
      }, 1000);
    } catch (e) {
      set({ ollamaStatus: 'failed', ollamaError: String(e) });
    }
  },

  fetchPythonDiagnostics: async () => {
    set({ pythonStatus: 'loading' });
    try {
      const info = await invoke<PythonEngineInfo>('get_python_engine_info');
      set({ pythonInfo: info, pythonStatus: 'active' });
    } catch (e) {
      console.warn('[WARNING] Python computational engine currently unreachable:', e);
      set({ pythonInfo: null, pythonStatus: 'disconnected' });
    }
  },

  restartPython: async () => {
    set({ pythonStatus: 'loading', pythonInfo: null });
    try {
      await invoke('restart_python_engine');
      await get().fetchPythonDiagnostics();
    } catch (e) {
      console.error('[ERROR] Failed to restart Python computational engine:', e);
      set({ pythonStatus: 'disconnected' });
    }
  },
}));
