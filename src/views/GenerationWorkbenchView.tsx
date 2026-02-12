import { useEffect, useState, useMemo } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { useUIStore } from '../store/uiStore';
import { useCompoundStore } from '../store/compoundStore';
import { useProjectStore } from '../store/projectStore';
import type { GenerationCompound, GenerationJobHistoryEntry } from '../types';
import { EmptyState } from '../components/shared/EmptyState';
import { ContextualHelp } from '../components/shared/ContextualHelp';
import { ProgressIndicator } from '../components/shared/ProgressIndicator';
import { ReactionEnumPanel } from '../components/design/ReactionEnumPanel';
import { useDesignStore } from '../store/designStore';
import { MmpTransformTable } from '../components/sar/MmpTransformTable';
import { FreeWilsonPanel } from '../components/sar/FreeWilsonPanel';
import { useSarStore } from '../store/sarStore';
import { TmapCanvas } from '../components/cartography/TmapCanvas';
import { useCartographyStore } from '../store/cartographyStore';
import { ShapeScreeningPanel } from '../components/shape/ShapeScreeningPanel';
import { ActiveLearningPanel } from '../components/al/ActiveLearningPanel';

import { 
  Play, 
  Trash2, 
  Activity, 
  Sliders, 
  Plus, 
  AlertTriangle,
  Info,
  ExternalLink,
  FolderOpen
} from 'lucide-react';

interface ReceptorPreset {
  id: string;
  name: string;
  pdbId: string;
  target: string;
  description: string;
}

const RECEPTOR_PRESETS: ReceptorPreset[] = [
  { id: 'als', name: 'ALS (Acetolactate Synthase)', pdbId: '1YBH', target: 'Herbicides (Sulfonylureas)', description: 'Target enzyme for ALS-inhibiting herbicides. Evaluates ALS-triazolopyrimidine/sulfonylurea binding pockets.' },
  { id: 'epsps', name: 'EPSPS (Shikimate Synthase)', pdbId: '2AAY', target: 'Herbicides (Glyphosate)', description: 'Sole target for glyphosate, blocking aromatic amino acid synthesis. Essential for evaluating shikimate pathway disruption fits.' },
  { id: 'hppd', name: 'HPPD (Dioxygenase)', pdbId: '1TFZ', target: 'Herbicides (Triketones)', description: 'Carotenoid bleaching target. Evaluates pocket binding for triketones (mesotrione, sulcotrione) and isoxazoles.' },
  { id: 'gs', name: 'GS (Glutamine Synthetase)', pdbId: '2O2A', target: 'Herbicides (Glufosinate)', description: 'Sole target for glufosinate, interrupting nitrogen assimilation. Essential for analyzing ammonium toxicity fits.' },
  { id: 'accase', name: 'ACCase (Acetyl-CoA Carboxylase)', pdbId: '1UYR', target: 'Herbicides (Fops & Dims)', description: 'Key lipid synthesis enzyme. Evaluates carboxyltransferase domain fits for aryloxyphenoxypropionates (fops) and cyclohexanediones (dims).' },
  { id: 'ppo', name: 'PPO (Protoporphyrinogen Oxidase)', pdbId: '1SEZ', target: 'Herbicides (Diphenyl Ethers)', description: 'Crucial target for PPO-inhibiting herbicides. Essential for studying diphenyl ether lipid peroxidation fits.' },
  { id: 'ps2', name: 'PSII (Photosystem II)', pdbId: '1FEV', target: 'Herbicides (Triazines)', description: 'Core photosynthetic electron-transport complex. Evaluates triazine and urea herbicide pocket binding.' },
  { id: 'sdh', name: 'SDH (Succinate Dehydrogenase)', pdbId: '2FBW', target: 'Fungicides (SDHIs)', description: 'Mitochondrial complex II respiratory target. Vital for carboxamide fungicide binding analysis.' },
];

function MoleculeDepict({ smiles, size = 120 }: { smiles: string; size?: number }) {
  const [svg, setSvg] = useState<string | null>(null);

  useEffect(() => {
    invoke<string>('depict_compound', { smiles, width: size, height: size - 20 })
      .then(setSvg)
      .catch((err) => console.error('Failed to depict compound:', err));
  }, [smiles, size]);

  if (!svg) {
    return (
      <div style={{ 
        width: size, 
        height: size - 20, 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center', 
        color: '#64748b', 
        fontSize: '11px',
        border: '1px dashed #e2e8f0',
        borderRadius: '6px',
        background: '#f8fafc' 
      }}>
        Loading...
      </div>
    );
  }

  return (
    <div 
      dangerouslySetInnerHTML={{ __html: svg }} 
      style={{ width: size, height: size - 20, display: 'flex', justifyContent: 'center', alignItems: 'center' }} 
    />
  );
}

export function GenerationWorkbenchView() {
  const activeProjectId = useProjectStore((s) => s.activeProjectId);
  const activeCompoundId = useUIStore((s) => s.selectedCompoundId);
  const exportedSmiles = useUIStore((s) => s.exportedSmiles);
  const libraryCompounds = useCompoundStore((s) => s.compounds);
  const fetchCompounds = useCompoundStore((s) => s.fetchCompounds);

  const activeCompoundSmiles = useMemo(() => {
    if (exportedSmiles) return exportedSmiles;
    const comp = libraryCompounds.find((c) => c.id === activeCompoundId);
    return comp ? comp.smiles : '';
  }, [activeCompoundId, exportedSmiles, libraryCompounds]);

  // State Variables
  const [activeTab, setActiveTab] = useState<'crem' | 'cremdock' | 'easydock' | 'crempharm'>('cremdock');
  const [jobName, setJobName] = useState('');
  const [parentSmiles, setParentSmiles] = useState('');
  const [selectedPresetId, setSelectedPresetId] = useState('als');
  
  // Docking box coordinates
  const [boxCenterX, setBoxCenterX] = useState(0.0);
  const [boxCenterY, setBoxCenterY] = useState(0.0);
  const [boxCenterZ, setBoxCenterZ] = useState(0.0);
  const [boxSizeX, setBoxSizeX] = useState(20.0);
  const [boxSizeY, setBoxSizeY] = useState(20.0);
  const [boxSizeZ, setBoxSizeZ] = useState(20.0);
  
  // Docking parameters
  const [dockingEngine, setDockingEngine] = useState<'vina' | 'gnina'>('vina');
  const [nIterations, setNIterations] = useState(3);
  const [populationSize, setPopulationSize] = useState(20);
  const [keepTopN, setKeepTopN] = useState(5);
  
  // CReM specific
  const [cremRadius, setCremRadius] = useState(2);
  const [cremMinSize, setCremMinSize] = useState(1);
  const [cremMaxSize, setCremMaxSize] = useState(5);
  const [cremMaxMutants, setCremMaxMutants] = useState(50);

  // EasyDock specific
  const [easyDockSmilesArea, setEasyDockSmilesArea] = useState('');

  // MPO Weights (0-100 sliders)
  const [weightPesticide, setWeightPesticide] = useState(100);
  const [weightSelectivity, setWeightSelectivity] = useState(100);
  const [weightResistance, setWeightResistance] = useState(100);
  const [weightToxicity, setWeightToxicity] = useState(100);
  const [weightEnvSafety, setWeightEnvSafety] = useState(100);

  // Pipeline Status & Results
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationProgress, setGenerationProgress] = useState(0);
  const [errorText, setErrorText] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  
  const [generationResults, setGenerationResults] = useState<GenerationCompound[]>([]);
  const [selectedMutant, setSelectedMutant] = useState<GenerationCompound | null>(null);
  const [historyJobs, setHistoryJobs] = useState<GenerationJobHistoryEntry[]>([]);
  const [loadedJobId, setLoadedJobId] = useState<string | null>(null);

  // Default job name generation
  useEffect(() => {
    if (!jobName) {
      const modeLabel = activeTab === 'cremdock' ? 'CReM-dock' : activeTab === 'crem' ? 'CReM Mutation' : 'EasyDock Batch';
      setJobName(`${modeLabel} - ${new Date().toLocaleDateString()} ${new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}`);
    }
  }, [activeTab, jobName]);

  // Sync active compound from Inspector or right-click export
  useEffect(() => {
    if (activeCompoundSmiles) {
      setParentSmiles(activeCompoundSmiles);
    }
  }, [activeCompoundSmiles]);

  // Load history jobs on mount
  const refreshHistory = async () => {
    try {
      const list = await invoke<GenerationJobHistoryEntry[]>('generation_history_list');
      setHistoryJobs(list);
    } catch (e) {
      console.error('Failed to load generation history:', e);
    }
  };

  useEffect(() => {
    refreshHistory();
  }, []);

  // Web socket listener for docking/generation progress
  useEffect(() => {
    const unlisten = listen<any>('docking://progress', (event) => {
      if (isGenerating && event.payload) {
        setGenerationProgress(event.payload.percent || 0);
      }
    });
    return () => {
      unlisten.then(f => f());
    };
  }, [isGenerating]);

  // Grab parent smiles from active compound in library/inspector
  const handlePullFromInspector = () => {
    if (activeCompoundSmiles) {
      setParentSmiles(activeCompoundSmiles);
      setErrorText(null);
    } else {
      setErrorText('No active compound selected in Inspector.');
    }
  };

  // Convert sliders to MPO weights dict
  const getNormalizedWeights = () => {
    return {
      pesticide_likeness: weightPesticide,
      selectivity: weightSelectivity,
      resistance: weightResistance,
      toxicity: weightToxicity,
      environmental_safety: weightEnvSafety,
    };
  };

  // Run the de novo generation pipeline
  const handleRunGeneration = async () => {
    setErrorText(null);
    setSuccessMessage(null);
    
    if (activeTab === 'easydock' && !easyDockSmilesArea.trim()) {
      setErrorText('Please provide one or more ligand SMILES for batch docking.');
      return;
    }
    
    if (activeTab !== 'easydock' && !parentSmiles.trim()) {
      setErrorText('Please specify a parent seed molecule SMILES.');
      return;
    }

    setIsGenerating(true);
    setGenerationProgress(0);
    setGenerationResults([]);
    setSelectedMutant(null);

    const boxCenter = [boxCenterX, boxCenterY, boxCenterZ];
    const boxSize = [boxSizeX, boxSizeY, boxSizeZ];
    const weightsApplied = getNormalizedWeights();

    try {
      let receptor = null;
      if (activeTab === 'cremdock' || activeTab === 'easydock') {
        // First load the prepared receptor from preset
        receptor = await invoke<any>('receptor_load_from_source', {
          sourceType: 'preset',
          identifier: selectedPresetId
        });
      }

      if (activeTab === 'crem') {
        // Plain CReM mutation (no docking)
        const mutants = await invoke<any[]>('crem_generate', {
          smiles: parentSmiles,
          radius: cremRadius,
          minSize: cremMinSize,
          maxSize: cremMaxSize,
          maxMutants: cremMaxMutants
        });
        
        // Mock properties / score locally since no docking was performed
        const processed: GenerationCompound[] = mutants.map((m: any) => ({
          smiles: m.mutant_smiles,
          docking_score: 0.0,
          generation: 1,
          parent_in_generation: parentSmiles,
          predicted_properties: {},
          composite_score: m.similarity_to_parent * 10.0,
          mpo_score: m.similarity_to_parent * 10.0,
          rank_category: 'Candidate'
        }));
        
        setGenerationResults(processed);
        if (processed.length > 0) setSelectedMutant(processed[0]);
        setSuccessMessage(`Successfully generated ${processed.length} CReM mutations.`);
      } 
      else if (activeTab === 'cremdock') {
        // Closed-loop de novo design
        const result = await invoke<any>('crem_dock_run', {
          jobName,
          parentSmiles,
          receptorHash: receptor.receptor_hash,
          receptorDisplayName: RECEPTOR_PRESETS.find(p => p.id === selectedPresetId)?.name || 'Receptor',
          boxCenter,
          boxSize,
          nIterations,
          populationSize,
          keepTopN,
          weights: weightsApplied
        });

        const best = result.best_compounds || [];
        setGenerationResults(best);
        if (best.length > 0) setSelectedMutant(best[0]);
        setSuccessMessage(`De novo design completed. Simulated ${result.total_compounds_generated} mutations, docked ${result.total_compounds_docked} candidates.`);
      } 
      else if (activeTab === 'easydock') {
        // EasyDock batch virtual screening
        const parsedSmiles = easyDockSmilesArea
          .split(/[\n,;]+/)
          .map(s => s.trim())
          .filter(Boolean);

        const results = await invoke<any[]>('easydock_dock', {
          jobName,
          receptorHash: receptor.receptor_hash,
          receptorDisplayName: RECEPTOR_PRESETS.find(p => p.id === selectedPresetId)?.name || 'Receptor',
          smiles: parsedSmiles,
          boxCenter,
          boxSize,
          engineName: dockingEngine
        });

        const mapped: GenerationCompound[] = results.map(r => ({
          smiles: r.smiles,
          docking_score: r.docking_score,
          generation: 1,
          parent_in_generation: 'N/A',
          predicted_properties: r.poses && r.poses.length > 0 ? r.poses[0].predicted_properties || {} : {},
          composite_score: r.docking_score !== 0 ? -1.5 * r.docking_score : 0.0,
          mpo_score: 0.0,
          rank_category: 'Candidate'
        }));

        setGenerationResults(mapped);
        if (mapped.length > 0) setSelectedMutant(mapped[0]);
        setSuccessMessage(`Batch docking completed. Screened ${results.length} ligands.`);
      }
      
      setJobName(''); // Reset for next job
      refreshHistory();
    } catch (e: any) {
      console.error(e);
      setErrorText(`Execution failed: ${e.message || e}`);
    } finally {
      setIsGenerating(false);
      setGenerationProgress(0);
    }
  };

  // Load a job from SQLite history
  const handleLoadJob = async (jobId: string) => {
    setErrorText(null);
    setSuccessMessage(null);
    setLoading(true);
    try {
      const job = await invoke<any>('generation_history_load', { jobId });
      setLoadedJobId(jobId);
      
      const mode = job.mode;
      const params = job.parameters || {};
      
      if (mode === 'CReM-dock') {
        setActiveTab('cremdock');
        setParentSmiles(job.parent_smiles || '');
        setSelectedPresetId(params.receptor_hash || 'als');
        if (params.box_center) {
          setBoxCenterX(params.box_center[0]);
          setBoxCenterY(params.box_center[1]);
          setBoxCenterZ(params.box_center[2]);
        }
        if (params.box_size) {
          setBoxSizeX(params.box_size[0]);
          setBoxSizeY(params.box_size[1]);
          setBoxSizeZ(params.box_size[2]);
        }
        setNIterations(params.n_iterations || 3);
        setPopulationSize(params.population_size || 20);
        setKeepTopN(params.keep_top_n || 5);
        
        const weights = params.weights || {};
        setWeightPesticide(weights.pesticide_likeness ?? 100);
        setWeightSelectivity(weights.selectivity ?? 100);
        setWeightResistance(weights.resistance ?? 100);
        setWeightToxicity(weights.toxicity ?? 100);
        setWeightEnvSafety(weights.environmental_safety ?? 100);

        const best = job.results?.best_compounds || [];
        setGenerationResults(best);
        if (best.length > 0) setSelectedMutant(best[0]);
      } 
      else if (mode === 'EasyDock Batch') {
        setActiveTab('easydock');
        setSelectedPresetId(params.receptor_hash || 'als');
        setDockingEngine(params.engine || 'vina');
        
        const results = job.results || [];
        const mapped: GenerationCompound[] = results.map((r: any) => ({
          smiles: r.smiles,
          docking_score: r.docking_score,
          generation: 1,
          parent_in_generation: 'N/A',
          predicted_properties: r.poses && r.poses.length > 0 ? r.poses[0].predicted_properties || {} : {},
          composite_score: r.docking_score !== 0 ? -1.5 * r.docking_score : 0.0,
          mpo_score: 0.0,
          rank_category: 'Candidate'
        }));
        
        setGenerationResults(mapped);
        if (mapped.length > 0) setSelectedMutant(mapped[0]);
      } 
      else {
        setActiveTab('crem');
        setParentSmiles(job.parent_smiles || '');
        setCremRadius(params.radius || 2);
        setCremMinSize(params.min_size || 1);
        setCremMaxSize(params.max_size || 5);
        setCremMaxMutants(params.max_mutants || 50);

        const results = job.results || [];
        setGenerationResults(results);
        if (results.length > 0) setSelectedMutant(results[0]);
      }

      setSuccessMessage(`Loaded job: ${job.name}`);
    } catch (e: any) {
      console.error(e);
      setErrorText(`Failed to load job: ${e.message || e}`);
    } finally {
      setLoading(false);
    }
  };

  // Delete a job from SQLite history
  const handleDeleteJob = async (e: React.MouseEvent, jobId: string) => {
    e.stopPropagation();
    if (!confirm('Are you sure you want to delete this job record?')) return;
    try {
      await invoke('generation_history_delete', { jobId });
      if (loadedJobId === jobId) {
        setLoadedJobId(null);
        setGenerationResults([]);
        setSelectedMutant(null);
      }
      refreshHistory();
    } catch (e: any) {
      console.error(e);
      setErrorText(`Delete failed: ${e.message || e}`);
    }
  };

  // Add the selected mutant analog to the active project library
  const handleAddToLibrary = async (compound: GenerationCompound) => {
    if (!activeProjectId) {
      setErrorText('No active project found. Select/create a project first.');
      return;
    }
    try {
      await invoke('add_compound', {
        projectId: activeProjectId,
        name: `Mutant Analog (${compound.rank_category})`,
        smiles: compound.smiles
      });
      setSuccessMessage('Analog successfully added to your project library!');
      await fetchCompounds(activeProjectId);
    } catch (e: any) {
      console.error(e);
      setErrorText(`Failed to add compound: ${e.message || e}`);
    }
  };

  const [, setLoading] = useState(false);

  return (
    <main className="main-content generation-workbench-layout" style={{ display: 'grid', gridTemplateColumns: '260px 1fr', height: '100%', background: 'var(--color-bg, #f5f5f0)', color: 'var(--color-text-900, #1a1a1a)' }}>
      
      {/* 1. History Sidebar */}
      <aside style={{ borderRight: '0.5px solid var(--color-border, #e5e5e0)', background: 'var(--color-surface, #ffffff)', padding: '16px', display: 'flex', flexDirection: 'column', gap: '16px', overflowY: 'auto' }}>
        <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-500, #7a7a7a)', letterSpacing: '0.05em' }}>DESIGN RUNS HISTORY</div>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {historyJobs.length === 0 ? (
            <div style={{ color: 'var(--color-text-400, #a0a0a0)', fontSize: '12px', textAlign: 'center', padding: '20px 0' }}>No design jobs saved yet.</div>
          ) : (
            historyJobs.map((job) => (
              <div 
                key={job.job_id} 
                onClick={() => handleLoadJob(job.job_id)}
                style={{ 
                  padding: '10px', 
                  borderRadius: '6px', 
                  background: loadedJobId === job.job_id ? 'var(--color-brand-50, #f4f8f0)' : 'var(--color-surface, #ffffff)', 
                  border: loadedJobId === job.job_id ? '0.5px solid var(--color-brand-400, #a6c98f)' : '0.5px solid var(--color-border, #e5e5e0)', 
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start'
                }}
              >
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', maxWidth: '80%' }}>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-900, #1a1a1a)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{job.name}</div>
                  <div style={{ fontSize: '11px', color: 'var(--color-text-500, #5a5a5a)' }}>{job.mode}</div>
                  <div style={{ fontSize: '10px', color: 'var(--color-text-400, #7a7a7a)' }}>{new Date(job.completed_at).toLocaleDateString()}</div>
                </div>
                <button 
                  onClick={(e) => handleDeleteJob(e, job.job_id)} 
                  style={{ background: 'none', border: 'none', color: 'var(--color-text-400, #7a7a7a)', cursor: 'pointer', padding: '4px', borderRadius: '4px' }}
                  onMouseEnter={(e) => e.currentTarget.style.color = '#ef4444'}
                  onMouseLeave={(e) => e.currentTarget.style.color = 'var(--color-text-400, #7a7a7a)'}
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))
          )}
        </div>
      </aside>

      {/* 2. Main Workbench Workspace */}
      <section style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px', overflowY: 'auto' }}>
        
        {/* Header */}
        <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h1 style={{ fontSize: '24px', fontWeight: 700, letterSpacing: '-0.02em', background: 'linear-gradient(to right, #2563eb, #3b82f6)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', margin: 0 }}>De Novo Design Workbench</h1>
            <p style={{ fontSize: '13px', color: 'var(--color-text-500, #5a5a5a)', margin: '4px 0 0 0' }}>Build, screen, and rank pesticide/drug candidates using closed-loop chemical evolution.</p>
          </div>
        </header>

        {/* Global Warnings / Messages */}
        {errorText && (
          <div style={{ padding: '12px 16px', background: '#fef2f2', border: '0.5px solid #fee2e2', borderRadius: '6px', color: '#b91c1c', display: 'flex', alignItems: 'center', gap: '10px', fontSize: '13px' }}>
            <AlertTriangle size={16} />
            <span>{errorText}</span>
          </div>
        )}

        {successMessage && (
          <div style={{ padding: '12px 16px', background: '#f0fdf4', border: '0.5px solid #dcfce7', borderRadius: '6px', color: '#166534', display: 'flex', alignItems: 'center', gap: '10px', fontSize: '13px' }}>
            <Info size={16} />
            <span>{successMessage}</span>
          </div>
        )}

        {/* Combinatorial Reaction Enumeration Mode */}
        {useDesignStore((s) => s.workbenchMode) === 'reaction' && (
          <ReactionEnumPanel coreSmiles={parentSmiles} />
        )}

        {/* Matched Molecular Pairs & Free-Wilson SAR Analysis Panel */}
        <div className="card" style={{ background: 'var(--color-surface)', border: '0.5px solid var(--color-border)', borderRadius: '8px', padding: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--color-text-900)' }}>
              Matched Pairs & Free-Wilson SAR Analysis
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                onClick={async () => {
                  const items = generationResults.map((r, i) => ({ id: String(i), smiles: r.smiles, potency: r.composite_score || 7.0, off_target: r.docking_score ? Math.abs(r.docking_score) : 4.0 }));
                  await useSarStore.getState().suggestSelectivityTransforms(items);
                }}
                disabled={generationResults.length === 0}
                style={{ padding: '4px 10px', fontSize: '11px', borderRadius: '6px', border: 'none', background: 'var(--color-brand-600)', color: 'white', fontWeight: 600, cursor: 'pointer', opacity: generationResults.length === 0 ? 0.5 : 1 }}
              >
                Analyze Library MMPs
              </button>
              <button
                onClick={async () => {
                  const items = generationResults.map((r, i) => ({ id: String(i), smiles: r.smiles, potency: r.composite_score || 7.0 }));
                  await useSarStore.getState().fitFreeWilson(items, 'potency');
                }}
                disabled={generationResults.length === 0}
                style={{ padding: '4px 10px', fontSize: '11px', borderRadius: '6px', border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-text-800)', fontWeight: 600, cursor: 'pointer', opacity: generationResults.length === 0 ? 0.5 : 1 }}
              >
                Fit Free-Wilson SAR Model
              </button>
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <MmpTransformTable transforms={useSarStore((s) => s.transforms)} />
            <FreeWilsonPanel result={useSarStore((s) => s.freeWilsonResult)} />
          </div>
        </div>

        {/* TMAP Chemical Space Cartography Card */}
        <div className="card" style={{ background: 'var(--color-surface)', border: '0.5px solid var(--color-border)', borderRadius: '8px', padding: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--color-text-900)' }}>
              Chemical-Space Cartography (TMAP &bull; LSH Minimum Spanning Tree)
            </div>
            <button
              onClick={async () => {
                const items = generationResults.map((r, i) => ({ id: String(i), smiles: r.smiles, composite_score: r.composite_score }));
                await useCartographyStore.getState().computeTmapLayout(items);
              }}
              disabled={generationResults.length === 0}
              style={{ padding: '4px 12px', fontSize: '11px', borderRadius: '6px', border: 'none', background: 'var(--color-brand-600)', color: 'white', fontWeight: 600, cursor: 'pointer', opacity: generationResults.length === 0 ? 0.5 : 1 }}
            >
              Compute TMAP Layout
            </button>
          </div>
          <TmapCanvas layout={useCartographyStore((s) => s.currentLayout)} />
        </div>

        {/* 3D Shape & Electrostatic Similarity Screening Card */}
        <ShapeScreeningPanel
          candidates={generationResults.map((r, i) => ({ id: String(i), smiles: r.smiles }))}
          defaultReference={parentSmiles}
        />

        {/* Bayesian-Optimization Active-Learning Loop Card */}
        <ActiveLearningPanel
          labeledPool={useCompoundStore.getState().compounds.map((c) => ({ id: c.id, smiles: c.smiles, potency: c.scores?.composite_score || 7.0 }))}
          candidatePool={generationResults.map((r, i) => ({ id: String(i), smiles: r.smiles }))}
        />

        {/* Main Interface Panels Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
          
          {/* Mode Configuration Card */}
          <div className="card" style={{ background: 'var(--color-surface, #ffffff)', border: '0.5px solid var(--color-border, #e5e5e0)', borderRadius: '8px', overflow: 'hidden' }}>
            
            {/* Tabs Selector */}
            <div style={{ display: 'flex', borderBottom: '0.5px solid var(--color-border, #e5e5e0)', background: 'var(--color-bg, #f5f5f0)' }}>
              <button 
                onClick={() => { setActiveTab('cremdock'); setErrorText(null); }}
                style={{ padding: '12px 16px', flex: 1, border: 'none', background: activeTab === 'cremdock' ? 'var(--color-surface, #ffffff)' : 'transparent', color: activeTab === 'cremdock' ? 'var(--color-brand-600, #3b6d11)' : 'var(--color-text-500, #64748b)', fontWeight: 600, fontSize: '12px', borderBottom: activeTab === 'cremdock' ? '2px solid var(--color-brand-600, #3b6d11)' : 'none', cursor: 'pointer' }}
              >
                CReM-dock
              </button>
              <button 
                onClick={() => { setActiveTab('crem'); setErrorText(null); }}
                style={{ padding: '12px 16px', flex: 1, border: 'none', background: activeTab === 'crem' ? 'var(--color-surface, #ffffff)' : 'transparent', color: activeTab === 'crem' ? 'var(--color-brand-600, #3b6d11)' : 'var(--color-text-500, #64748b)', fontWeight: 600, fontSize: '12px', borderBottom: activeTab === 'crem' ? '2px solid var(--color-brand-600, #3b6d11)' : 'none', cursor: 'pointer' }}
              >
                CReM Mutation
              </button>
              <button 
                onClick={() => { setActiveTab('easydock'); setErrorText(null); }}
                style={{ padding: '12px 16px', flex: 1, border: 'none', background: activeTab === 'easydock' ? 'var(--color-surface, #ffffff)' : 'transparent', color: activeTab === 'easydock' ? 'var(--color-brand-600, #3b6d11)' : 'var(--color-text-500, #64748b)', fontWeight: 600, fontSize: '12px', borderBottom: activeTab === 'easydock' ? '2px solid var(--color-brand-600, #3b6d11)' : 'none', cursor: 'pointer' }}
              >
                EasyDock Batch
              </button>
              <button 
                onClick={() => { useDesignStore.getState().setWorkbenchMode(useDesignStore.getState().workbenchMode === 'reaction' ? 'crem' : 'reaction'); }}
                style={{ padding: '12px 16px', flex: 1, border: 'none', background: useDesignStore((s) => s.workbenchMode) === 'reaction' ? 'var(--color-surface, #ffffff)' : 'transparent', color: useDesignStore((s) => s.workbenchMode) === 'reaction' ? 'var(--color-brand-600, #3b6d11)' : 'var(--color-text-500, #64748b)', fontWeight: 600, fontSize: '12px', borderBottom: useDesignStore((s) => s.workbenchMode) === 'reaction' ? '2px solid var(--color-brand-600, #3b6d11)' : 'none', cursor: 'pointer' }}
              >
                Enumerate Reactions
              </button>
            </div>

            <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              
              {/* Job settings name */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label style={{ fontSize: '11px', color: 'var(--color-text-500, #7a7a7a)', fontWeight: 600 }}>DESIGN JOB NAME</label>
                <input 
                  type="text" 
                  value={jobName} 
                  onChange={(e) => setJobName(e.target.value)}
                  style={{ padding: '8px 12px', borderRadius: '6px', background: 'var(--color-surface, #ffffff)', border: '0.5px solid var(--color-border, #e5e5e0)', color: 'var(--color-text-900, #1a1a1a)', fontSize: '13px' }}
                />
              </div>

              {/* Tab specific options */}
              {activeTab === 'crempharm' && (
                <div style={{ padding: '12px', background: '#fffbeb', border: '1px solid #fef3c7', color: '#b45309', fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <div style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <AlertTriangle size={14} /> 
                    GPLv3 Copyleft Restriction
                    <ContextualHelp topicId="crem.pharm" />
                  </div>
                  <div>CReM-pharm (pharmacophore-guided mutations) is licensed under GPLv3. To comply with commercial licensing regulations, it is excluded from Edeon's default binary. Install it locally and configure the path in settings to unlock.</div>
                </div>
              )}

              {/* Seed structure input */}
              {activeTab !== 'easydock' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <label style={{ fontSize: '11px', color: 'var(--color-text-500, #7a7a7a)', fontWeight: 600 }}>PARENT SEED SMILES</label>
                    <button 
                      onClick={handlePullFromInspector}
                      style={{ border: 'none', background: 'none', color: '#3b82f6', fontSize: '11px', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}
                    >
                      <ExternalLink size={12} /> Pull active compound
                    </button>
                  </div>
                  <input 
                    type="text" 
                    value={parentSmiles} 
                    onChange={(e) => setParentSmiles(e.target.value)}
                    placeholder="c1ccccc1..."
                    style={{ padding: '8px 12px', borderRadius: '6px', background: 'var(--color-surface, #ffffff)', border: '0.5px solid var(--color-border, #e5e5e0)', color: 'var(--color-text-900, #1a1a1a)', fontSize: '13px' }}
                  />
                  {parentSmiles ? (
                    <div style={{ display: 'flex', justifyContent: 'center', padding: '10px', background: 'var(--color-bg, #f5f5f0)', borderRadius: '6px', border: '0.5px solid var(--color-border, #e5e5e0)' }}>
                      <MoleculeDepict smiles={parentSmiles} size={150} />
                    </div>
                  ) : (
                    <div style={{ display: 'flex', justifyContent: 'center', padding: '10px' }}>
                      <EmptyState
                        icon={<FolderOpen size={16} />}
                        title="No parent smiles selected"
                        description="Select a compound in the library or pull the active inspector compound."
                        primaryAction={{
                          label: "Pull from Inspector",
                          onClick: handlePullFromInspector
                        }}
                      />
                    </div>
                  )}
                </div>
              )}

              {/* Receptor target selector (CReM-dock & EasyDock) */}
              {(activeTab === 'cremdock' || activeTab === 'easydock') && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <label style={{ fontSize: '11px', color: 'var(--color-text-500, #7a7a7a)', fontWeight: 600 }}>TARGET RECEPTOR PROTEIN</label>
                  <select 
                    value={selectedPresetId} 
                    onChange={(e) => setSelectedPresetId(e.target.value)}
                    style={{ padding: '8px 12px', borderRadius: '6px', background: 'var(--color-surface, #ffffff)', border: '0.5px solid var(--color-border, #e5e5e0)', color: 'var(--color-text-900, #1a1a1a)', fontSize: '13px', width: '100%' }}
                  >
                    {RECEPTOR_PRESETS.map((p) => (
                      <option key={p.id} value={p.id}>{p.name} ({p.pdbId})</option>
                    ))}
                  </select>
                  <div style={{ fontSize: '11px', color: 'var(--color-text-500, #5a5a5a)', marginTop: '2px' }}>
                    {RECEPTOR_PRESETS.find(p => p.id === selectedPresetId)?.description}
                  </div>
                </div>
              )}

              {/* Custom Batch list input (EasyDock) */}
              {activeTab === 'easydock' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <label style={{ fontSize: '11px', color: 'var(--color-text-500, #7a7a7a)', fontWeight: 600 }}>LIGAND BATCH SMILES (Comma or Newline separated)</label>
                  <textarea 
                    value={easyDockSmilesArea}
                    onChange={(e) => setEasyDockSmilesArea(e.target.value)}
                    placeholder="Cc1ccccc1&#10;c1ccccc1&#10;Clc1ccccc1"
                    rows={4}
                    style={{ padding: '8px 12px', borderRadius: '6px', background: 'var(--color-surface, #ffffff)', border: '0.5px solid var(--color-border, #e5e5e0)', color: 'var(--color-text-900, #1a1a1a)', fontSize: '13px', fontFamily: 'monospace', resize: 'vertical' }}
                  />
                </div>
              )}

              {/* Crem core specific sizing parameter inputs */}
              {activeTab === 'crem' && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <label style={{ fontSize: '11px', color: 'var(--color-text-500, #7a7a7a)', fontWeight: 600 }}>MUTATION RADIUS</label>
                    <input type="number" min={1} max={5} value={cremRadius} onChange={e => setCremRadius(parseInt(e.target.value))} style={{ padding: '8px 12px', borderRadius: '6px', background: 'var(--color-surface, #ffffff)', border: '0.5px solid var(--color-border, #e5e5e0)', color: 'var(--color-text-900, #1a1a1a)', fontSize: '13px' }} />
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <label style={{ fontSize: '11px', color: 'var(--color-text-500, #7a7a7a)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}>
                      MAX MUTANTS
                      <ContextualHelp topicId="generation.mutations" />
                    </label>
                    <input type="number" min={5} max={500} value={cremMaxMutants} onChange={e => setCremMaxMutants(parseInt(e.target.value))} style={{ padding: '8px 12px', borderRadius: '6px', background: 'var(--color-surface, #ffffff)', border: '0.5px solid var(--color-border, #e5e5e0)', color: 'var(--color-text-900, #1a1a1a)', fontSize: '13px' }} />
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <label style={{ fontSize: '11px', color: 'var(--color-text-500, #7a7a7a)', fontWeight: 600 }}>MIN HEAVY ATOMS SIZE</label>
                    <input type="number" min={1} max={10} value={cremMinSize} onChange={e => setCremMinSize(parseInt(e.target.value))} style={{ padding: '8px 12px', borderRadius: '6px', background: 'var(--color-surface, #ffffff)', border: '0.5px solid var(--color-border, #e5e5e0)', color: 'var(--color-text-900, #1a1a1a)', fontSize: '13px' }} />
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <label style={{ fontSize: '11px', color: 'var(--color-text-500, #7a7a7a)', fontWeight: 600 }}>MAX HEAVY ATOMS SIZE</label>
                    <input type="number" min={1} max={25} value={cremMaxSize} onChange={e => setCremMaxSize(parseInt(e.target.value))} style={{ padding: '8px 12px', borderRadius: '6px', background: 'var(--color-surface, #ffffff)', border: '0.5px solid var(--color-border, #e5e5e0)', color: 'var(--color-text-900, #1a1a1a)', fontSize: '13px' }} />
                  </div>
                </div>
              )}

              {/* Evolutionary configuration parameters (CReM-dock) */}
              {activeTab === 'cremdock' && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <label style={{ fontSize: '11px', color: 'var(--color-text-500, #7a7a7a)', fontWeight: 600 }}>GENERATIONS (ITERATIONS)</label>
                    <input type="number" min={1} max={5} value={nIterations} onChange={e => setNIterations(parseInt(e.target.value))} style={{ padding: '8px 12px', borderRadius: '6px', background: 'var(--color-surface, #ffffff)', border: '0.5px solid var(--color-border, #e5e5e0)', color: 'var(--color-text-900, #1a1a1a)', fontSize: '13px' }} />
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <label style={{ fontSize: '11px', color: 'var(--color-text-500, #7a7a7a)', fontWeight: 600 }}>POOL SIZE / GEN</label>
                    <input type="number" min={5} max={100} value={populationSize} onChange={e => setPopulationSize(parseInt(e.target.value))} style={{ padding: '8px 12px', borderRadius: '6px', background: 'var(--color-surface, #ffffff)', border: '0.5px solid var(--color-border, #e5e5e0)', color: 'var(--color-text-900, #1a1a1a)', fontSize: '13px' }} />
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <label style={{ fontSize: '11px', color: 'var(--color-text-500, #7a7a7a)', fontWeight: 600 }}>SEEDS KEPT / GEN</label>
                    <input type="number" min={1} max={25} value={keepTopN} onChange={e => setKeepTopN(parseInt(e.target.value))} style={{ padding: '8px 12px', borderRadius: '6px', background: 'var(--color-surface, #ffffff)', border: '0.5px solid var(--color-border, #e5e5e0)', color: 'var(--color-text-900, #1a1a1a)', fontSize: '13px' }} />
                  </div>
                </div>
              )}

              {/* Run Trigger */}
              <button 
                onClick={handleRunGeneration}
                disabled={isGenerating || activeTab === 'crempharm'}
                style={{ 
                  marginTop: '10px', 
                  padding: '12px', 
                  borderRadius: '6px', 
                  background: activeTab === 'crempharm' ? 'var(--color-border, #e5e5e0)' : 'linear-gradient(to right, #2563eb, #3b82f6)', 
                  color: '#ffffff', 
                  fontWeight: 600, 
                  fontSize: '13px', 
                  border: 'none', 
                  cursor: isGenerating || activeTab === 'crempharm' ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center',
                  gap: '8px',
                  boxShadow: '0 4px 14px 0 rgba(59, 130, 246, 0.3)'
                }}
              >
                <Play size={14} fill="#ffffff" />
                {isGenerating ? 'Simulating Design Pipeline...' : 'Execute Design Job'}
              </button>
            </div>
          </div>

          {/* MPO Score Weight Customizer Slider Panel (For CReM-dock) */}
          <div className="card" style={{ background: 'var(--color-surface, #ffffff)', border: '0.5px solid var(--color-border, #e5e5e0)', padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Sliders size={16} style={{ color: 'var(--color-brand-600, #3b6d11)' }} />
              <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-500, #7a7a7a)', letterSpacing: '0.05em', display: 'flex', alignItems: 'center', gap: '4px' }}>
                MPO SAFETY MULTI-PARAMETER OPTIMIZATION WEIGHTS
                <ContextualHelp topicId="generation.mpo" />
              </div>
            </div>

            <p style={{ fontSize: '12px', color: 'var(--color-text-500, #64748b)', margin: 0 }}>Configure the relative optimization weights below. Edeon will penalize analogs with bad safety/toxicity scores in the closed-loop selection round.</p>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '10px' }}>
              
              {/* Pesticide-likeness */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', fontWeight: 600 }}>
                  <span style={{ color: 'var(--color-text-800, #3a3a3a)' }}>Pesticide Likeness (Tice Rules)</span>
                  <span style={{ color: 'var(--color-brand-600, #3b6d11)' }}>{weightPesticide}%</span>
                </div>
                <input type="range" min={0} max={100} value={weightPesticide} onChange={e => setWeightPesticide(parseInt(e.target.value))} style={{ width: '100%', height: '5px', background: 'var(--color-border, #e5e5e0)', outline: 'none', borderRadius: '3px' }} />
              </div>

              {/* Selectivity */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', fontWeight: 600 }}>
                  <span style={{ color: 'var(--color-text-800, #3a3a3a)' }}>Cross-species Selectivity (Apis / Fish safety margin)</span>
                  <span style={{ color: 'var(--color-brand-600, #3b6d11)' }}>{weightSelectivity}%</span>
                </div>
                <input type="range" min={0} max={100} value={weightSelectivity} onChange={e => setWeightSelectivity(parseInt(e.target.value))} style={{ width: '100%', height: '5px', background: 'var(--color-border, #e5e5e0)', outline: 'none', borderRadius: '3px' }} />
              </div>

              {/* Resistance */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', fontWeight: 600 }}>
                  <span style={{ color: 'var(--color-text-800, #3a3a3a)' }}>Resistance Evasion Risk (target mutation binding resistance)</span>
                  <span style={{ color: 'var(--color-brand-600, #3b6d11)' }}>{weightResistance}%</span>
                </div>
                <input type="range" min={0} max={100} value={weightResistance} onChange={e => setWeightResistance(parseInt(e.target.value))} style={{ width: '100%', height: '5px', background: 'var(--color-border, #e5e5e0)', outline: 'none', borderRadius: '3px' }} />
              </div>

              {/* Toxicity */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', fontWeight: 600 }}>
                  <span style={{ color: 'var(--color-text-800, #3a3a3a)' }}>Inspected Toxicity Profile (Rat acute oral LD50 / Sensitisation)</span>
                  <span style={{ color: 'var(--color-brand-600, #3b6d11)' }}>{weightToxicity}%</span>
                </div>
                <input type="range" min={0} max={100} value={weightToxicity} onChange={e => setWeightToxicity(parseInt(e.target.value))} style={{ width: '100%', height: '5px', background: 'var(--color-border, #e5e5e0)', outline: 'none', borderRadius: '3px' }} />
              </div>

              {/* Env fate safety */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', fontWeight: 600 }}>
                  <span style={{ color: 'var(--color-text-800, #3a3a3a)' }}>Environmental Fate (Soil persistence DT50 / Leaching GUS)</span>
                  <span style={{ color: 'var(--color-brand-600, #3b6d11)' }}>{weightEnvSafety}%</span>
                </div>
                <input type="range" min={0} max={100} value={weightEnvSafety} onChange={e => setWeightEnvSafety(parseInt(e.target.value))} style={{ width: '100%', height: '5px', background: 'var(--color-border, #e5e5e0)', outline: 'none', borderRadius: '3px' }} />
              </div>

            </div>
          </div>
        </div>

        {/* 3. Progress Streaming loader bar */}
        {isGenerating && (
          <div className="card" style={{ background: 'var(--color-surface, #ffffff)', border: '0.5px solid var(--color-border, #e5e5e0)', borderRadius: '8px', padding: '20px' }}>
            <ProgressIndicator
              variant="determinate"
              value={generationProgress}
              label="Running Closed-loop Generative Screening..."
              cancelable={false}
            />
          </div>
        )}

        {/* 4. Results Grid Table & Selected Compound detail */}
        {generationResults.length > 0 ? (
          <div style={{ display: 'grid', gridTemplateColumns: '3fr 2fr', gap: '20px', minHeight: '400px' }}>
            
            {/* Results Table list */}
            <div className="card" style={{ background: 'var(--color-surface, #ffffff)', border: '0.5px solid var(--color-border, #e5e5e0)', borderRadius: '8px', padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px', overflow: 'hidden' }}>
              <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-500, #7a7a7a)', letterSpacing: '0.05em' }}>GENERATED CANDIDATE ANALOGS ({generationResults.length})</div>
              
              <div style={{ overflowX: 'auto', width: '100%', maxHeight: '420px', overflowY: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                  <thead>
                    <tr style={{ borderBottom: '0.5px solid var(--color-border, #e5e5e0)', color: 'var(--color-text-500, #7a7a7a)' }}>
                      <th style={{ padding: '10px 8px' }}>Candidate (SMILES)</th>
                      <th style={{ padding: '10px 8px' }}>Composite Score</th>
                      <th style={{ padding: '10px 8px' }}>Docking Score</th>
                      <th style={{ padding: '10px 8px' }}>MPO Safety</th>
                      <th style={{ padding: '10px 8px' }}>Rank</th>
                    </tr>
                  </thead>
                  <tbody>
                    {generationResults.map((c, idx) => (
                      <tr 
                        key={idx} 
                        onClick={() => setSelectedMutant(c)}
                        style={{ 
                          borderBottom: '0.5px solid var(--color-border, #e5e5e0)', 
                          background: selectedMutant?.smiles === c.smiles ? 'var(--color-brand-50, #f4f8f0)' : 'transparent',
                          cursor: 'pointer',
                          transition: 'all 0.1s' 
                        }}
                        onMouseEnter={(e) => { if (selectedMutant?.smiles !== c.smiles) e.currentTarget.style.background = 'var(--color-bg, #f5f5f0)'; }}
                        onMouseLeave={(e) => { if (selectedMutant?.smiles !== c.smiles) e.currentTarget.style.background = 'transparent'; }}
                      >
                        <td style={{ padding: '10px 8px', maxWidth: '200px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontFamily: 'monospace' }}>{c.smiles}</td>
                        <td style={{ padding: '10px 8px', fontWeight: 600, color: 'var(--color-brand-600, #3b6d11)' }}>{c.composite_score}</td>
                        <td style={{ padding: '10px 8px', color: c.docking_score < 0 ? '#10b981' : 'var(--color-text-600, #5a5a5a)' }}>{c.docking_score !== 0 ? `${c.docking_score} kcal` : 'N/A'}</td>
                        <td style={{ padding: '10px 8px', color: 'var(--color-text-900, #1a1a1a)' }}>{c.mpo_score > 0 ? `${c.mpo_score}/10` : 'N/A'}</td>
                        <td style={{ padding: '10px 8px' }}>
                          <span style={{ 
                            padding: '2px 6px', 
                            borderRadius: '4px', 
                            fontSize: '11px', 
                            fontWeight: 600, 
                            background: c.rank_category === 'Lead' ? '#dcfce7' : c.rank_category === 'Candidate' ? '#dbeafe' : '#fee2e2', 
                            color: c.rank_category === 'Lead' ? '#166534' : c.rank_category === 'Candidate' ? '#1e40af' : '#991b1b' 
                          }}>
                            {c.rank_category}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Selected compound side-by-side detail comparison card */}
            {selectedMutant && (
              <div className="card" style={{ background: 'var(--color-surface, #ffffff)', border: '0.5px solid var(--color-border, #e5e5e0)', borderRadius: '8px', padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '0.5px solid var(--color-border, #e5e5e0)', paddingBottom: '10px' }}>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-800, #3a3a3a)' }}>MUTANT COMPARISON DETAIL</div>
                  <button 
                    onClick={() => handleAddToLibrary(selectedMutant)}
                    style={{ padding: '6px 12px', borderRadius: '4px', background: '#10b981', color: '#ffffff', fontWeight: 600, fontSize: '11px', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}
                  >
                    <Plus size={12} /> Add to Project Library
                  </button>
                </div>

                {/* Side-by-side molecular structure depictions */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', textAlign: 'center' }}>
                  <div style={{ background: 'var(--color-bg, #f5f5f0)', padding: '10px', borderRadius: '6px', border: '0.5px solid var(--color-border, #e5e5e0)' }}>
                    <div style={{ fontSize: '10px', color: 'var(--color-text-500, #5a5a5a)', marginBottom: '6px' }}>PARENT SEED</div>
                    <MoleculeDepict smiles={parentSmiles || selectedMutant.parent_in_generation} size={130} />
                  </div>
                  <div style={{ background: 'var(--color-bg, #f5f5f0)', padding: '10px', borderRadius: '6px', border: '0.5px solid var(--color-border, #e5e5e0)' }}>
                    <div style={{ fontSize: '10px', color: '#10b981', marginBottom: '6px' }}>MUTATED ANALOG</div>
                    <MoleculeDepict smiles={selectedMutant.smiles} size={130} />
                  </div>
                </div>

                {/* Side-by-side metrics */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  
                  {/* Composite Score Row */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '0.5px solid var(--color-border, #e5e5e0)' }}>
                    <span style={{ fontSize: '12px', color: 'var(--color-text-500, #5a5a5a)' }}>Composite Lead Rank:</span>
                    <span style={{ fontSize: '14px', fontWeight: 700, color: 'var(--color-brand-600, #3b6d11)' }}>{selectedMutant.composite_score}</span>
                  </div>

                  {/* Docking Score Row */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '0.5px solid var(--color-border, #e5e5e0)' }}>
                    <span style={{ fontSize: '12px', color: 'var(--color-text-500, #5a5a5a)' }}>Docking Affinity:</span>
                    <span style={{ fontSize: '13px', fontWeight: 600, color: selectedMutant.docking_score < 0 ? '#10b981' : 'var(--color-text-900, #1a1a1a)' }}>
                      {selectedMutant.docking_score !== 0 ? `${selectedMutant.docking_score} kcal/mol` : 'N/A'}
                    </span>
                  </div>

                  {/* MPO Score Row */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '0.5px solid var(--color-border, #e5e5e0)' }}>
                    <span style={{ fontSize: '12px', color: 'var(--color-text-500, #5a5a5a)' }}>MPO Safety Rating:</span>
                    <span style={{ fontSize: '13px', fontWeight: 600, color: selectedMutant.mpo_score >= 7.0 ? '#10b981' : selectedMutant.mpo_score >= 4.5 ? '#f59e0b' : '#ef4444' }}>
                      {selectedMutant.mpo_score > 0 ? `${selectedMutant.mpo_score} / 10` : 'N/A'}
                    </span>
                  </div>

                  {/* Detailed QSAR endpoints properties profiles comparison */}
                  <div style={{ marginTop: '10px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--color-text-500, #7a7a7a)', fontWeight: 600, marginBottom: '6px' }}>Tox/Fate Property Delta Profiles</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '160px', overflowY: 'auto' }}>
                      
                      {Object.keys(selectedMutant.predicted_properties).length === 0 ? (
                        <div style={{ fontSize: '11px', color: 'var(--color-text-400, #a0a0a0)', textAlign: 'center', padding: '10px' }}>Property profiles unavailable for simple CReM mode.</div>
                      ) : (
                        Object.entries(selectedMutant.predicted_properties).map(([epName, predVal]: [string, any]) => {
                          const valStr = predVal?.value?.numeric !== undefined 
                             ? predVal.value.numeric.toFixed(2) 
                             : predVal?.value?.categorical || predVal?.value?.binary?.toString() || 'N/A';
                          const units = predVal?.units || '';
                          
                          return (
                            <div key={epName} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--color-bg, #f5f5f0)', padding: '6px 8px', borderRadius: '4px' }}>
                              <span style={{ fontSize: '11px', color: 'var(--color-text-800, #3a3a3a)', textTransform: 'capitalize' }}>{epName.replace(/_/g, ' ')}</span>
                              <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-900, #1a1a1a)' }}>{valStr} {units}</span>
                            </div>
                          );
                        })
                      )}

                    </div>
                  </div>

                </div>
              </div>
            )}
          </div>
        ) : (
          !isGenerating && (
            <div style={{ marginTop: '10px' }}>
              <EmptyState
                icon={<Activity size={20} />}
                title="No Generative Run Results"
                description="Configure the seed structures, target receptor, and MPO safety weights above, then click 'Execute Design Job' to simulate chemical evolution, or select a previous design run from the sidebar history."
              />
            </div>
          )
        )}

      </section>
    </main>
  );
}
