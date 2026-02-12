/* ==========================================================
   Edeon Desktop — Workflow Store
   Zustand store for workflow execution and results.
   Listens to Tauri events for real-time progress updates.
   ========================================================== */

import { create } from 'zustand';
import { invoke } from '@tauri-apps/api/core';
import { listen, type UnlistenFn } from '@tauri-apps/api/event';
import type {
  WorkflowRecord,
  WorkflowResultRecord,
  WorkflowProgress,
  PipelineStage,
} from '../types';

// Default pipeline template (before a workflow runs)
const DEFAULT_STAGES: PipelineStage[] = [
  { id: 1, name: 'Standardize', description: 'Salts, tautomers', status: 'waiting' },
  { id: 2, name: 'Properties', description: 'MW, LogP, TPSA', status: 'waiting' },
  { id: 3, name: 'Pesticide-likeness', description: 'Tice rules filter', status: 'waiting' },
];

interface WorkflowState {
  activeWorkflow: WorkflowRecord | null;
  stages: PipelineStage[];
  results: WorkflowResultRecord[];
  isRunning: boolean;
  pythonReady: boolean;
  error: string | null;
  unlisten: UnlistenFn | null;

  // Actions
  startWorkflow: (projectId: string) => Promise<void>;
  fetchResults: (workflowId: string) => Promise<void>;
  loadLatestWorkflow: (projectId: string) => Promise<void>;
  checkPython: () => Promise<void>;
  setupEventListener: () => Promise<void>;
  cleanup: () => void;
  reset: () => void;
}

export const useWorkflowStore = create<WorkflowState>((set, get) => ({
  activeWorkflow: null,
  stages: DEFAULT_STAGES.map((s) => ({ ...s })),
  results: [],
  isRunning: false,
  pythonReady: false,
  error: null,
  unlisten: null,

  startWorkflow: async (projectId: string) => {
    set({ isRunning: true, error: null, results: [] });

    // Reset stages to running state
    set({
      stages: [
        { id: 1, name: 'Standardize', description: 'Salts, tautomers', status: 'running', progressLabel: 'Processing...' },
        { id: 2, name: 'Properties', description: 'MW, LogP, TPSA', status: 'waiting' },
        { id: 3, name: 'Pesticide-likeness', description: 'Tice rules filter', status: 'waiting' },
      ],
    });

    // Setup event listener before starting
    await get().setupEventListener();

    try {
      const workflow = await invoke<WorkflowRecord>('start_workflow', {
        projectId,
      });

      // Workflow completed — fetch results
      set({ activeWorkflow: workflow, isRunning: false });
      await get().fetchResults(workflow.id);

      // Update stages to all done
      set({
        stages: [
          { id: 1, name: 'Standardize', description: 'Salts, tautomers', status: 'done', compoundCount: workflow.compounds_total, compoundLabel: 'compounds' },
          { id: 2, name: 'Properties', description: 'MW, LogP, TPSA', status: 'done', compoundCount: workflow.compounds_total, compoundLabel: 'computed' },
          { id: 3, name: 'Pesticide-likeness', description: 'Tice rules filter', status: 'done', compoundCount: workflow.compounds_total, compoundLabel: 'scored' },
        ],
      });
    } catch (e) {
      set({ error: String(e), isRunning: false });
    }
  },

  fetchResults: async (workflowId: string) => {
    try {
      const results = await invoke<WorkflowResultRecord[]>('get_workflow_results', {
        workflowId,
      });
      set({ results });
    } catch (e) {
      console.error('Failed to fetch workflow results:', e);
    }
  },

  loadLatestWorkflow: async (projectId: string) => {
    try {
      const workflows = await invoke<WorkflowRecord[]>('list_workflows', { projectId });
      if (workflows.length > 0) {
        const latest = workflows[0];
        set({ activeWorkflow: latest });

        if (latest.status === 'complete') {
          await get().fetchResults(latest.id);
          set({
            stages: [
              { id: 1, name: 'Standardize', description: 'Salts, tautomers', status: 'done', compoundCount: latest.compounds_total, compoundLabel: 'compounds' },
              { id: 2, name: 'Properties', description: 'MW, LogP, TPSA', status: 'done', compoundCount: latest.compounds_total, compoundLabel: 'computed' },
              { id: 3, name: 'Pesticide-likeness', description: 'Tice rules filter', status: 'done', compoundCount: latest.compounds_total, compoundLabel: 'scored' },
            ],
          });
        }
      }
    } catch (e) {
      console.error('Failed to load workflows:', e);
    }
  },

  checkPython: async () => {
    try {
      const ready = await invoke<boolean>('check_python_engine');
      set({ pythonReady: ready });
    } catch {
      set({ pythonReady: false });
    }
  },

  setupEventListener: async () => {
    // Clean up any existing listener
    const existing = get().unlisten;
    if (existing) existing();

    const unlisten = await listen<WorkflowProgress>('workflow://progress', (event) => {
      const progress = event.payload;

      // Update stages based on progress
      const stagesComplete = progress.stages_complete;
      const currentStage = progress.current_stage;

      const stageNames = ['Standardize', 'Properties', 'Pesticide-likeness'];
      const stageDescs = ['Salts, tautomers', 'MW, LogP, TPSA', 'Tice rules filter'];

      const newStages: PipelineStage[] = stageNames.map((name, i) => {
        const stageNum = i + 1;
        let status: 'done' | 'running' | 'waiting';
        if (stageNum <= stagesComplete) {
          status = 'done';
        } else if (name === currentStage) {
          status = 'running';
        } else {
          status = 'waiting';
        }

        const stage: PipelineStage = {
          id: stageNum,
          name,
          description: stageDescs[i],
          status,
        };

        if (status === 'done' && progress.stage_result?.stage === name) {
          stage.compoundCount = progress.stage_result.compound_count;
          stage.compoundLabel = i === 0 ? 'compounds' : i === 1 ? 'computed' : 'scored';
        }

        if (status === 'running') {
          stage.progressLabel = `${progress.compounds_processed}/${progress.compounds_total}`;
        }

        return stage;
      });

      set({ stages: newStages });
    });

    set({ unlisten });
  },

  cleanup: () => {
    const unlisten = get().unlisten;
    if (unlisten) unlisten();
    set({ unlisten: null });
  },

  reset: () => {
    get().cleanup();
    set({
      activeWorkflow: null,
      stages: DEFAULT_STAGES.map((s) => ({ ...s })),
      results: [],
      isRunning: false,
      error: null,
    });
  },
}));
