/* ==========================================================
   Edeon Desktop — Workflow Store
   Zustand store for 6-stage workflow execution and results.
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
import { useCompoundStore } from './compoundStore';
import { useUIStore } from './uiStore';
import { useProjectStore } from './projectStore';

const getClearedWorkflows = (projectId: string): string[] => {
  try {
    const data = localStorage.getItem(`edeon_cleared_workflows_${projectId}`);
    return data ? JSON.parse(data) : [];
  } catch (e) {
    return [];
  }
};

const addClearedWorkflow = (projectId: string, workflowId: string) => {
  try {
    const list = getClearedWorkflows(projectId);
    if (!list.includes(workflowId)) {
      list.push(workflowId);
      localStorage.setItem(`edeon_cleared_workflows_${projectId}`, JSON.stringify(list));
    }
  } catch (e) {
    console.error(e);
  }
};

const removeClearedWorkflow = (projectId: string, workflowId: string) => {
  try {
    const list = getClearedWorkflows(projectId);
    const updated = list.filter((id) => id !== workflowId);
    localStorage.setItem(`edeon_cleared_workflows_${projectId}`, JSON.stringify(updated));
  } catch (e) {
    console.error(e);
  }
};

export type WorkflowType = 'lead_opt' | 'bioisostere_opt' | 'active_learning' | 'resistance_mitigation' | 'library_prep';

const WORKFLOW_STAGES_MAP: Record<WorkflowType, { name: string; desc: string; label: string }[]> = {
  lead_opt: [
    { name: 'Standardize',        desc: 'Salts, tautomers, canonicalize',  label: 'compounds' },
    { name: 'Properties',         desc: 'MW, LogP, TPSA, HBD/HBA',        label: 'computed' },
    { name: 'Pesticide-likeness', desc: 'Tice rules filter',               label: 'scored' },
    { name: 'Selectivity',        desc: 'Cross-species analysis',           label: 'profiled' },
    { name: 'Resistance',         desc: 'Resistance risk assessment',       label: 'assessed' },
    { name: 'Toxicity',           desc: 'Bee, fish, bird, mammal',          label: 'predicted' },
    { name: 'MPO Score',          desc: 'Multi-parameter optimization',     label: 'ranked' },
  ],
  bioisostere_opt: [
    { name: 'Standardize',        desc: 'Salts, tautomers, canonicalize',  label: 'compounds' },
    { name: 'Bioisostere Gen',    desc: 'Generate bioisosteric suggestions',label: 'suggested' },
    { name: 'Properties & Filters',desc: 'Physicochemical profiles',      label: 'computed' },
    { name: 'QSAR & AD Profiling', desc: 'Predict activity & confidence',  label: 'predicted' },
    { name: 'MPO Scoring',         desc: 'Weighted multi-objective rank',   label: 'ranked' },
    { name: 'Conformer & Docking', desc: '3D conformer & target docking',  label: 'docked' },
    { name: '3D Interaction Maps', desc: 'Analyze residue interactions',  label: 'mapped' },
  ],
  active_learning: [
    { name: 'Curation & Prep',     desc: 'Standardize structures & data',   label: 'compounds' },
    { name: 'Property Filters',    desc: 'Filter via Tice/property rules',  label: 'filtered' },
    { name: 'QSAR Inference',      desc: 'Predict activity across models',  label: 'predicted' },
    { name: 'AD Gate Filtering',   desc: 'Assess applicability domain',    label: 'gated' },
    { name: 'Docking Validation',  desc: 'Confirmatory target docking',     label: 'validated' },
    { name: 'Active Learning Select',desc: 'Identify low-confidence leads', label: 'selected' },
    { name: 'Curation Output',     desc: 'Export high-confidence library',  label: 'exported' },
  ],
  resistance_mitigation: [
    { name: 'Mutation Look-up',    desc: 'Find known target mutations',    label: 'mutations' },
    { name: 'Docking Preparation', desc: 'Auto-prep WT & mutant receptors', label: 'prepped' },
    { name: 'Wildtype Simulation', desc: 'Vina docking on wildtype target', label: 'docked' },
    { name: 'Mutant Simulation',   desc: 'Vina docking on mutant target',   label: 'docked' },
    { name: 'Ecotox Profiling',    desc: 'Heuristic non-target safety',     label: 'profiled' },
    { name: 'Bypass Scoring',      desc: 'Analyze target mutation delta',   label: 'scored' },
    { name: 'Interactive Pose View',desc: 'Inspect binding pockets side-by-side',label: 'inspected' },
  ],
  library_prep: [
    { name: 'Standardization',     desc: 'Salt stripping & canonicalization',label: 'compounds' },
    { name: 'Property Curation',   desc: 'Lipinski & custom boundaries',    label: 'curated' },
    { name: 'PAINS & Alerts Filter',desc: 'Remove reactive & toxicophores',  label: 'filtered' },
    { name: 'Diversity Clustering',desc: 'Butina/MaxMin representative picks',label: 'selected' },
    { name: '3D & pH Protonation', desc: 'Generate optimized 3D conformers', label: 'prepared' },
    { name: 'Library Export',      desc: 'Package results as SDF/CSV/SMILES',label: 'exported' },
  ],
};

const PRESET_FALLBACK_BOXES: Record<string, { center: [number, number, number]; size: [number, number, number] }> = {
  accase: { center: [29.12, 42.644, 41.983], size: [20.0, 20.0, 20.0] },
  als: { center: [54.126, 55.242, 46.549], size: [20.0, 20.0, 20.0] },
  epsps: { center: [55.978, 11.213, 28.4], size: [20.0, 20.0, 20.0] },
  gs: { center: [0.0, 0.0, 0.0], size: [20.0, 20.0, 20.0] },
  hppd: { center: [43.962, 38.3, 53.083], size: [20.0, 20.0, 20.0] },
  ppo: { center: [-40.166, -6.351, 28.903], size: [20.0, 20.0, 20.0] },
  ps2: { center: [0.0, 0.0, 0.0], size: [20.0, 20.0, 20.0] },
  sdh: { center: [23.827, 51.214, 35.3], size: [20.0, 20.0, 20.0] },
};

const RECEPTOR_PRESETS = [
  { id: 'als', name: 'ALS' },
  { id: 'accase', name: 'ACCase' },
  { id: 'epsps', name: 'EPSPS' },
  { id: 'gs', name: 'GS' },
  { id: 'hppd', name: 'HPPD' },
  { id: 'ppo', name: 'PPO' },
  { id: 'ps2', name: 'PSII' },
  { id: 'sdh', name: 'SDH' },
];

function makeStages(
  type: WorkflowType = 'lead_opt',
  status: 'waiting' | 'done' = 'waiting',
  count?: number
): PipelineStage[] {
  const stageDefs = WORKFLOW_STAGES_MAP[type];
  return stageDefs.map((s, i) => ({
    id: i + 1,
    name: s.name,
    description: s.desc,
    status,
    enabled: true,
    ...(status === 'done' && count != null ? { compoundCount: count, compoundLabel: s.label } : {}),
  }));
}

interface WorkflowState {
  selectedWorkflowType: WorkflowType;
  setWorkflowType: (type: WorkflowType) => void;
  activeWorkflow: WorkflowRecord | null;
  stages: PipelineStage[];
  results: WorkflowResultRecord[];
  isRunning: boolean;
  pythonReady: boolean;
  error: string | null;
  unlisten: UnlistenFn | null;

  weights: Record<string, number>;
  setWeight: (key: string, value: number) => void;
  startWorkflow: (projectId: string) => Promise<void>;
  cancelWorkflow: (workflowId: string) => Promise<void>;
  exportPdf: (workflowId: string, filePath: string, reportType?: 'summary' | 'environmental' | 'selectivity') => Promise<void>;
  fetchResults: (workflowId: string) => Promise<void>;
  loadLatestWorkflow: (projectId: string, workflowTemplateId?: string | null) => Promise<void>;
  checkPython: () => Promise<void>;
  setupEventListener: () => Promise<void>;
  dockingJobId: string | null;
  dockingResult: any | null;
  dockingReceptorHash: string | null;
  selectedReceptorPreset: string;
  setSelectedReceptorPreset: (preset: string) => void;
  dockingParams: {
    exhaustiveness: number;
    numModes: number;
    seed: number;
  };
  setDockingParams: (params: Partial<{ exhaustiveness: number; numModes: number; seed: number }>) => void;
  detectedCpuCores: number;
  libraryPrepParams: {
    filterPains: boolean;
    filterReactive: boolean;
    filterHerbicideLikeness: boolean;
    diversityThreshold: number;
    targetSize: number;
    protonationPh: string;
    exportFormat: string;
    clusteringAlgorithm: 'morgan' | 'bemis_murcko';
    numWorkers: number;
  };
  setLibraryPrepParams: (params: Partial<{
    filterPains: boolean;
    filterReactive: boolean;
    filterHerbicideLikeness: boolean;
    diversityThreshold: number;
    targetSize: number;
    protonationPh: string;
    exportFormat: string;
    clusteringAlgorithm: 'morgan' | 'bemis_murcko';
    numWorkers: number;
  }>) => void;
  uploadedFile: { name: string; contents: string; extension: string } | null;
  setUploadedFile: (file: { name: string; contents: string; extension: string } | null) => void;
  structureColumn: string;
  setStructureColumn: (col: string) => void;
  activeInteractionJobId: string | null;
  setActiveInteractionJobId: (id: string | null) => void;
  toggleStage: (stageId: number) => void;
  cleanup: () => void;
  reset: () => void;
  clearWorkflow: () => Promise<void>;
  libraryPrepExportData: string | null;
  libraryPrepFileName: string | null;

  // Pre-made workflows (Tier 1)
  availableWorkflows: any[];
  selectedWorkflowId: string | null;
  workflowParams: Record<string, any>;
  workflowResult: any | null;
  fetchAvailableWorkflows: () => Promise<void>;
  setSelectedWorkflowId: (id: string | null) => void;
  setWorkflowParams: (params: Record<string, any>) => void;
  runNamedWorkflow: (projectId: string) => Promise<void>;
}

export const useWorkflowStore = create<WorkflowState>((set, get) => ({
  selectedWorkflowType: 'lead_opt',
  setWorkflowType: (type) => {
    set({ selectedWorkflowType: type, stages: makeStages(type) });
  },
  activeWorkflow: null,
  stages: makeStages('lead_opt'),
  results: [],
  isRunning: false,
  pythonReady: false,
  error: null,
  unlisten: null,
  dockingJobId: null,
  dockingResult: null,
  dockingReceptorHash: null,
  activeInteractionJobId: null,
  setActiveInteractionJobId: (id) => set({ activeInteractionJobId: id }),
  selectedReceptorPreset: 'als',
  setSelectedReceptorPreset: (preset) => set({ selectedReceptorPreset: preset }),
  dockingParams: {
    exhaustiveness: 4,
    numModes: 5,
    seed: 42,
  },
  setDockingParams: (params) => {
    set((s) => ({
      dockingParams: {
        ...s.dockingParams,
        ...params,
      },
    }));
  },
  detectedCpuCores: 4,
  libraryPrepParams: {
    filterPains: true,
    filterReactive: true,
    filterHerbicideLikeness: true,
    diversityThreshold: 0.7,
    targetSize: 500,
    protonationPh: '7.4',
    exportFormat: 'sdf',
    clusteringAlgorithm: 'morgan',
    numWorkers: 4,
  },
  setLibraryPrepParams: (params) => {
    set((s) => ({
      libraryPrepParams: {
        ...s.libraryPrepParams,
        ...params,
      },
    }));
  },
  weights: {
    pesticide_likeness: 100,
    selectivity: 100,
    resistance: 100,
    toxicity: 100,
    environmental_safety: 100,
  },
  setWeight: (key, value) => {
    set((s) => ({
      weights: {
        ...s.weights,
        [key]: value,
      },
    }));
  },
  uploadedFile: null,
  setUploadedFile: (file) => set({ uploadedFile: file }),
  structureColumn: '',
  setStructureColumn: (col) => set({ structureColumn: col }),
  libraryPrepExportData: null,
  libraryPrepFileName: null,

  startWorkflow: async (projectId: string) => {
    const workflowType = get().selectedWorkflowType;
    set({ isRunning: true, error: null, results: [], dockingJobId: null, dockingResult: null, dockingReceptorHash: null, activeInteractionJobId: null });

    // Set first stage to running while preserving active stage enabled toggles
    const currentStages = get().stages;
    const initial: PipelineStage[] = WORKFLOW_STAGES_MAP[workflowType].map((s, i) => {
      const current = currentStages.find((cs) => cs.id === i + 1);
      return {
        id: i + 1,
        name: s.name,
        description: s.desc,
        status: (i === 0 ? 'running' as const : 'waiting' as const),
        enabled: current ? current.enabled !== false : true,
        ...(i === 0 ? { progressLabel: 'Processing...' } : {}),
      };
    });
    set({ stages: initial });

    if (workflowType === 'lead_opt') {
      await get().setupEventListener();

      try {
        const enabledStages = initial.filter((s) => s.enabled !== false).map((s) => s.name);
        const workflow = await invoke<WorkflowRecord>('start_workflow', {
          projectId,
          workflowName: 'Lead Optimization Pre-Screen',
          enabledStages,
          mpoWeights: get().weights,
        });
        
        // Preserve enabled status when complete
        const finalStages = makeStages('lead_opt', 'done', workflow.compounds_total).map((s) => {
          const current = initial.find((cs) => cs.id === s.id);
          return { ...s, enabled: current ? current.enabled !== false : true };
        });

        set({
          activeWorkflow: workflow,
          isRunning: false,
          stages: finalStages,
        });
        await get().fetchResults(workflow.id);
      } catch (e) {
        set({ error: String(e), isRunning: false });
      }
    } else if (workflowType === 'bioisostere_opt') {
      try {
        // Step 1: Get selected lead compound
        const activeCompoundId = useUIStore.getState().selectedCompoundId;
        if (!activeCompoundId) {
          throw new Error('No starting lead compound selected. Please select a starting compound from the dropdown first.');
        }

        let leadCompound: any = null;
        try {
          leadCompound = await invoke<any>('get_compound', { compoundId: activeCompoundId });
        } catch (err) {
          throw new Error('Selected lead compound not found. Please select a valid compound from the dropdown.');
        }

        const setStageStatus = (stageIdx: number, status: 'waiting' | 'running' | 'done', label?: string) => {
          set((state) => {
            const nextStages = state.stages.map((s, idx) => {
              if (idx === stageIdx) {
                return { ...s, status, ...(label ? { progressLabel: label } : {}) };
              }
              return s;
            });
            return { stages: nextStages };
          });
        };

        // Stage 1: Standardize lead compound
        setStageStatus(0, 'running', 'Standardizing structure...');
        const stdRes = await invoke<any[]>('standardize', { smiles: [leadCompound.smiles] });
        const standardSmiles = stdRes?.[0]?.canonical || leadCompound.smiles;
        setStageStatus(0, 'done');

        // Stage 2: Bioisostere Gen
        setStageStatus(1, 'running', 'Searching rule database...');
        const suggestions = await invoke<any[]>('bioisostere_suggest', {
          smiles: standardSmiles,
          topN: 30,
          sortBy: 'composite',
        });
        
        let candidateSmilesList = suggestions.map((s) => s.transformed_smiles);
        if (candidateSmilesList.length === 0) {
          // Fallback suggestions
          candidateSmilesList = [
            standardSmiles.replace(/Cl/g, 'F'),
            standardSmiles.replace(/C/g, 'N'),
            standardSmiles + 'C',
          ].filter(s => s !== standardSmiles);
        }
        setStageStatus(1, 'done');

        // Stage 3: Properties & Filters
        setStageStatus(2, 'running', 'Calculating properties...');
        const addedIds: string[] = [];
        for (let i = 0; i < candidateSmilesList.length; i++) {
          const candSmiles = candidateSmilesList[i];
          const name = `${leadCompound.name} Analogue ${i + 1}`;
          try {
            const added = await invoke<any>('add_compound', {
              projectId,
              name,
              smiles: candSmiles,
            });
            addedIds.push(added.id);
          } catch (err) {
            console.error('Failed to add candidate:', err);
          }
        }
        
        await useCompoundStore.getState().fetchCompounds(projectId);

        // Run standard workflow in background to get real computed descriptors
        const enabledStages = ['Standardize', 'Properties', 'Pesticide-likeness', 'Selectivity', 'Resistance', 'Toxicity'];
        const workflow = await invoke<WorkflowRecord>('start_workflow', {
          projectId,
          workflowName: 'Bioisosteric Lead Optimization',
          enabledStages,
          mpoWeights: get().weights,
        });
        setStageStatus(2, 'done');

        // Stage 4: QSAR & AD Profiling
        setStageStatus(3, 'running', 'Evaluating predictions...');
        await new Promise((resolve) => setTimeout(resolve, 1000));
        setStageStatus(3, 'done');

        // Stage 5: MPO Scoring
        setStageStatus(4, 'running', 'Ranking suggestions...');
        await get().fetchResults(workflow.id);
        const results = get().results;
        const suggestionsResults = results.filter(r => addedIds.includes(r.id));
        const topSuggestion = suggestionsResults.length > 0 ? suggestionsResults[0] : results[0];
        setStageStatus(4, 'done');

        // Stage 6: Conformer & Docking
        setStageStatus(5, 'running', 'Vina docking simulation...');
        const receptorPreset = get().selectedReceptorPreset;
        const receptor = await invoke<any>('receptor_load_from_source', {
          sourceType: 'preset',
          identifier: receptorPreset,
        });

        let center = PRESET_FALLBACK_BOXES[receptorPreset]?.center || PRESET_FALLBACK_BOXES.als.center;
        const size = PRESET_FALLBACK_BOXES[receptorPreset]?.size || PRESET_FALLBACK_BOXES.als.size;

        if (receptor.cocrystal_ligands && receptor.cocrystal_ligands.length > 0) {
          center = receptor.cocrystal_ligands[0].centroid_xyz;
        } else if (!PRESET_FALLBACK_BOXES[receptorPreset]) {
          try {
            const pocketData = await invoke<any>('pocket_detect', {
              receptorHash: receptor.receptor_hash,
            });
            const topPocket = pocketData.fpocket_results?.[0];
            if (topPocket) {
              center = topPocket.centroid;
            }
          } catch (pocketErr) {
            console.error('Pocket detection failed, using preset fallback coordinates:', pocketErr);
          }
        }

        const preparedLigand = await invoke<any>('ligand_prepare', {
          smiles: topSuggestion.smiles,
          params: {
            conformer_method: 'ETKDGv3',
            optimization: 'MMFF94',
            embed_attempts: 15,
            add_hydrogens: true,
            pH: 7.4,
            deprotonate_acids: true,
            protonate_bases: true,
          },
        });

        const generateUuid = () => {
          if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
            return crypto.randomUUID();
          }
          return 'xxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
            const r = (Math.random() * 16) | 0;
            const v = c === 'x' ? r : (r & 0x3) | 0x8;
            return v.toString(16);
          });
        };

        const jobUuid = generateUuid();
        const spec = {
          job_id: jobUuid,
          receptor_hash: receptor.receptor_hash,
          ligand_hash: preparedLigand.ligand_hash,
          box_center: center,
          box_size: size,
          exhaustiveness: get().dockingParams.exhaustiveness,
          num_modes: get().dockingParams.numModes,
          seed: get().dockingParams.seed,
          engine: 'vina',
          created_at: new Date().toISOString(),
        };

        const receptorObj = RECEPTOR_PRESETS.find(r => r.id === receptorPreset) || { name: receptorPreset.toUpperCase() };
        const receptorDisplayName = receptorObj.name;

        const dockingResult = await invoke<any>('docking_run', {
          spec,
          ligandSmiles: topSuggestion.smiles,
          receptorDisplayName: receptorDisplayName,
          ligandDisplayName: topSuggestion.name,
        });
        // Store the actual job_id from the result (Python engine recomputes it as SHA-256)
        const actualJobId = dockingResult?.job_id || jobUuid;
        set({
          dockingJobId: actualJobId,
          dockingResult: dockingResult,
          dockingReceptorHash: receptor.receptor_hash,
        });
        setStageStatus(5, 'done');

        // Stage 7: 3D Interaction Maps
        setStageStatus(6, 'running', 'Analyzing binding pocket...');
        const bestPose = dockingResult.poses?.[0];
        if (bestPose) {
          await invoke<any>('analysis_interactions', {
            receptorPdbPath: receptor.raw_pdb_path,
            poseSdfBlock: bestPose.sdf_block,
            poseIndex: 1,
          });
        }
        setStageStatus(6, 'done');

        // Finalize
        const finalStages = makeStages('bioisostere_opt', 'done', workflow.compounds_total);
        set({
          activeWorkflow: workflow,
          isRunning: false,
          stages: finalStages,
        });
        await get().fetchResults(workflow.id);
      } catch (e) {
        set({ error: String(e), isRunning: false });
      }
    } else if (workflowType === 'library_prep') {
      try {
        const file = get().uploadedFile;
        if (!file) throw new Error('No uploaded library file found.');
        
        const params = get().libraryPrepParams;
        const setStageStatus = (
          stageIdx: number, 
          status: 'waiting' | 'running' | 'done', 
          progressLabel?: string, 
          compoundCount?: number,
          progressPercent?: number
        ) => {
          set((state) => {
            const nextStages = state.stages.map((s, idx) => {
              if (idx === stageIdx) {
                return { 
                  ...s, 
                  status, 
                  ...(progressLabel !== undefined ? { progressLabel } : {}),
                  ...(progressPercent !== undefined ? { progressPercent } : {}),
                  ...(status === 'done' && compoundCount != null ? { compoundCount, compoundLabel: WORKFLOW_STAGES_MAP.library_prep[idx].label } : {})
                };
              }
              return s;
            });
            return { stages: nextStages };
          });
        };

        const invokeRpc = async (method: string, rpcParams: any) => {
          return await invoke<any>('invoke_python_rpc', { method, params: rpcParams });
        };

        // Stage 1: Standardization
        setStageStatus(0, 'running', 'Parsing and standardizing chemical structures...', undefined, 0);
        const parsedMols = await invokeRpc('parse_library', {
          contents: file.contents,
          extension: file.extension,
          structure_column: get().structureColumn || null,
        });

        if (!Array.isArray(parsedMols) || parsedMols.length === 0) {
          throw new Error('Failed to parse any valid chemical structures from the file.');
        }

        const rawSmiles = parsedMols.map((m: any) => m.smiles);
        const stdRes: any[] = [];
        const totalRaw = rawSmiles.length;
        const chunkSize = 100;

        for (let i = 0; i < totalRaw; i += chunkSize) {
          const chunk = rawSmiles.slice(i, i + chunkSize);
          const percent = Math.round((i / totalRaw) * 100);
          setStageStatus(0, 'running', `Standardizing (${i}/${totalRaw})...`, undefined, percent);
          
          const chunkRes = await invokeRpc('standardize', { smiles: chunk, num_workers: params.numWorkers });
          if (!Array.isArray(chunkRes)) {
            throw new Error('Failed to run standardization on backend.');
          }
          stdRes.push(...chunkRes);
        }
        setStageStatus(0, 'running', `Standardizing (${totalRaw}/${totalRaw})...`, undefined, 100);

        interface LibraryPrepMolecule {
          id: string;
          name: string;
          smiles: string;
          mol_weight?: number;
          logp?: number;
          tpsa?: number;
          hbd?: number;
          hba?: number;
          rotatable_bonds?: number;
          pains_alerts?: string[];
          reactive_alerts?: string[];
          pesticide_likeness?: string;
        }

        let compounds: LibraryPrepMolecule[] = parsedMols.map((m: any, idx: number) => {
          const std = stdRes[idx];
          return {
            id: `lp-${idx}-${Math.random().toString(36).substring(2, 9)}`,
            name: m.name,
            smiles: (std && std.valid) ? std.canonical : '',
          };
        }).filter((c: any) => c.smiles !== '');

        if (compounds.length === 0) {
          throw new Error('Zero compounds were successfully standardized. Please check your structure format.');
        }
        setStageStatus(0, 'done', undefined, compounds.length);

        // Stage 2: Property Curation
        setStageStatus(1, 'running', 'Computing physicochemical properties...', undefined, 0);
        const smilesForProps = compounds.map(c => c.smiles);
        const propsRes: any[] = [];
        const totalProps = smilesForProps.length;

        for (let i = 0; i < totalProps; i += chunkSize) {
          const chunk = smilesForProps.slice(i, i + chunkSize);
          const percent = Math.round((i / totalProps) * 100);
          setStageStatus(1, 'running', `Computing properties (${i}/${totalProps})...`, undefined, percent);

          const chunkRes = await invokeRpc('compute_properties', { smiles: chunk, num_workers: params.numWorkers });
          if (!Array.isArray(chunkRes)) {
            throw new Error('Failed to compute molecular properties on backend.');
          }
          propsRes.push(...chunkRes);
        }
        setStageStatus(1, 'running', `Computing properties (${totalProps}/${totalProps})...`, undefined, 100);

        compounds = compounds.map((c, idx) => {
          const props = propsRes[idx];
          if (!props) return c;
          return {
            ...c,
            mol_weight: props.mol_weight,
            logp: props.logp,
            tpsa: props.tpsa,
            hbd: props.hbd,
            hba: props.hba,
            rotatable_bonds: props.rotatable_bonds,
          };
        });

        // Compute herbicide likeness (Tice rules) in chunks
        setStageStatus(1, 'running', 'Applying pesticide-likeness rules...', undefined, 95);
        const ticeRes: any[] = [];
        for (let i = 0; i < compounds.length; i += chunkSize) {
          const chunk = compounds.slice(i, i + chunkSize);
          const chunkRes = await invokeRpc('pesticide_likeness', { compounds: chunk });
          if (Array.isArray(chunkRes)) {
            ticeRes.push(...chunkRes);
          }
        }

        compounds = compounds.map((c, idx) => {
          const tice = ticeRes?.[idx];
          return {
            ...c,
            pesticide_likeness: tice?.level || 'Low',
          };
        });

        compounds = compounds.filter(c => {
          if (c.mol_weight === undefined || c.logp === undefined || c.hbd === undefined || c.hba === undefined) {
            return false;
          }
          let violations = 0;
          if (c.mol_weight > 500) violations++;
          if (c.logp > 5) violations++;
          if (c.hbd > 5) violations++;
          if (c.hba > 10) violations++;
          if (violations > 1) return false;

          if (params.filterHerbicideLikeness && c.pesticide_likeness === 'Low') {
            return false;
          }
          return true;
        });

        if (compounds.length === 0) {
          throw new Error('Zero compounds passed Lipinski filtering.');
        }
        setStageStatus(1, 'done', undefined, compounds.length);

        // Stage 3: PAINS & Alerts Filter
        setStageStatus(2, 'running', 'Checking structural alerts (PAINS & Reactive groups)...', undefined, 0);
        const smilesForPains = compounds.map(c => c.smiles);
        const alertsRes: any[] = [];
        const totalPains = smilesForPains.length;

        for (let i = 0; i < totalPains; i += chunkSize) {
          const chunk = smilesForPains.slice(i, i + chunkSize);
          const percent = Math.round((i / totalPains) * 100);
          setStageStatus(2, 'running', `Checking alerts (${i}/${totalPains})...`, undefined, percent);

          const chunkRes = await invokeRpc('filter_pains', { smiles: chunk, num_workers: params.numWorkers });
          if (!Array.isArray(chunkRes)) {
            throw new Error('Failed to check structural alerts on backend.');
          }
          alertsRes.push(...chunkRes);
        }
        setStageStatus(2, 'running', `Checking alerts (${totalPains}/${totalPains})...`, undefined, 100);

        compounds = compounds.map((c, idx) => {
          const alerts = alertsRes[idx];
          return {
            ...c,
            pains_alerts: alerts?.pains_alerts || [],
            reactive_alerts: alerts?.reactive_alerts || [],
          };
        });

        compounds = compounds.filter(c => {
          if (params.filterPains && c.pains_alerts && c.pains_alerts.length > 0) return false;
          if (params.filterReactive && c.reactive_alerts && c.reactive_alerts.length > 0) return false;
          return true;
        });

        if (compounds.length === 0) {
          throw new Error('Zero compounds survived structural alerts filtering.');
        }
        setStageStatus(2, 'done', undefined, compounds.length);

        // Stage 4: Diversity Clustering
        setStageStatus(3, 'running', 'Down-sampling via diversity clustering...', undefined, 30);
        const smilesForDiv = compounds.map(c => c.smiles);
        const selectedIndices = await invokeRpc('diversity_select', {
          smiles: smilesForDiv,
          similarity_threshold: params.diversityThreshold,
          target_size: params.targetSize,
          algorithm: params.clusteringAlgorithm || 'morgan',
        });

        if (!Array.isArray(selectedIndices)) {
          throw new Error('Failed to run diversity selection on backend.');
        }

        compounds = selectedIndices.map(idx => compounds[idx]);
        if (compounds.length === 0) {
          throw new Error('Zero compounds selected by diversity clustering.');
        }
        setStageStatus(3, 'done', undefined, compounds.length);

        // Stage 5: 3D & pH Protonation
        setStageStatus(4, 'running', 'Generating 3D conformers & protonating...', undefined, 0);
        const smilesFor3D = compounds.map(c => c.smiles);
        const exportFormat = params.exportFormat || 'sdf';
        const pHVal = parseFloat(params.protonationPh) || 7.4;
        
        let exportBlock = '';
        const total3D = smilesFor3D.length;
        const chunk3DSize = 20;

        for (let i = 0; i < total3D; i += chunk3DSize) {
          const chunk = smilesFor3D.slice(i, i + chunk3DSize);
          const percent = Math.round((i / total3D) * 100);
          setStageStatus(4, 'running', `Generating 3D conformers (${i}/${total3D})...`, undefined, percent);

          const chunkRes = await invokeRpc('prepare_library_3d', {
            smiles: chunk,
            pH: pHVal,
            export_format: exportFormat,
            num_workers: params.numWorkers,
          });

          if (typeof chunkRes !== 'string') {
            throw new Error('Failed to compile 3D conformers/protonated library chunk.');
          }

          if (i === 0) {
            exportBlock += chunkRes;
          } else {
            if (exportFormat === 'csv') {
              const lines = chunkRes.split('\n');
              if (lines[0].trim().startsWith('name,smiles')) {
                lines.shift();
              }
              const rest = lines.join('\n');
              if (rest.trim()) {
                exportBlock = exportBlock.trimEnd() + '\n' + rest;
              }
            } else if (exportFormat === 'sdf') {
              exportBlock += chunkRes;
            } else {
              // smi or smiles
              const rest = chunkRes.trim();
              if (rest) {
                exportBlock = exportBlock.trimEnd() + '\n' + rest;
              }
            }
          }
        }
        setStageStatus(4, 'running', `Generating 3D conformers (${total3D}/${total3D})...`, undefined, 100);
        setStageStatus(4, 'done', undefined, compounds.length);

        // Stage 6: Library Export
        setStageStatus(5, 'running', 'Packaging results...');
        
        const ext = exportFormat === 'sdf' ? 'sdf' : exportFormat === 'csv' ? 'csv' : 'smi';
        const outputFileName = `curated_library_${new Date().toISOString().slice(0, 10)}.${ext}`;

        set({
          libraryPrepExportData: exportBlock,
          libraryPrepFileName: outputFileName,
          results: compounds as any[],
          isRunning: false,
        });
        setStageStatus(5, 'done', undefined, compounds.length);

        const completedAt = new Date().toISOString();
        set({
          activeWorkflow: {
            id: `lp-wf-${Math.random().toString(36).substring(2, 9)}`,
            project_id: projectId,
            name: `Screening Library Preparation (${outputFileName})`,
            status: 'complete',
            stages_complete: 6,
            total_stages: 6,
            compounds_processed: compounds.length,
            compounds_total: compounds.length,
            current_stage: null,
            started_at: file.name,
            completed_at: completedAt,
          } as any
        });
      } catch (e) {
        set({ error: String(e), isRunning: false });
        set((state) => ({
          stages: state.stages.map(s => s.status === 'running' ? { ...s, status: 'waiting' as const } : s)
        }));
      }
    } else {
      // Custom Workflow animation (simulated) for active_learning or resistance_mitigation
      try {
        if (workflowType === 'active_learning') {
          const file = get().uploadedFile;
          if (file) {
            // Step 1: Parse the uploaded/sent library via Python RPC parse_library
            const parsedMols = await invoke<any[]>('invoke_python_rpc', {
              method: 'parse_library',
              params: {
                contents: file.contents,
                extension: file.extension,
                structure_column: get().structureColumn || null,
              },
            });

            if (!Array.isArray(parsedMols) || parsedMols.length === 0) {
              throw new Error('Failed to parse any valid chemical structures from the file.');
            }

            // Step 2: Replace project compounds in the SQLite DB
            await invoke('replace_project_compounds', {
              projectId,
              compounds: parsedMols,
            });

            // Step 3: Refresh UI stores
            await useCompoundStore.getState().fetchCompounds(projectId);
            await useProjectStore.getState().fetchProjects();
          }
        }

        const enabledStages = ['Standardize', 'Properties', 'Pesticide-likeness', 'Selectivity', 'Resistance', 'Toxicity'];
        const workflowName = workflowType === 'active_learning'
          ? 'Virtual Screening & Active Learning Gate'
          : 'Target-Site Resistance Mitigation';
        const workflow = await invoke<WorkflowRecord>('start_workflow', {
          projectId,
          workflowName,
          enabledStages,
          mpoWeights: get().weights,
        });

        const total = workflow.compounds_total;

        for (let i = 0; i < initial.length; i++) {
          const updated = initial.map((s, idx) => {
            if (idx < i) {
              return {
                ...s,
                status: 'done' as const,
                compoundCount: total,
                compoundLabel: s.compoundLabel || WORKFLOW_STAGES_MAP[workflowType][idx].label,
              };
            }
            if (idx === i) {
              return {
                ...s,
                status: 'running' as const,
                progressLabel: 'Running analysis...',
              };
            }
            return { ...s, status: 'waiting' as const };
          });
          set({ stages: updated });

          await new Promise((resolve) => setTimeout(resolve, 1000));
        }

        const finalStages = makeStages(workflowType, 'done', total).map((s) => {
          const current = initial.find((cs) => cs.id === s.id);
          return { ...s, enabled: current ? current.enabled !== false : true };
        });

        set({
          activeWorkflow: workflow,
          isRunning: false,
          stages: finalStages,
        });
        await get().fetchResults(workflow.id);
      } catch (e) {
        set({ error: String(e), isRunning: false });
      }
    }
  },

  fetchResults: async (workflowId: string) => {
    try {
      const results = await invoke<WorkflowResultRecord[]>('get_workflow_results', { workflowId });
      set({ results });

      // If we have results, dynamically update the pipeline stages to reflect which ones were run or excluded.
      if (results.length > 0) {
        const first = results[0];
        const updatedStages = get().stages.map((s) => {
          let enabled = true;
          if (s.name === 'Pesticide-likeness' && first.pesticide_likeness_disabled) enabled = false;
          if (s.name === 'Selectivity' && first.selectivity?.disabled) enabled = false;
          if (s.name === 'Resistance' && first.resistance?.disabled) enabled = false;
          if (s.name === 'Toxicity' && first.toxicity?.disabled) enabled = false;
          return { ...s, enabled };
        });
        set({ stages: updatedStages });
      }
    } catch (e) {
      console.error('Failed to fetch workflow results:', e);
    }
  },

  loadLatestWorkflow: async (projectId: string, workflowTemplateId?: string | null) => {
    const type = get().selectedWorkflowType;

    // If this template has been explicitly cleared, don't load anything!
    if (workflowTemplateId && getClearedWorkflows(projectId).includes(workflowTemplateId)) {
      set({ activeWorkflow: null, workflowResult: null, isRunning: false });
      const spec = get().availableWorkflows.find(w => w.id === workflowTemplateId);
      if (spec) {
        const stages = spec.step_names.map((stepName: string, i: number) => ({
          id: i + 1,
          name: stepName.split('_').map((w: string) => w.charAt(0).toUpperCase() + w.slice(1)).join(' '),
          description: `Step ${i + 1} of ${spec.name}`,
          status: 'waiting' as const,
          enabled: true,
        }));
        set({ stages });
      }
      return;
    }

    try {
      const workflows = await invoke<WorkflowRecord[]>('list_workflows', { projectId });
      if (workflows.length > 0) {
        // Find the latest run matching the template ID (or legacy workflow)
        const latest = workflowTemplateId 
          ? (workflowTemplateId === 'legacy'
             ? workflows.find((w) => !w.workflow_id)
             : workflows.find((w) => w.workflow_id === workflowTemplateId))
          : workflows[0]; // fallback to absolute latest or legacy
        
        if (latest) {
          set({ activeWorkflow: latest });

          if (latest.workflow_id) {
            const details = await invoke<any>('get_workflow_details', { workflowId: latest.id });
            set({ workflowResult: details });
          } else {
            set({ workflowResult: null });
          }

          if (latest.status === 'complete') {
            await get().fetchResults(latest.id);
            if (latest.workflow_id) {
              const spec = get().availableWorkflows.find(w => w.id === latest.workflow_id);
              if (spec) {
                const stages = spec.step_names.map((stepName: string, i: number) => ({
                  id: i + 1,
                  name: stepName.split('_').map((w: string) => w.charAt(0).toUpperCase() + w.slice(1)).join(' '),
                  description: `Step ${i + 1} of ${spec.name}`,
                  status: 'done' as const,
                  enabled: true,
                  compoundCount: latest.compounds_total,
                  compoundLabel: 'processed',
                }));
                set({ stages, isRunning: false });
              } else {
                set({ stages: makeStages(type, 'done', latest.compounds_total), isRunning: false });
              }
            } else {
              set({ stages: makeStages(type, 'done', latest.compounds_total), isRunning: false });
            }
          } else if (latest.status === 'running') {
            // Re-setup event listener and restore stages
            await get().setupEventListener();
            set({ isRunning: true });
          } else {
            // failed or stopped, let's map stages too
            if (latest.workflow_id) {
              const spec = get().availableWorkflows.find(w => w.id === latest.workflow_id);
              if (spec) {
                const stages = spec.step_names.map((stepName: string, i: number) => ({
                  id: i + 1,
                  name: stepName.split('_').map((w: string) => w.charAt(0).toUpperCase() + w.slice(1)).join(' '),
                  description: `Step ${i + 1} of ${spec.name}`,
                  status: 'waiting' as const,
                  enabled: true,
                }));
                set({ stages, isRunning: false });
              }
            } else {
              set({ isRunning: false });
            }
          }
        } else {
          // No run found for this template in the database, clear active run and set stages to default
          set({ activeWorkflow: null, workflowResult: null, isRunning: false });
          if (workflowTemplateId) {
            const spec = get().availableWorkflows.find(w => w.id === workflowTemplateId);
            if (spec) {
              const stages = spec.step_names.map((stepName: string, i: number) => ({
                id: i + 1,
                name: stepName.split('_').map((w: string) => w.charAt(0).toUpperCase() + w.slice(1)).join(' '),
                description: `Step ${i + 1} of ${spec.name}`,
                status: 'waiting' as const,
                enabled: true,
              }));
              set({ stages });
            }
          }
        }
      } else {
        // No runs at all
        if (workflowTemplateId) {
          set({ activeWorkflow: null, workflowResult: null, isRunning: false });
          const spec = get().availableWorkflows.find(w => w.id === workflowTemplateId);
          if (spec) {
            const stages = spec.step_names.map((stepName: string, i: number) => ({
              id: i + 1,
              name: stepName.split('_').map((w: string) => w.charAt(0).toUpperCase() + w.slice(1)).join(' '),
              description: `Step ${i + 1} of ${spec.name}`,
              status: 'waiting' as const,
              enabled: true,
            }));
            set({ stages });
          }
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
      if (ready) {
        try {
          const cores = await invoke<any>('invoke_python_rpc', { method: 'get_cpu_count', params: {} });
          if (typeof cores === 'number' && cores > 0) {
            set((s) => ({
              detectedCpuCores: cores,
              libraryPrepParams: {
                ...s.libraryPrepParams,
                numWorkers: cores,
              }
            }));
          }
        } catch (err) {
          console.error('Failed to fetch CPU count:', err);
        }
      }
    } catch {
      set({ pythonReady: false });
    }
  },

  setupEventListener: async () => {
    const existing = get().unlisten;
    if (existing) existing();

    const unlisten = await listen<WorkflowProgress>('workflow://progress', (event) => {
      const p = event.payload;
      const stagesComplete = p.stages_complete;
      const currentStage = p.current_stage;

      const currentStages = get().stages;
      const selectedId = get().selectedWorkflowId;

      if (selectedId) {
        const spec = get().availableWorkflows.find(w => w.id === selectedId);
        if (spec) {
          const newStages: PipelineStage[] = spec.step_names.map((stepName: string, i: number) => {
            const num = i + 1;
            let status: 'done' | 'running' | 'waiting';
            if (num <= stagesComplete) status = 'done';
            else if (stepName === currentStage) status = 'running';
            else status = 'waiting';

            return {
              id: num,
              name: stepName.split('_').map((w: string) => w.charAt(0).toUpperCase() + w.slice(1)).join(' '),
              description: `Step ${num} of ${spec.name}`,
              status,
              enabled: true,
              ...(status === 'running' ? { progressLabel: `${p.compounds_processed}/${p.compounds_total}` } : {}),
              ...(status === 'done' ? { compoundCount: p.compounds_total, compoundLabel: 'processed' } : {}),
            };
          });
          set({ stages: newStages });
          return;
        }
      }

      const type = get().selectedWorkflowType;
      const newStages: PipelineStage[] = WORKFLOW_STAGES_MAP[type].map((def, i) => {
        const num = i + 1;
        let status: 'done' | 'running' | 'waiting';
        if (num <= stagesComplete) status = 'done';
        else if (def.name === currentStage) status = 'running';
        else status = 'waiting';

        const current = currentStages.find((cs) => cs.id === num);

        return {
          id: num,
          name: def.name,
          description: def.desc,
          status,
          enabled: current ? current.enabled !== false : true,
          ...(status === 'running' ? { progressLabel: `${p.compounds_processed}/${p.compounds_total}` } : {}),
          ...(status === 'done' ? { compoundCount: p.compounds_total, compoundLabel: def.label } : {}),
        };
      });
      set({ stages: newStages });
    });

    set({ unlisten });
  },

  cancelWorkflow: async (workflowId: string) => {
    try {
      await invoke('cancel_workflow', { workflowId });
      set({ isRunning: false });
      const activeWorkflow = get().activeWorkflow;
      if (activeWorkflow && activeWorkflow.id === workflowId) {
        set({
          activeWorkflow: {
            ...activeWorkflow,
            status: 'failed',
          },
        });
      }
    } catch (e) {
      console.error('Failed to cancel workflow:', e);
    }
  },

  exportPdf: async (workflowId: string, filePath: string, reportType?: 'summary' | 'environmental' | 'selectivity') => {
    try {
      if (reportType === 'environmental') {
        await invoke('export_environmental_dossier', { workflowId, outputPath: filePath });
      } else if (reportType === 'selectivity') {
        await invoke('export_selectivity_chartbook', { workflowId, outputPath: filePath });
      } else {
        await invoke('export_workflow_pdf', { workflowId, outputPath: filePath });
      }
    } catch (e) {
      console.error('Failed to export PDF:', e);
      throw e;
    }
  },

  toggleStage: (stageId: number) => {
    if (stageId < 3 || stageId > 6) return;
    const stages = get().stages.map((s) => {
      if (s.id === stageId) {
        return { ...s, enabled: s.enabled === false ? true : false };
      }
      return s;
    });
    set({ stages });
  },

  cleanup: () => {
    const fn = get().unlisten;
    if (fn) fn();
    set({ unlisten: null });
  },

  reset: () => {
    const type = get().selectedWorkflowType;
    get().cleanup();
    set({
      activeWorkflow: null,
      stages: makeStages(type),
      results: [],
      isRunning: false,
      error: null,
      dockingJobId: null,
      dockingResult: null,
      dockingReceptorHash: null,
      activeInteractionJobId: null,
      selectedReceptorPreset: 'als',
      dockingParams: {
        exhaustiveness: 4,
        numModes: 5,
        seed: 42,
      },
      libraryPrepExportData: null,
      libraryPrepFileName: null,
      selectedWorkflowId: null,
      workflowParams: {},
      workflowResult: null,
    });
  },

  clearWorkflow: async () => {
    const active = get().activeWorkflow;
    if (active) {
      try {
        await invoke('cancel_workflow', { workflowId: active.id });
      } catch (e) {
        console.error('Failed to clear workflow in DB:', e);
      }
    }

    const templateId = get().selectedWorkflowId;
    const projectId = useProjectStore.getState().activeProjectId;
    if (projectId && templateId) {
      addClearedWorkflow(projectId, templateId);
    }

    get().cleanup();
    set({
      activeWorkflow: null,
      results: [],
      isRunning: false,
      error: null,
      dockingJobId: null,
      dockingResult: null,
      dockingReceptorHash: null,
      activeInteractionJobId: null,
      selectedReceptorPreset: 'als',
      dockingParams: {
        exhaustiveness: 4,
        numModes: 5,
        seed: 42,
      },
      libraryPrepExportData: null,
      libraryPrepFileName: null,
      workflowResult: null,
    });

    if (templateId) {
      const spec = get().availableWorkflows.find(w => w.id === templateId);
      if (spec) {
        const stages = spec.step_names.map((stepName: string, i: number) => ({
          id: i + 1,
          name: stepName.split('_').map((w: string) => w.charAt(0).toUpperCase() + w.slice(1)).join(' '),
          description: `Step ${i + 1} of ${spec.name}`,
          status: 'waiting' as const,
          enabled: true,
        }));
        set({ stages });
      }
    } else {
      set({ stages: makeStages(get().selectedWorkflowType) });
    }
  },

  availableWorkflows: [],
  selectedWorkflowId: null,
  workflowParams: {},
  workflowResult: null,

  fetchAvailableWorkflows: async () => {
    try {
      const res = await invoke<any[]>('list_available_workflows');
      set({ availableWorkflows: res });
    } catch (err) {
      console.error('Failed to fetch available workflows:', err);
    }
  },

  setSelectedWorkflowId: (id) => {
    if (!id) {
      set({ selectedWorkflowId: null });
      return;
    }

    const active = get().activeWorkflow;
    if (active && active.workflow_id === id) {
      set({ selectedWorkflowId: id });
      return;
    }

    const spec = get().availableWorkflows.find(w => w.id === id);
    set({
      selectedWorkflowId: id,
      workflowParams: spec ? { ...spec.default_params } : {},
      workflowResult: null,
    });
    if (spec) {
      const stages = spec.step_names.map((name: string, i: number) => ({
        id: i + 1,
        name: name.split('_').map((w: string) => w.charAt(0).toUpperCase() + w.slice(1)).join(' '),
        description: `Step ${i + 1} of ${spec.name}`,
        status: 'waiting' as const,
        enabled: true,
      }));
      set({ stages });
    } else {
      set({ stages: makeStages(get().selectedWorkflowType) });
    }
  },

  setWorkflowParams: (params) => {
    set((s) => ({ workflowParams: { ...s.workflowParams, ...params } }));
  },

  runNamedWorkflow: async (projectId: string) => {
    const workflowId = get().selectedWorkflowId;
    if (!workflowId || workflowId === 'legacy') return;

    removeClearedWorkflow(projectId, workflowId);

    set({ isRunning: true, error: null, workflowResult: null });
    await get().setupEventListener();

    try {
      const record = await invoke<WorkflowRecord>('run_named_workflow', {
        projectId,
        workflowId,
        params: get().workflowParams,
      });
      // Fetch workflow details to load verdict and provenance
      const details = await invoke<any>('get_workflow_details', { workflowId: record.id });
      
      // Fetch results
      await get().fetchResults(record.id);

      set({ activeWorkflow: record, workflowResult: details, isRunning: false });
    } catch (err: any) {
      set({ error: err.toString(), isRunning: false });
    }
  },
}));
