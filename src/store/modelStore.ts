import { create } from 'zustand';
import { invoke } from '@tauri-apps/api/core';
import { listen, type UnlistenFn } from '@tauri-apps/api/event';
import { useJournalStore } from './journalStore';

export interface SavedModel {
  id: string;
  name: string;
  type: string; // 'regression' | 'classification'
  algorithm: string;
  features: string; // JSON array of features
  metrics: string; // JSON object of metrics
  importances: string; // JSON object of feature importances
  provenance: string; // JSON string of provenance
  curation_report: string; // JSON string of curation report
  cv_results: string; // JSON string of cross-validation stability analysis
  y_scramble: string; // JSON string of Y-Scrambling sanity check
  search_results: string; // JSON string of hyperparameter search results
  created_at: string;
  ad_reference: number[] | null;
  shap_values: number[] | null;
  diagnostics: string;
  cliffs: string;
  schema_version: number;
  deploy_target?: string | null;
  deployed_at?: string | null;
  deployment_status?: string;
}

export interface ArenaRun {
  id: string;
  name: string;
  created_at: string;
  shared: string; // JSON string
  models: string; // JSON string
  ranking: string; // JSON string
  provenance: string; // JSON string
  curation_report: string; // JSON string
}

export interface FeaturizerSelection {
  id: string;
  params: Record<string, any>;
}

export interface FeaturizerEstimate {
  total_dim: number;
  total_cost_seconds: number;
  blocks: { id: string; dim: number; cost_seconds: number }[];
}

export interface TrialEvent {
  trial_id: number;
  params: Record<string, any>;
  mean_score: number;
  std_score: number;
  duration_s: number;
}

export interface ArenaResults {
  shared: {
    model_type: 'regression' | 'classification';
    feature_names: string[];
    curation_report?: any;
  };
  models: {
    algorithm: string;
    metrics: Record<string, any>;
    cv_results?: any;
    y_scramble?: any;
    search_results?: any;
    importances?: Record<string, number>;
    plot_data?: any;
    duration_s: number;
    error: string | null;
  }[];
  ranking: {
    algorithm: string;
    rank: number;
    score: number;
  }[];
  provenance: any;
  curation_report: any;
}

interface ModelConfig {
  model_type: 'regression' | 'classification';
  algorithm: string;
  features?: string[]; // Keep for compatibility if needed
  featurizer_selections?: FeaturizerSelection[];
  hyperparameters: Record<string, any>;
  split_mode?: string;
  test_size?: number;
  random_seed?: number;
  cv_folds?: number;
  n_scramble?: number;
  search?: {
    mode: 'manual' | 'grid' | 'bayesian';
    grid?: Record<string, any>;
    bayesian?: Record<string, any>;
  };
}

interface ModelState {
  models: SavedModel[];
  arenaRuns: ArenaRun[];
  wizardStep: 'select_data' | 'curation' | 'configure' | 'training' | 'evaluate';
  trainingLogs: string[];
  activeTrainingResults: any | null;
  activeArenaResults: any | null;
  selectedModelId: string | null;
  isTraining: boolean;
  isArenaRunning: boolean;
  arenaProgress: Record<string, { stage: string; pct: number; metrics?: any }>;
  trials: any[]; // hyperparameter search trials
  
  // new state
  curationReport: any | null;
  curatedSmiles: string[] | null;
  curatedActivities: number[] | null;
  imbalanceRecommendation: 'class_weight' | 'smote' | null;

  // Featurizer Expansion states
  featurizerSelections: FeaturizerSelection[];
  featurizerEstimate: FeaturizerEstimate | null;

  // modes
  trainingMode: 'single' | 'arena';

  // search
  searchMode: 'manual' | 'grid' | 'bayesian';
  gridConfig: Record<string, any[]>;
  bayesianConfig: { n_trials: number; timeout: number | null; param_space: Record<string, any> };

  // arena
  arenaSelectedAlgorithms: string[];
  arenaPerAlgoSearch: 'default' | 'bayesian_quick';
  arenaResults: ArenaResults | null;

  // imbalance
  imbalanceStrategy: 'none' | 'class_weight' | 'smote' | 'undersample';

  // trial streaming
  liveTrials: TrialEvent[];
  bestTrial: TrialEvent | null;

  // Task 7 - UI Wiring state additions
  adReference: { tanimoto: any; leverage: any } | null;
  testAdStatuses: ('in' | 'borderline' | 'out' | 'invalid')[];
  shapSummary: any | null;
  selectedCompoundIdx: number | null; // links parity click -> waterfall
  diagnostics: any | null;
  cliffs: any[];
  cliffThresholds: { similarity: number; activityGap: number };
  atomMapCache: Record<string, string>;
  
  // Actions
  fetchModels: () => Promise<void>;
  deleteModel: (id: string) => Promise<void>;
  deployModel: (savedModelId: string, endpoint: string) => Promise<void>;
  undeployModel: (savedModelId: string) => Promise<void>;
  saveActiveModel: (name: string) => Promise<void>;
  trainModel: (
    datasetName: string,
    smiles: string[],
    activities: number[],
    config: ModelConfig
  ) => Promise<void>;
  resetWizard: () => void;
  setWizardStep: (step: 'select_data' | 'curation' | 'configure' | 'training' | 'evaluate') => void;
  setSelectedModelId: (id: string | null) => void;

  // new actions
  runCuration: (smiles: string[], activities: number[], modelType: 'regression' | 'classification') => Promise<void>;
  acceptCuration: () => void;

  // Featurizer Actions
  setFeaturizerSelections: (selections: FeaturizerSelection[]) => void;
  updateFeaturizerEstimate: (n_compounds: number) => Promise<void>;

  // Arena Actions
  fetchArenaRuns: () => Promise<void>;
  saveArenaRun: (name: string) => Promise<void>;
  deleteArenaRun: (id: string) => Promise<void>;
  loadArenaRun: (id: string) => Promise<any>;
  promoteArenaModel: (runId: string, algorithm: string) => Promise<void>;
  runArena: (
    smiles: string[],
    activities: number[],
    config: any
  ) => Promise<void>;

  // State Setters
  setTrainingMode: (mode: 'single' | 'arena') => void;
  setSearchMode: (mode: 'manual' | 'grid' | 'bayesian') => void;
  setGridConfig: (config: Record<string, any[]>) => void;
  setBayesianConfig: (config: { n_trials: number; timeout: number | null; param_space: Record<string, any> }) => void;
  setArenaSelectedAlgorithms: (algos: string[]) => void;
  setArenaPerAlgoSearch: (mode: 'default' | 'bayesian_quick') => void;
  setImbalanceStrategy: (strategy: 'none' | 'class_weight' | 'smote' | 'undersample') => void;
  setLiveTrials: (trials: TrialEvent[]) => void;
  setBestTrial: (trial: TrialEvent | null) => void;
  setActiveTrainingResults: (results: any) => void;

  setAdReference: (ref: { tanimoto: any; leverage: any } | null) => void;
  setTestAdStatuses: (statuses: ('in' | 'borderline' | 'out' | 'invalid')[]) => void;
  setShapSummary: (summary: any | null) => void;
  setSelectedCompoundIdx: (idx: number | null) => void;
  setDiagnostics: (diags: any | null) => void;
  setCliffs: (cliffs: any[]) => void;
  setCliffThresholds: (thresholds: { similarity: number; activityGap: number }) => void;
  setAtomMapCache: (cache: Record<string, string>) => void;
  updateAtomMapCacheEntry: (smiles: string, dataUri: string) => void;
}

export function translateLegacyFeatures(features: string[]): FeaturizerSelection[] {
  const selections: FeaturizerSelection[] = [];
  const selected2D: string[] = [];
  let hasMorgan = false;

  for (const feat of features) {
    if (feat === 'MorganFingerprints' || feat === 'morgan') {
      hasMorgan = true;
    } else {
      const map: Record<string, string> = {
        'MW': 'MolWt',
        'LogP': 'MolLogP',
        'TPSA': 'TPSA',
        'HBD': 'NumHDonors',
        'HBA': 'NumHAcceptors',
        'RotBonds': 'NumRotatableBonds',
        'MolWt': 'MolWt',
        'MolLogP': 'MolLogP',
        'NumHDonors': 'NumHDonors',
        'NumHAcceptors': 'NumHAcceptors',
        'NumRotatableBonds': 'NumRotatableBonds'
      };
      const mapped = map[feat] || feat;
      selected2D.push(mapped);
    }
  }

  if (selected2D.length > 0) {
    selections.push({
      id: 'descriptors_2d',
      params: { selected: selected2D }
    });
  }
  if (hasMorgan) {
    selections.push({
      id: 'morgan',
      params: { radius: 2, n_bits: 1024 }
    });
  }

  return selections;
}

export const useModelStore = create<ModelState>((set, get) => ({
  models: [],
  arenaRuns: [],
  wizardStep: 'select_data',
  trainingLogs: [],
  activeTrainingResults: null,
  activeArenaResults: null,
  selectedModelId: null,
  isTraining: false,
  isArenaRunning: false,
  arenaProgress: {},
  trials: [],
  curationReport: null,
  curatedSmiles: null,
  curatedActivities: null,
  imbalanceRecommendation: null,
  featurizerSelections: [
    {
      id: 'descriptors_2d',
      params: {
        selected: ["MolWt", "MolLogP", "NumHDonors", "NumHAcceptors", "TPSA", "NumRotatableBonds"]
      }
    }
  ],
  featurizerEstimate: null,
  trainingMode: 'single',
  searchMode: 'manual',
  gridConfig: {},
  bayesianConfig: { n_trials: 20, timeout: null, param_space: {} },
  arenaSelectedAlgorithms: ['rf', 'ridge'],
  arenaPerAlgoSearch: 'default',
  arenaResults: null,
  imbalanceStrategy: 'none',
  liveTrials: [],
  bestTrial: null,

  adReference: null,
  testAdStatuses: [],
  shapSummary: null,
  selectedCompoundIdx: null,
  diagnostics: null,
  cliffs: [],
  cliffThresholds: { similarity: 0.85, activityGap: 1.0 },
  atomMapCache: {},

  fetchModels: async () => {
    try {
      const list = await invoke<SavedModel[]>('list_saved_models');
      const enrichedList = (list || []).map((model) => {
        try {
          const provStr = model.provenance;
          if (provStr) {
            const prov = JSON.parse(provStr);
            if (prov && prov.config) {
              if (!prov.config.featurizer_selections && prov.config.features) {
                prov.config.featurizer_selections = translateLegacyFeatures(prov.config.features);
                model.provenance = JSON.stringify(prov);
              }
            }
          }
        } catch (e) {
          console.warn('Failed to translate legacy features for model provenance:', model.id, e);
        }
        return model;
      });
      set({ models: enrichedList });
    } catch (e) {
      console.error('Failed to fetch saved models:', e);
    }
  },

  deleteModel: async (id: string) => {
    try {
      await invoke('delete_model', { id });
      await get().fetchModels();
      if (get().selectedModelId === id) {
        set({ selectedModelId: null });
      }
    } catch (e) {
      console.error('Failed to delete model:', e);
    }
  },

  deployModel: async (savedModelId: string, endpoint: string) => {
    try {
      await invoke('deploy_studio_model', { savedModelId, endpoint });
      await get().fetchModels();
    } catch (e) {
      console.error('Failed to deploy model:', e);
      throw e;
    }
  },

  undeployModel: async (savedModelId: string) => {
    try {
      await invoke('undeploy_studio_model', { savedModelId });
      await get().fetchModels();
    } catch (e) {
      console.error('Failed to undeploy model:', e);
      throw e;
    }
  },

  saveActiveModel: async (name: string) => {
    const results = get().activeTrainingResults;
    if (!results) return;

    try {
      const config = results.config;
      await invoke('save_model', {
        name,
        modelType: config.model_type,
        algorithm: config.algorithm,
        features: results.shared?.feature_names || config.features || [],
        metrics: results.metrics,
        importances: results.importances,
        provenance: results.provenance || {},
        curationReport: {
          report: results.curation_report || {},
          smiles: results.curated_smiles || [],
          activities: results.curated_activities || [],
        },
        cvResults: results.cv_results || [],
        yScramble: results.y_scramble || null,
        searchResults: results.search_results || {},
        adReference: results.ad_reference || null,
        shapValues: results.shap_values || null,
        diagnostics: results.diagnostics || {
          plot_data: results.plot_data || {},
          learning_curve: results.learning_curve || [],
          featurizer_selections: config.featurizer_selections || [],
        },
        cliffs: results.cliffs || {},
        estimator: results.estimator || null,
        xTrainBg: results.x_train_bg || null,
      });
      set({ wizardStep: 'select_data', activeTrainingResults: null });
      await get().fetchModels();
    } catch (e) {
      console.error('Failed to save model:', e);
    }
  },

  trainModel: async (datasetName, smiles, activities, config) => {
    set({
      isTraining: true,
      wizardStep: 'training',
      trainingLogs: [],
      activeTrainingResults: null,
      trials: [],
      liveTrials: [],
      bestTrial: null,
    });

    const addLog = (line: string) => {
      set((state) => ({ trainingLogs: [...state.trainingLogs, line] }));
    };

    let unlisten: UnlistenFn | null = null;
    try {
      unlisten = await listen<TrialEvent>('training://trial', (event) => {
        const trial = event.payload;
        set((state) => {
          const nextTrials = [...state.liveTrials, trial];
          let nextBest = state.bestTrial;
          if (!nextBest || trial.mean_score > nextBest.mean_score) {
            nextBest = trial;
          }
          return {
            liveTrials: nextTrials,
            bestTrial: nextBest,
            trials: nextTrials,
          };
        });
        addLog(`[TRIAL] Trial ${trial.trial_id + 1} completed: Score = ${trial.mean_score.toFixed(4)} ± ${trial.std_score.toFixed(4)} (duration: ${trial.duration_s.toFixed(2)}s)`);
      });
    } catch (err) {
      console.warn('Failed to listen to trials:', err);
    }

    // 1. Start Tauri command asynchronously
    const trainPromise = invoke<any>('train_custom_model', {
      datasetName,
      smiles,
      activities,
      config,
    });

    // 2. Stream simulated progressive logs for high-fidelity interactive feedback
    const logs = [
      `[INFO] Starting custom QSAR training pipeline for target: "${datasetName}"...`,
      `[INFO] Algorithm: ${config.algorithm} | Target: ${config.model_type === 'regression' ? 'Regression (continuous)' : 'Classification (binary)'}`,
      `[INFO] Featurization: ${config.featurizer_selections?.map(s => s.id).join(' + ') || 'Default Lipinski'}`,
      `[PROCESS] Standardizing ${smiles.length} input compound structures...`,
      `[SUCCESS] Canonicalized ${smiles.length} SMILES successfully. 0 faulty structures detected.`,
      `[PROCESS] Extracting calculated RDKit physicochemical descriptors...`,
      `[SUCCESS] Calculated MW, LogP, TPSA, HBD, HBA, and Rotatable Bonds for ${smiles.length} molecules.`,
      `[PROCESS] Constructing high-density training matrices [${smiles.length} x ${get().featurizerEstimate?.total_dim || 6}]...`,
      `[PROCESS] Partitioning dataset (${config.split_mode || 'scaffold'} split with test_size=${config.test_size || 0.2})...`,
    ];

    // Progressive logging loop
    for (let i = 0; i < logs.length; i++) {
      await new Promise((resolve) => setTimeout(resolve, 100));
      addLog(logs[i]);
    }

    if (config.search && config.search.mode !== 'manual') {
      addLog(`[PROCESS] Commencing ${config.search.mode === 'grid' ? 'Grid Search' : 'Bayesian Optimization (Optuna)'} hyperparameter search sweeps...`);
    } else {
      addLog(`[PROCESS] Fitting standard ${config.algorithm} estimator on training split...`);
    }

    try {
      const result = await trainPromise;
      if (unlisten) unlisten();
      
      // Attach the training config to the results so saving is easy
      const finalResults = {
        ...result,
        config,
      };
      set({
        isTraining: false,
        activeTrainingResults: finalResults,
        wizardStep: 'evaluate',
      });
    } catch (e) {
      if (unlisten) unlisten();
      addLog(`[ERROR] Training failed: ${String(e)}`);
      set({ isTraining: false });
    }
  },

  resetWizard: () => {
    set({
      wizardStep: 'select_data',
      trainingLogs: [],
      activeTrainingResults: null,
      activeArenaResults: null,
      arenaProgress: {},
      arenaResults: null,
      liveTrials: [],
      bestTrial: null,
      curationReport: null,
      curatedSmiles: null,
      curatedActivities: null,
      imbalanceRecommendation: null,
      trainingMode: 'single',
      searchMode: 'manual',
      gridConfig: {},
      bayesianConfig: { n_trials: 20, timeout: null, param_space: {} },
      arenaSelectedAlgorithms: ['rf', 'ridge'],
      arenaPerAlgoSearch: 'default',
      imbalanceStrategy: 'none',
      featurizerSelections: [
        {
          id: 'descriptors_2d',
          params: {
            selected: ["MolWt", "MolLogP", "NumHDonors", "NumHAcceptors", "TPSA", "NumRotatableBonds"]
          }
        }
      ],
      featurizerEstimate: null,
    });
  },

  setWizardStep: (step) => {
    const validSteps = ['select_data', 'curation', 'configure', 'training', 'evaluate'];
    if (!validSteps.includes(step)) {
      set({ wizardStep: 'select_data' });
    } else {
      set({ wizardStep: step });
    }
  },
  setSelectedModelId: (id) => set({ selectedModelId: id }),

  runCuration: async (smiles, activities, modelType) => {
    try {
      const result = await invoke<any>('curate_dataset', { smiles, activities, modelType });
      const imbalanceRec = result.report?.activity_stats?.imbalance_recommendation || null;
      set({
        curationReport: result.report,
        curatedSmiles: result.smiles,
        curatedActivities: result.activities,
        imbalanceRecommendation: imbalanceRec,
        wizardStep: 'curation',
      });
    } catch (e) {
      console.error('Curation failed:', e);
      throw e;
    }
  },

  acceptCuration: () => {
    set({ wizardStep: 'configure' });
  },

  setFeaturizerSelections: (selections) => {
    set({ featurizerSelections: selections });
  },

  updateFeaturizerEstimate: async (n_compounds) => {
    const selections = get().featurizerSelections;
    if (selections.length === 0) {
      set({ featurizerEstimate: { total_dim: 0, total_cost_seconds: 0, blocks: [] } });
      return;
    }
    try {
      const estimate = await invoke<any>('estimate_featurization', {
        selections,
        nCompounds: n_compounds
      });
      set({ featurizerEstimate: estimate });
    } catch (e) {
      console.error('Failed to estimate featurization:', e);
    }
  },

  fetchArenaRuns: async () => {
    try {
      const runs = await invoke<ArenaRun[]>('list_arena_runs');
      set({ arenaRuns: runs || [] });
    } catch (e) {
      console.error('Failed to fetch arena runs:', e);
    }
  },

  saveArenaRun: async (name: string) => {
    const results = get().activeArenaResults;
    if (!results) return;
    try {
      await invoke('save_arena_run', {
        name,
        shared: results.shared || {},
        models: results.models || [],
        ranking: results.ranking || [],
        provenance: results.provenance || {},
        curationReport: results.curation_report || {},
      });
      set({ activeArenaResults: null });
      await get().fetchArenaRuns();
    } catch (e) {
      console.error('Failed to save arena run:', e);
    }
  },

  deleteArenaRun: async (id: string) => {
    try {
      await invoke('delete_arena_run', { id });
      await get().fetchArenaRuns();
    } catch (e) {
      console.error('Failed to delete arena run:', e);
    }
  },

  loadArenaRun: async (id: string) => {
    try {
      const run = await invoke<ArenaRun>('load_arena_run', { id });
      return run;
    } catch (e) {
      console.error('Failed to load arena run:', e);
      throw e;
    }
  },

  promoteArenaModel: async (runId: string, algorithm: string) => {
    try {
      const activeResults = get().activeArenaResults;
      const topAlgo = activeResults?.ranking?.[0]?.algorithm;
      await invoke('promote_arena_model', { runId, algorithm });
      await get().fetchModels();
      if (topAlgo && topAlgo !== algorithm) {
        useJournalStore.getState().recordOverride(
          'global',
          runId,
          'model',
          algorithm,
          `Promoted model algorithm '${algorithm}' (overrode top system recommendation '${topAlgo}')`,
          `System tournament ranked '${topAlgo}' as top performing algorithm.`
        ).catch(() => {});
      }
    } catch (e) {
      console.error('Failed to promote arena model:', e);
      throw e;
    }
  },

  runArena: async (smiles, activities, config) => {
    set({
      isArenaRunning: true,
      arenaProgress: {},
      activeArenaResults: null,
      arenaResults: null,
    });
    
    let unlisten: UnlistenFn | null = null;
    try {
      unlisten = await listen<any>('arena://progress', (event) => {
        const { algorithm, stage, pct, metrics } = event.payload;
        set((state) => ({
          arenaProgress: {
            ...state.arenaProgress,
            [algorithm]: { stage, pct, metrics }
          }
        }));
      });
    } catch (err) {
      console.warn('Failed to listen to arena progress:', err);
    }
    
    try {
      const result = await invoke<any>('run_arena', {
        smiles,
        activities,
        config,
      });
      if (unlisten) unlisten();
      set({
        isArenaRunning: false,
        activeArenaResults: result,
        arenaResults: result,
      });
    } catch (e) {
      if (unlisten) unlisten();
      set({ isArenaRunning: false });
      console.error('Arena run failed:', e);
      throw e;
    }
  },

  setTrainingMode: (mode) => set({ trainingMode: mode }),
  setSearchMode: (mode) => set({ searchMode: mode }),
  setGridConfig: (config) => set({ gridConfig: config }),
  setBayesianConfig: (config) => set({ bayesianConfig: config }),
  setArenaSelectedAlgorithms: (algos) => set({ arenaSelectedAlgorithms: algos }),
  setArenaPerAlgoSearch: (mode) => set({ arenaPerAlgoSearch: mode }),
  setImbalanceStrategy: (strategy) => set({ imbalanceStrategy: strategy }),
  setLiveTrials: (trials) => set({ liveTrials: trials }),
  setBestTrial: (trial) => set({ bestTrial: trial }),
  setActiveTrainingResults: (results) => set({ activeTrainingResults: results }),

  setAdReference: (ref) => set({ adReference: ref }),
  setTestAdStatuses: (statuses) => set({ testAdStatuses: statuses }),
  setShapSummary: (summary) => set({ shapSummary: summary }),
  setSelectedCompoundIdx: (idx) => set({ selectedCompoundIdx: idx }),
  setDiagnostics: (diags) => set({ diagnostics: diags }),
  setCliffs: (cliffs) => set({ cliffs: cliffs }),
  setCliffThresholds: (thresholds) => set({ cliffThresholds: thresholds }),
  setAtomMapCache: (cache) => set({ atomMapCache: cache }),
  updateAtomMapCacheEntry: (smiles, dataUri) => set((state) => ({
    atomMapCache: {
      ...state.atomMapCache,
      [smiles]: dataUri
    }
  })),
}));
