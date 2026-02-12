import { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { useUIStore } from '../store/uiStore';
import { useCompoundStore } from '../store/compoundStore';
import { open as openFileDialog } from '@tauri-apps/plugin-dialog';

// NGL is UMD, resolve cleanly
import NglModule from 'ngl';
import * as NGL from 'ngl';

function resolveNgl(): any {
  const candidates = [
    NglModule,
    (NglModule as any)?.default,
    NGL,
    (NGL as any)?.default,
    (globalThis as any).NGL,
    (window as any).NGL,
  ];
  for (const c of candidates) {
    if (c && typeof c.Stage === 'function') return c;
  }
  return null;
}

const NglObj: any = resolveNgl();

import { 
  Rotate3d, 
  Camera, 
  RefreshCw, 
  Info,
  X,
  Trash2,
  Star,
  Compass,
  AlertTriangle,
  ChevronDown
} from 'lucide-react';
import { EmptyState } from '../components/shared/EmptyState';
import { ContextualHelp } from '../components/shared/ContextualHelp';
import { ProgressIndicator } from '../components/shared/ProgressIndicator';

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

export function DockingWorkbenchView() {
  const activeCompoundId = useUIStore((s) => s.selectedCompoundId);
  const theme = useUIStore((s) => s.theme);
  const libraryCompounds = useCompoundStore((s) => s.compounds);

  // Active workspace compound
  const workspaceCompound = useMemo(() => {
    return libraryCompounds.find((c) => c.id === activeCompoundId) || null;
  }, [activeCompoundId, libraryCompounds]);

  // NGL references
  const viewportRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<any>(null);
  const receptorComponentRef = useRef<any>(null);
  const ligandComponentRef = useRef<any>(null);
  const boxComponentRef = useRef<any>(null);
  const pocketHighlightComponentRef = useRef<any>(null);

  // Core state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pocketLabels, setPocketLabels] = useState<{ id: string; text: string; x: number; y: number; z: number }[]>([]);

  // Receptor State
  const [selectedPresetId, setSelectedPresetId] = useState('als');
  const [pdbCodeInput, setPdbCodeInput] = useState('');
  const [afUniprotInput, setAfUniprotInput] = useState('');
  const [preparedReceptor, setPreparedReceptor] = useState<any>(null);
  const [hetList, setHetList] = useState<any[]>([]);
  const [customHetActions, setCustomHetActions] = useState<Record<string, string>>({});
  const [keepWater, setKeepWater] = useState(false);
  const [keepIons, setKeepIons] = useState(false);
  const [keepCofactors, setKeepCofactors] = useState(true);
  const [keepCocrystalLigands] = useState(false);
  const [repreparing, setRepreparing] = useState(false);

  // Pocket State
  const [pocketMode, setPocketMode] = useState<'cocrystal' | 'fpocket' | 'residues' | 'manual'>('cocrystal');
  const [fpocketResults, setFpocketResults] = useState<any[]>([]);
  const [selectedPocketId, setSelectedPocketId] = useState<number | null>(null);
  const [detectingPockets, setDetectingPockets] = useState(false);

  // Grid Box Coordinates
  const [boxCenterX, setBoxCenterX] = useState(0.0);
  const [boxCenterY, setBoxCenterY] = useState(0.0);
  const [boxCenterZ, setBoxCenterZ] = useState(0.0);
  const [boxSizeX, setBoxSizeX] = useState(20.0);
  const [boxSizeY, setBoxSizeY] = useState(20.0);
  const [boxSizeZ, setBoxSizeZ] = useState(20.0);
  const [linkSizes, setLinkSizes] = useState(false);

  // Ligand State
  const [ligandSource, setLigandSource] = useState<'workspace' | 'smiles' | 'upload'>('workspace');
  const [customSmiles, setCustomSmiles] = useState('');
  const [preparedLigand, setPreparedLigand] = useState<any>(null);
  const [preparingLigand, setPreparingLigand] = useState(false);
  const [ligandDisplayName, setLigandDisplayName] = useState('');

  // Upload/Local file state
  const [uploadedFileName, setUploadedFileName] = useState('');
  const [fileMols, setFileMols] = useState<any[]>([]);
  const [selectedFileMolIdx, setSelectedFileMolIdx] = useState<number>(0);

  // Docking Control
  const [exhaustiveness, setExhaustiveness] = useState<number>(8);
  const [numModes, setNumModes] = useState<number>(9);
  const [dockingEngine, setDockingEngine] = useState<'vina' | 'gnina'>('vina');
  const [isDocking, setIsDocking] = useState(false);
  const [dockingProgress, setDockingProgress] = useState(0);
  const [dockingJobId, setDockingJobId] = useState<string | null>(null);
  const [dockingResult, setDockingResult] = useState<any>(null);
  const [selectedPoseIndex, setSelectedPoseIndex] = useState<number | null>(null);
  const [interactionFingerprint, setInteractionFingerprint] = useState<any>(null);
  const [loadingInteractions, setLoadingInteractions] = useState(false);

  // Distance Tool
  const [measureMode, setMeasureMode] = useState(false);
  const [selectedAtoms, setSelectedAtoms] = useState<string[]>([]);
  const [measuredDistances, setMeasuredDistances] = useState<Array<{ id: string; a1: string; a2: string; value: number }>>([]);

  // Pose Clustering State
  const [clusterMode, setClusterMode] = useState(false);
  const [poseClusters, setPoseClusters] = useState<number[][]>([]);
  const [rmsdCutoff, setRmsdCutoff] = useState<number>(2.0);

  // Job History
  const [historyOpen, setHistoryOpen] = useState(false);
  const [jobHistory, setJobHistory] = useState<any[]>([]);
  const [historySearch, setHistorySearch] = useState('');
  const [historyStarredOnly, setHistoryStarredOnly] = useState(false);

  // View Settings
  const [isSpinning, setIsSpinning] = useState(false);
  const [cameraType, setCameraType] = useState<'perspective' | 'orthographic'>('perspective');
  const [bgColor, setBgColor] = useState<'white' | 'pale-grey' | 'black'>('pale-grey');
  const [representation, setRepresentation] = useState<'cartoon' | 'surface' | 'sticks'>('cartoon');

  // Scoring details modal / tooltip state
  const [showScoreInterpretation, setShowScoreInterpretation] = useState(false);

  // Helper: Draw 3D wireframe box
  const drawBox = useCallback((cx: number, cy: number, cz: number, sx: number, sy: number, sz: number) => {
    if (!stageRef.current || !NglObj) return;

    if (boxComponentRef.current) {
      try {
        stageRef.current.removeComponent(boxComponentRef.current);
      } catch (e) {
        console.warn('Failed to remove box component', e);
      }
      boxComponentRef.current = null;
    }

    const shape = new NglObj.Shape('grid-box');
    const hx = sx / 2;
    const hy = sy / 2;
    const hz = sz / 2;

    const corners = [
      [cx - hx, cy - hy, cz - hz],
      [cx + hx, cy - hy, cz - hz],
      [cx + hx, cy + hy, cz - hz],
      [cx - hx, cy + hy, cz - hz],
      [cx - hx, cy - hy, cz + hz],
      [cx + hx, cy - hy, cz + hz],
      [cx + hx, cy + hy, cz + hz],
      [cx - hx, cy + hy, cz + hz],
    ];

    const edges = [
      [0, 1], [1, 2], [2, 3], [3, 0], // bottom
      [4, 5], [5, 6], [6, 7], [7, 4], // top
      [0, 4], [1, 5], [2, 6], [3, 7]  // pillars
    ];

    const color = [0.2, 0.4, 0.9];
    const radius = 0.12;

    edges.forEach(([i, j]) => {
      shape.addCylinder(corners[i], corners[j], color, radius);
    });

    const shapeComp = stageRef.current.addComponentFromObject(shape);
    if (shapeComp) {
      shapeComp.addRepresentation('buffer', { opacity: 0.7 });
      boxComponentRef.current = shapeComp;
    }
  }, []);

  // Update box rendering when coordinates shift
  useEffect(() => {
    drawBox(boxCenterX, boxCenterY, boxCenterZ, boxSizeX, boxSizeY, boxSizeZ);
  }, [boxCenterX, boxCenterY, boxCenterZ, boxSizeX, boxSizeY, boxSizeZ, drawBox]);

  // Handle Resize and Init Stage
  useEffect(() => {
    if (!viewportRef.current || !NglObj) return;

    let stage: any;
    let cancelled = false;

    const raf = requestAnimationFrame(() => {
      if (cancelled || !viewportRef.current) return;
      try {
        if (stageRef.current) {
          try { stageRef.current.dispose(); } catch (e) {}
        }
        const initialTheme = useUIStore.getState().theme;
        stage = new NglObj.Stage(viewportRef.current, {
          backgroundColor: initialTheme === 'dark' ? '#09090b' : '#f1f5f9',
          tooltip: true
        });
        stageRef.current = stage;
        
        // Auto-load ALS preset initially
        loadReceptor('preset', 'als');
      } catch (e: any) {
        setError(`Failed to initialize NGL stage: ${e.message || e}`);
      }
    });

    const handleResize = () => {
      if (stageRef.current) {
        stageRef.current.handleResize();
      }
    };
    window.addEventListener('resize', handleResize);

    const observer = new ResizeObserver(() => {
      if (stageRef.current) {
        stageRef.current.handleResize();
      }
    });
    observer.observe(viewportRef.current);

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', handleResize);
      observer.disconnect();
      if (stageRef.current) {
        stageRef.current.dispose();
        stageRef.current = null;
      }
    };
  }, []);

  // Sync stage settings
  useEffect(() => {
    if (!stageRef.current) return;
    stageRef.current.setSpin(isSpinning);
  }, [isSpinning]);

  useEffect(() => {
    if (!stageRef.current) return;
    stageRef.current.setParameters({ cameraType });
  }, [cameraType]);

  useEffect(() => {
    if (!stageRef.current) return;
    const colorHex = bgColor === 'white' ? '#ffffff' : bgColor === 'pale-grey' ? (theme === 'dark' ? '#09090b' : '#f1f5f9') : '#000000';
    stageRef.current.setParameters({ backgroundColor: colorHex });
  }, [bgColor, theme]);

  // Sync progress bar
  useEffect(() => {
    const unlisten = listen<any>('docking://progress', (event) => {
      if (isDocking && event.payload) {
        setDockingProgress(event.payload.percent || 0);
      }
    });
    return () => {
      unlisten.then(f => f());
    };
  }, [isDocking]);

  // Synchronize HTML overlay labels with WebGL camera
  useEffect(() => {
    let animId: number;
    let active = true;

    const updateLabelPositions = () => {
      if (!active) return;

      const stage = stageRef.current;
      const viewport = viewportRef.current;

      if (stage && stage.viewer && viewport && NglObj && pocketLabels.length > 0) {
        const camera = stage.viewer.camera;
        const width = viewport.clientWidth;
        const height = viewport.clientHeight;

        pocketLabels.forEach((lbl) => {
          const el = document.getElementById(`ngl-label-${lbl.id}`);
          if (!el) return;

          // Project 3D coordinates to Normalized Device Coordinates (NDC)
          const pos = new NglObj.Vector3(lbl.x, lbl.y, lbl.z);
          pos.project(camera);

          // Check if coordinate is behind camera near plane or beyond far plane
          if (pos.z > 1 || pos.z < -1) {
            el.style.display = 'none';
          } else {
            // Convert NDC (-1 to 1) to viewport CSS coordinates (px)
            const left = (pos.x * 0.5 + 0.5) * width;
            const top = (-(pos.y * 0.5) + 0.5) * height;

            el.style.left = `${left}px`;
            el.style.top = `${top}px`;
            el.style.display = 'block';
          }
        });
      }

      animId = requestAnimationFrame(updateLabelPositions);
    };

    if (pocketLabels.length > 0) {
      animId = requestAnimationFrame(updateLabelPositions);
    }

    return () => {
      active = false;
      cancelAnimationFrame(animId);
    };
  }, [pocketLabels]);

  // Auto-fill ligand name when source changes
  useEffect(() => {
    if (ligandSource === 'workspace' && workspaceCompound) {
      setLigandDisplayName(workspaceCompound.name);
      setCustomSmiles(workspaceCompound.smiles);
    } else if (ligandSource === 'smiles') {
      setLigandDisplayName('Custom Smiles');
    } else if (ligandSource === 'upload' && fileMols.length > 0 && fileMols[selectedFileMolIdx]) {
      setLigandDisplayName(fileMols[selectedFileMolIdx].name || `Compound ${selectedFileMolIdx + 1}`);
    }
  }, [ligandSource, workspaceCompound, fileMols, selectedFileMolIdx]);

  // Execute docking pose clustering
  const runPoseClustering = useCallback(async () => {
    if (!dockingResult || !dockingResult.poses) return;
    try {
      setLoading(true);
      const clusters = await invoke<number[][]>('cluster_poses', {
        poses: dockingResult.poses,
        rmsdCutoff: rmsdCutoff
      });
      setPoseClusters(clusters);
    } catch (err) {
      console.error('Pose clustering failed:', err);
    } finally {
      setLoading(false);
    }
  }, [dockingResult, rmsdCutoff]);

  useEffect(() => {
    if (clusterMode && dockingResult && dockingResult.poses) {
      runPoseClustering();
    } else {
      setPoseClusters([]);
    }
  }, [clusterMode, dockingResult, rmsdCutoff, runPoseClustering]);

  // Load Receptor Function
  const loadReceptor = async (sourceType: string, identifier: string) => {
    setLoading(true);
    setError(null);
    setPreparedReceptor(null);
    setHetList([]);
    setCustomHetActions({});
    setFpocketResults([]);
    setDockingResult(null);
    setSelectedPoseIndex(null);
    setInteractionFingerprint(null);
    
    if (receptorComponentRef.current) {
      stageRef.current.removeComponent(receptorComponentRef.current);
      receptorComponentRef.current = null;
    }
    if (ligandComponentRef.current) {
      stageRef.current.removeComponent(ligandComponentRef.current);
      ligandComponentRef.current = null;
    }
    if (pocketHighlightComponentRef.current) {
      stageRef.current.removeComponent(pocketHighlightComponentRef.current);
      pocketHighlightComponentRef.current = null;
    }
    setPocketLabels([]);

    try {
      // 1. Prepare/Load Receptor Metadata
      const receptorData = await invoke<any>('receptor_load_from_source', {
        sourceType,
        identifier
      });
      setPreparedReceptor(receptorData);
      setHetList(receptorData.het_entries || []);

      // 2. Read cleaned PDB text and load into NGL
      const cleanedPdbRelative = receptorData.pdbqt_path.endsWith('prepared.pdbqt')
        ? receptorData.pdbqt_path.replace('prepared.pdbqt', 'cleaned.pdb')
        : receptorData.pdbqt_path.replace('.pdbqt', '.pdb');
      const pdbContent = await invoke<string>('read_text_file', { path: cleanedPdbRelative });
      
      const blob = new Blob([pdbContent], { type: 'text/plain' });
      const comp = await stageRef.current.loadFile(blob, { ext: 'pdb', defaultRepresentation: false });
      receptorComponentRef.current = comp;
      
      // Add standard cartoon representation
      comp.addRepresentation(representation, { colorScheme: 'chainid' });
      
      // Show cofactors
      comp.addRepresentation('licorice', { sele: 'hetero and not (water or ion)', colorScheme: 'element' });
      
      // Show ions
      comp.addRepresentation('spacefill', { sele: 'ion', scale: 0.3 });

      stageRef.current.autoView();

      // 3. Set default box coordinates
      if (receptorData.cocrystal_ligands && receptorData.cocrystal_ligands.length > 0) {
        const centroid = receptorData.cocrystal_ligands[0].centroid_xyz;
        setBoxCenterX(centroid[0]);
        setBoxCenterY(centroid[1]);
        setBoxCenterZ(centroid[2]);
        setPocketMode('cocrystal');
      } else {
        // Run pocket detection
        setPocketMode('fpocket');
        runPocketDetection(receptorData.receptor_hash);
      }
    } catch (e: any) {
      console.error(e);
      setError(`Failed to load receptor: ${e.message || e}`);
    } finally {
      setLoading(false);
    }
  };

  // Run Pocket Detection
  const runPocketDetection = async (hash: string) => {
    setDetectingPockets(true);
    try {
      const pocketData = await invoke<any>('pocket_detect', { receptorHash: hash });
      setFpocketResults(pocketData.fpocket_results || []);
      if (pocketData.fpocket_results && pocketData.fpocket_results.length > 0) {
        const topPocket = pocketData.fpocket_results[0];
        setBoxCenterX(topPocket.centroid[0]);
        setBoxCenterY(topPocket.centroid[1]);
        setBoxCenterZ(topPocket.centroid[2]);
        setSelectedPocketId(topPocket.pocket_id);
        highlightPocket(topPocket);
      }
    } catch (e: any) {
      console.error('Pocket detection failed', e);
    } finally {
      setDetectingPockets(false);
    }
  };

  // Highlight fpocket
  const highlightPocket = (pocket: any) => {
    if (!stageRef.current || !receptorComponentRef.current) return;

    if (pocketHighlightComponentRef.current) {
      stageRef.current.removeComponent(pocketHighlightComponentRef.current);
      pocketHighlightComponentRef.current = null;
    }

    // Highlighting residues
    const residues = pocket.pocket_residues || [];
    const selectionList = residues.map((r: string) => {
      const parts = r.split(':');
      if (parts.length < 2) return '';
      const chain = parts[0];
      const rest = parts[1].split('-');
      if (rest.length < 2) return '';
      const num = rest[1];
      return `${num}:${chain}`;
    }).filter(Boolean);

    const selectionString = selectionList.join(' or ');

    if (selectionString) {
      try {
        const highlightRepr = receptorComponentRef.current.addRepresentation('licorice', {
          sele: selectionString,
          colorValue: '#f59e0b',
          opacity: 0.8
        });
        pocketHighlightComponentRef.current = highlightRepr;
      } catch (err) {
        console.warn('Highlight representation failed', err);
      }
    }
  };

  // Apply customized HET actions and reprepare
  const applyReprepare = async () => {
    if (!preparedReceptor) return;
    setRepreparing(true);
    setError(null);
    try {
      const params = {
        keep_water: keepWater,
        keep_ions: keepIons,
        keep_cofactors: keepCofactors,
        keep_cocrystal_ligands: keepCocrystalLigands,
        custom_het_actions: customHetActions,
        add_hydrogens: true,
        ph: 7.4,
        method: 'meeko'
      };

      const reprepped = await invoke<any>('receptor_reprepare', {
        receptorHash: preparedReceptor.receptor_hash,
        params
      });

      // Reload PDB into NGL
      setPreparedReceptor(reprepped);
      setHetList(reprepped.het_entries || []);

      const cleanedPdbRelative = reprepped.pdbqt_path.endsWith('prepared.pdbqt')
        ? reprepped.pdbqt_path.replace('prepared.pdbqt', 'cleaned.pdb')
        : reprepped.pdbqt_path.replace('.pdbqt', '.pdb');
      const pdbContent = await invoke<string>('read_text_file', { path: cleanedPdbRelative });
      
      if (receptorComponentRef.current) {
        stageRef.current.removeComponent(receptorComponentRef.current);
      }

      const blob = new Blob([pdbContent], { type: 'text/plain' });
      const comp = await stageRef.current.loadFile(blob, { ext: 'pdb', defaultRepresentation: false });
      receptorComponentRef.current = comp;
      comp.addRepresentation(representation, { colorScheme: 'chainid' });
      comp.addRepresentation('licorice', { sele: 'hetero and not (water or ion)', colorScheme: 'element' });
      comp.addRepresentation('spacefill', { sele: 'ion', scale: 0.3 });

      stageRef.current.autoView();
    } catch (e: any) {
      console.error(e);
      setError(`Reprepare failed: ${e.message || e}`);
    } finally {
      setRepreparing(false);
    }
  };

  const handlePickLigandFile = async () => {
    try {
      const selected = await openFileDialog({
        multiple: false,
        filters: [
          { name: 'Chemical Structure Files', extensions: ['sdf', 'smi', 'smiles', 'csv', 'txt'] }
        ]
      });

      if (!selected) return;

      const pathStr = selected as string;
      const fileName = pathStr.split(/[/\\]/).pop() || 'file';
      const ext = fileName.split('.').pop() || '';

      setLoading(true);
      setError(null);

      // Read file contents using 'read_text_file' command
      const contents = await invoke<string>('read_text_file', { path: pathStr });

      // Parse using 'parse_library' RPC call
      const parsed = await invoke<any[]>('invoke_python_rpc', {
        method: 'parse_library',
        params: {
          contents,
          extension: ext
        }
      });

      if (Array.isArray(parsed) && parsed.length > 0) {
        setFileMols(parsed);
        setSelectedFileMolIdx(0);
        setUploadedFileName(fileName);
        setLigandDisplayName(parsed[0].name || fileName.split('.')[0] || 'Ligand');
      } else {
        setError('No valid chemical structures could be parsed from this file.');
      }
    } catch (err: any) {
      console.error('File load failed:', err);
      setError(`Failed to read/parse chemical file: ${err.message || err}`);
    } finally {
      setLoading(false);
    }
  };

  // Prepare Ligand
  const handlePrepareLigand = async () => {
    let smilesToPrep = '';
    if (ligandSource === 'workspace' || ligandSource === 'smiles') {
      smilesToPrep = customSmiles.trim();
    } else if (ligandSource === 'upload') {
      if (fileMols.length > 0 && fileMols[selectedFileMolIdx]) {
        smilesToPrep = fileMols[selectedFileMolIdx].smiles;
      }
    }

    if (!smilesToPrep) {
      setError('Please select/provide a valid ligand structure');
      return;
    }
    setPreparingLigand(true);
    setError(null);
    setPreparedLigand(null);

    try {
      const params = {
        conformer_method: 'ETKDGv3',
        optimization: 'MMFF94',
        embed_attempts: 15,
        add_hydrogens: true,
        pH: 7.4,
        deprotonate_acids: true,
        protonate_bases: true
      };

      const result = await invoke<any>('ligand_prepare', {
        smiles: smilesToPrep,
        params
      });

      setPreparedLigand(result);
    } catch (e: any) {
      console.error(e);
      setError(`Ligand prep failed: ${e.message || e}`);
    } finally {
      setPreparingLigand(false);
    }
  };

  // Run Vina Docking Job
  const handleDock = async () => {
    if (!preparedReceptor || !preparedLigand) {
      setError('Please load a receptor and prepare a ligand first.');
      return;
    }
    setIsDocking(true);
    setDockingProgress(0);
    setError(null);
    setDockingResult(null);
    setSelectedPoseIndex(null);
    setInteractionFingerprint(null);

    if (ligandComponentRef.current) {
      stageRef.current.removeComponent(ligandComponentRef.current);
      ligandComponentRef.current = null;
    }

    const jobUuid = crypto.randomUUID();
    setDockingJobId(jobUuid);

    const spec = {
      job_id: jobUuid,
      receptor_hash: preparedReceptor.receptor_hash,
      ligand_hash: preparedLigand.ligand_hash,
      box_center: [boxCenterX, boxCenterY, boxCenterZ],
      box_size: [boxSizeX, boxSizeY, boxSizeZ],
      exhaustiveness,
      num_modes: numModes,
      seed: 42,
      engine: dockingEngine,
      created_at: new Date().toISOString()
    };

    try {
      const result = await invoke<any>('docking_run', {
        spec,
        ligandSmiles: preparedLigand.source_smiles,
        receptorDisplayName: preparedReceptor.pdb_source.includes('preset') 
          ? preparedReceptor.pdb_source.split(':')[1].toUpperCase() 
          : preparedReceptor.pdb_source.split('/').pop() || 'Receptor',
        ligandDisplayName: ligandDisplayName
      });

      setDockingResult(result);
      if (result.poses && result.poses.length > 0) {
        loadPose(result.poses[0], 0);
      }
      refreshJobHistory();
    } catch (e: any) {
      console.error(e);
      setError(`Docking execution failed: ${e.message || e}`);
    } finally {
      setIsDocking(false);
      setDockingJobId(null);
    }
  };

  // Cancel Docking
  const handleCancelDocking = async () => {
    if (!dockingJobId) return;
    try {
      await invoke('docking_cancel', { jobId: dockingJobId });
      setError('Docking job cancelled by user.');
    } catch (e: any) {
      console.error(e);
    } finally {
      setIsDocking(false);
      setDockingJobId(null);
    }
  };

  // Load Pose in 3D View
  const loadPose = async (pose: any, index: number) => {
    setSelectedPoseIndex(index);
    setInteractionFingerprint(null);
    
    if (!stageRef.current) return;

    if (ligandComponentRef.current) {
      stageRef.current.removeComponent(ligandComponentRef.current);
      ligandComponentRef.current = null;
    }

    try {
      const poseSdf = pose.sdf_block || '';
      const blob = new Blob([poseSdf], { type: 'text/plain' });
      const comp = await stageRef.current.loadFile(blob, { ext: 'sdf', defaultRepresentation: false });
      ligandComponentRef.current = comp;

      comp.addRepresentation('ball+stick', {
        colorValue: '#10b981',
        multipleBond: 'offset'
      });

      // Polar contacts / H-bonds
      comp.addRepresentation('contact', {
        contactType: 'polar',
        colorValue: '#10b981',
        dashed: true
      });

      // Focus camera on ligand
      const center = comp.getCenter();
      if (center) {
        stageRef.current.animationControls.zoomMove(
          center,
          stageRef.current.getZoom() * 0.45,
          1000
        );
      }

      // Compute Interactions
      loadInteractions(poseSdf, index + 1);
    } catch (err: any) {
      console.error('Failed to load pose', err);
      setError(`Failed to render pose: ${err.message || err}`);
    }
  };

  // Load Interaction Fingerprints
  const loadInteractions = async (sdfBlock: string, poseIdx: number) => {
    if (!preparedReceptor) return;
    setLoadingInteractions(true);
    try {
      const data = await invoke<any>('analysis_interactions', {
        receptorPdbPath: preparedReceptor.raw_pdb_path,
        poseSdfBlock: sdfBlock,
        poseIndex: poseIdx
      });
      setInteractionFingerprint(data);
    } catch (err: any) {
      console.error('Failed to compute interactions', err);
    } finally {
      setLoadingInteractions(false);
    }
  };

  // Highlight single residue interaction
  const focusResidue = (residue: string) => {
    if (!stageRef.current) return;
    const parts = residue.split(':');
    if (parts.length < 2) return;
    const chain = parts[0];
    const rest = parts[1].split('-');
    const resnum = rest[1] || rest[0];
    
    stageRef.current.autoView(`:${chain} and ${resnum}`, 800);
  };

  // Handle Distance Measurement Click
  const toggleMeasureMode = () => {
    const next = !measureMode;
    setMeasureMode(next);
    setSelectedAtoms([]);
    
    if (!stageRef.current) return;

    if (next) {
      stageRef.current.signals.clicked.add(handleAtomPick);
    } else {
      stageRef.current.signals.clicked.remove(handleAtomPick);
    }
  };

  const handleAtomPick = (pickingProxy: any) => {
    if (!pickingProxy) return;
    const atom = pickingProxy.atom;
    if (!atom) return;

    const label = `${atom.chainname}:${atom.resname}-${atom.resno}:${atom.atomname}`;
    setSelectedAtoms((prev) => {
      const updated = [...prev, label];
      if (updated.length === 2) {
        computePickedDistance(updated[0], updated[1]);
        return [];
      }
      return updated;
    });
  };

  const computePickedDistance = async (a1: string, a2: string) => {
    if (!dockingResult || selectedPoseIndex === null || !preparedReceptor) return;
    const currentPose = dockingResult.poses[selectedPoseIndex];
    try {
      const val = await invoke<number>('analysis_distance', {
        poseSdfBlock: currentPose.sdf_block,
        receptorPdbPath: preparedReceptor.raw_pdb_path,
        atom1Selector: a1,
        atom2Selector: a2
      });

      setMeasuredDistances((prev) => [
        { id: crypto.randomUUID(), a1, a2, value: Number(val.toFixed(3)) },
        ...prev.slice(0, 4) // cap at 5 measurements
      ]);
    } catch (e: any) {
      console.error(e);
      setError(`Failed to compute distance: ${e.message || e}`);
    }
  };

  // Job History Functions
  const refreshJobHistory = async () => {
    try {
      const list = await invoke<any[]>('history_list', {
        receptorId: null,
        starredOnly: historyStarredOnly || null,
        searchQuery: historySearch || null
      });
      setJobHistory(list);
    } catch (e) {
      console.error('History fetch failed', e);
    }
  };

  useEffect(() => {
    refreshJobHistory();
  }, [historyStarredOnly, historySearch]);

  const handleStarJob = async (jobId: string, starred: boolean) => {
    try {
      await invoke('history_star', { jobId, starred });
      refreshJobHistory();
    } catch (e) {
      console.error(e);
    }
  };

  const handleDeleteJob = async (jobId: string) => {
    try {
      await invoke('history_delete', { jobId });
      refreshJobHistory();
    } catch (e) {
      console.error(e);
    }
  };

  const handleReloadJob = async (jobId: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await invoke<any>('history_load', { jobId });
      setDockingResult(data);
      if (data.poses && data.poses.length > 0) {
        loadPose(data.poses[0], 0);
      }
    } catch (e: any) {
      setError(`Failed to reload job: ${e.message || e}`);
    } finally {
      setLoading(false);
    }
  };

  const getScoreColor = (score: number) => {
    if (score <= -10.0) return { label: 'Strong', color: 'bg-emerald-900 border-emerald-600 text-emerald-100' };
    if (score > -10.0 && score <= -8.0) return { label: 'Moderate', color: 'bg-amber-800 border-amber-500 text-amber-100' };
    if (score > -8.0 && score <= -6.0) return { label: 'Weak', color: 'bg-orange-800 border-orange-500 text-orange-100' };
    return { label: 'Unfavorable', color: 'bg-rose-950 border-rose-800 text-rose-100' };
  };

  const focusWholeProtein = () => {
    if (!stageRef.current) return;
    try {
      stageRef.current.autoView(800);
      
      // Reset main representation (cartoon/surface/sticks) to fully opaque (1.0)
      if (receptorComponentRef.current) {
        receptorComponentRef.current.eachRepresentation((repr: any) => {
          const reprType = repr.repr?.type || repr.type || '';
          if (reprType === representation) {
            repr.setParameters({ opacity: 1.0 });
          }
        });
      }

      // Remove pocket residue labels
      setPocketLabels([]);
    } catch (err) {
      console.warn('[DockingWorkbench] focusWholeProtein failed:', err);
    }
  };

  const focusBindingSite = () => {
    if (!stageRef.current) return;
    try {
      // Determine center coordinate: ligand center if loaded, else grid box center
      let center = { x: boxCenterX, y: boxCenterY, z: boxCenterZ };
      
      if (ligandComponentRef.current) {
        const ligCenter = ligandComponentRef.current.getCenter();
        if (ligCenter) {
          center = { x: ligCenter.x, y: ligCenter.y, z: ligCenter.z };
        }
      }

      // Clear existing pocket labels first
      setPocketLabels([]);

      // Find residues of protein near this center (within 6Å)
      const selectionParts: string[] = [];
      const newPocketLabels: { id: string; text: string; x: number; y: number; z: number }[] = [];
      if (receptorComponentRef.current && receptorComponentRef.current.structure) {
        const struct = receptorComponentRef.current.structure;
        const nearResidues = new Set<string>();
        const fallbackAtomByResKey: Record<string, { x: number; y: number; z: number; resname: string; resno: number }> = {};

        struct.eachAtom((atom: any) => {
          const dx = atom.x - center.x;
          const dy = atom.y - center.y;
          const dz = atom.z - center.z;
          const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
          const chain = atom.chainname ? atom.chainname.trim() : '';
          const resKey = chain ? `${atom.resno}:${chain}` : `${atom.resno}`;
          
          if (dist <= 6.0) {
            nearResidues.add(resKey);
          }
          
          // Store CA as priority, or fallback to any atom of the residue
          if (atom.atomname === 'CA' || !fallbackAtomByResKey[resKey]) {
            fallbackAtomByResKey[resKey] = {
              x: atom.x,
              y: atom.y,
              z: atom.z,
              resname: atom.resname || '',
              resno: atom.resno
            };
          }
        });

        nearResidues.forEach((resKey) => {
          selectionParts.push(resKey);
          const ca = fallbackAtomByResKey[resKey];
          if (ca) {
            newPocketLabels.push({
              id: resKey,
              text: `${ca.resname.toUpperCase()}${ca.resno}`,
              x: ca.x,
              y: ca.y,
              z: ca.z
            });
          }
        });
      }

      let focused = false;
      const selString = selectionParts.length > 0 ? selectionParts.join(' or ') : '';
      if (selString && receptorComponentRef.current) {
        const selectionObj = new NglObj.Selection(selString);
        const view = receptorComponentRef.current.structure.getView(selectionObj);
        if (view && view.center && !isNaN(view.center.x)) {
          stageRef.current.animationControls.zoomMove(view.center, 30.0, 800);
          focused = true;
        }
      }

      if (!focused && center && !isNaN(center.x)) {
        stageRef.current.animationControls.zoomMove(center, 30.0, 800);
      }

      // Make the main representation (cartoon/surface/sticks) semi-transparent (0.35)
      // to let the binding site and ligand stand out clearly.
      if (receptorComponentRef.current) {
        receptorComponentRef.current.eachRepresentation((repr: any) => {
          const reprType = repr.repr?.type || repr.type || '';
          if (reprType === representation) {
            repr.setParameters({ opacity: 0.35 });
          }
        });
      }

      // Update state to trigger coordinate projection loop
      if (newPocketLabels.length > 0) {
        setPocketLabels(newPocketLabels);
      }
    } catch (err) {
      console.warn('[DockingWorkbench] focusBindingSite failed:', err);
    }
  };

  return (
    <div className="main-content" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      
      {/* Top Bar Header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '12px 20px',
        borderBottom: '0.5px solid var(--color-border)',
        background: 'var(--color-surface)',
        flexShrink: 0
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <h2 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--color-brand-900)' }}>🛰️ Docking Workbench</h2>
            {preparedReceptor && (
              <span style={{
                fontSize: '10px',
                fontWeight: 600,
                color: 'var(--color-brand-900)',
                background: 'var(--color-brand-100)',
                padding: '2px 8px',
                borderRadius: '10px',
                border: '0.5px solid var(--color-brand-50)'
              }}>
                {preparedReceptor.pdb_source.includes('preset') 
                  ? preparedReceptor.pdb_source.split(':')[1].toUpperCase() 
                  : 'CUSTOM'} Prepared
              </span>
            )}
          </div>
          <p style={{ fontSize: '11px', color: 'var(--color-text-600)', marginTop: '2px' }}>
            Curate receptors, configure binding site boxes, prepare target ligands, and execute high-fidelity AutoDock Vina calculations.
          </p>
        </div>
        
        <div style={{ display: 'flex', gap: '8px' }}>
          <button 
            onClick={() => setHistoryOpen(!historyOpen)}
            className="workflow-btn-configure"
            style={{
              padding: '6px 12px',
              fontSize: '11px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontWeight: 600
            }}
          >
            📋 Job History ({jobHistory.length})
          </button>
        </div>
      </div>

      {/* Main 3-Pane Work Area */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        
        {/* LEFT COLUMN: RECEPTOR & POCKET PREPARATION */}
        <div style={{
          width: '340px',
          borderRight: '0.5px solid var(--color-border)',
          background: 'var(--color-bg)',
          display: 'flex',
          flexDirection: 'column',
          overflowY: 'auto',
          padding: '16px',
          gap: '16px'
        }} className="changelog-scroll">
          
          {/* Receptor Selection Tabs */}
          <div style={{
            background: 'var(--color-surface)',
            border: '0.5px solid var(--color-border)',
            borderRadius: '8px',
            padding: '12px'
          }}>
            <h3 style={{ fontSize: '12px', fontWeight: 700, color: 'var(--color-text-900)', marginBottom: '8px' }}>1. Receptor Macromolecule</h3>
            
            {/* Source select buttons */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginBottom: '8px' }}>
              {['Preset', 'PDB Code', 'AlphaFold'].map((mode) => (
                <button
                  key={mode}
                  onClick={() => {
                    if (mode === 'Preset') setSelectedPresetId(RECEPTOR_PRESETS[0].id);
                  }}
                  style={{
                    flex: 1,
                    fontSize: '10px',
                    padding: '4px 6px',
                    borderRadius: '4px',
                    fontWeight: 600,
                    border: '0.5px solid var(--color-border)',
                    cursor: 'pointer',
                    background: selectedPresetId ? 'var(--color-brand-100)' : 'transparent',
                    color: selectedPresetId ? 'var(--color-brand-900)' : 'var(--color-text-600)'
                  }}
                >
                  {mode}
                </button>
              ))}
            </div>

            {/* Presets Grid */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <select
                value={selectedPresetId}
                onChange={(e) => {
                  setSelectedPresetId(e.target.value);
                  loadReceptor('preset', e.target.value);
                }}
                className="config-select"
                style={{ fontSize: '11px', width: '100%', padding: '6px' }}
              >
                {RECEPTOR_PRESETS.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
              <span style={{ fontSize: '9px', color: 'var(--color-text-400)', marginTop: '2px', lineHeight: '1.3' }}>
                {RECEPTOR_PRESETS.find(p => p.id === selectedPresetId)?.description}
              </span>
            </div>

            {/* Manual PDB/AF codes */}
            <div style={{ display: 'flex', gap: '4px', marginTop: '8px' }}>
              <input
                type="text"
                placeholder="PDB Code (e.g. 1YBH)"
                value={pdbCodeInput}
                onChange={(e) => setPdbCodeInput(e.target.value)}
                style={{
                  flex: 1,
                  padding: '4px 8px',
                  borderRadius: '4px',
                  border: '0.5px solid var(--color-border)',
                  fontSize: '10px'
                }}
              />
              <button
                onClick={() => loadReceptor('pdb_code', pdbCodeInput)}
                className="workflow-btn-configure"
                style={{ fontSize: '10px', height: '24px', padding: '0 8px' }}
              >
                Fetch
              </button>
            </div>
            
            <div style={{ display: 'flex', gap: '4px', marginTop: '4px' }}>
              <input
                type="text"
                placeholder="UniProt ID (e.g. P0A7A5)"
                value={afUniprotInput}
                onChange={(e) => setAfUniprotInput(e.target.value)}
                style={{
                  flex: 1,
                  padding: '4px 8px',
                  borderRadius: '4px',
                  border: '0.5px solid var(--color-border)',
                  fontSize: '10px'
                }}
              />
              <button
                onClick={() => loadReceptor('alphafold', afUniprotInput)}
                className="workflow-btn-configure"
                style={{ fontSize: '10px', height: '24px', padding: '0 8px' }}
              >
                AF Load
              </button>
            </div>
          </div>

          {/* HET Atoms Manager */}
          {preparedReceptor && (
            <div style={{
              background: 'var(--color-surface)',
              border: '0.5px solid var(--color-border)',
              borderRadius: '8px',
              padding: '12px'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <h3 style={{ fontSize: '12px', fontWeight: 700, color: 'var(--color-text-900)' }}>2. HET Atom Curation</h3>
                <button
                  onClick={applyReprepare}
                  disabled={repreparing}
                  className="workflow-btn-configure"
                  style={{ fontSize: '9px', padding: '2px 8px', height: '20px', fontWeight: 700 }}
                >
                  {repreparing ? 'Prepping...' : 'Apply & Prep'}
                </button>
              </div>

              {repreparing && (
                <div style={{ marginTop: '8px' }}>
                  <ProgressIndicator
                    variant="indeterminate"
                    label="Repreparing receptor structures (solvent extraction)..."
                  />
                </div>
              )}

              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', maxHeight: '150px', overflowY: 'auto' }}>
                {hetList.length === 0 ? (
                  <span style={{ fontSize: '10px', color: 'var(--color-text-400)' }}>No HET residues detected.</span>
                ) : (
                  hetList.map((entry) => (
                    <div 
                      key={`${entry.chain_id}-${entry.residue_number}`}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '4px 6px',
                        background: 'var(--color-bg)',
                        borderRadius: '4px',
                        border: '0.5px solid var(--color-border)'
                      }}
                    >
                      <span style={{ fontSize: '10px', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                        {entry.residue_name} ({entry.chain_id}:{entry.residue_number})
                      </span>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <span style={{
                          fontSize: '8px',
                          padding: '1px 4px',
                          borderRadius: '3px',
                          background: 'var(--color-brand-100)',
                          color: 'var(--color-brand-900)',
                          fontWeight: 600
                        }}>
                          {entry.type_classification}
                        </span>
                        <input
                          type="checkbox"
                          checked={customHetActions[entry.residue_name] === 'keep' || (!customHetActions[entry.residue_name] && entry.default_action === 'keep')}
                          onChange={(e) => {
                            setCustomHetActions({
                              ...customHetActions,
                              [entry.residue_name]: e.target.checked ? 'keep' : 'strip'
                            });
                          }}
                          style={{ accentColor: 'var(--color-brand-600)', cursor: 'pointer' }}
                        />
                      </div>
                    </div>
                  ))
                )}
              </div>

              {/* Quick selectors */}
              <div style={{ display: 'flex', gap: '8px', marginTop: '8px', fontSize: '9px', color: 'var(--color-text-600)' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '2px', cursor: 'pointer' }}>
                  <input type="checkbox" checked={keepWater} onChange={(e) => setKeepWater(e.target.checked)} style={{ transform: 'scale(0.8)' }} />
                  Water
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '2px', cursor: 'pointer' }}>
                  <input type="checkbox" checked={keepIons} onChange={(e) => setKeepIons(e.target.checked)} style={{ transform: 'scale(0.8)' }} />
                  Ions
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '2px', cursor: 'pointer' }}>
                  <input type="checkbox" checked={keepCofactors} onChange={(e) => setKeepCofactors(e.target.checked)} style={{ transform: 'scale(0.8)' }} />
                  Cofactors
                </label>
              </div>
            </div>
          )}

          {/* Pocket detection / Selection */}
          {preparedReceptor && (
            <div style={{
              background: 'var(--color-surface)',
              border: '0.5px solid var(--color-border)',
              borderRadius: '8px',
              padding: '12px'
            }}>
              <h3 style={{ fontSize: '12px', fontWeight: 700, color: 'var(--color-text-900)', marginBottom: '8px' }}>3. Target Binding Site</h3>
              
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginBottom: '8px' }}>
                <button
                  onClick={() => setPocketMode('cocrystal')}
                  disabled={!preparedReceptor.cocrystal_ligands || preparedReceptor.cocrystal_ligands.length === 0}
                  style={{
                    flex: 1,
                    fontSize: '9px',
                    padding: '4px',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    background: pocketMode === 'cocrystal' ? 'var(--color-brand-100)' : 'transparent',
                    border: '0.5px solid var(--color-border)',
                    color: pocketMode === 'cocrystal' ? 'var(--color-brand-900)' : 'var(--color-text-600)',
                    opacity: (!preparedReceptor.cocrystal_ligands || preparedReceptor.cocrystal_ligands.length === 0) ? 0.5 : 1
                  }}
                >
                  ⚡ Cocrystal
                </button>
                <button
                  onClick={() => {
                    setPocketMode('fpocket');
                    if (fpocketResults.length === 0) {
                      runPocketDetection(preparedReceptor.receptor_hash);
                    }
                  }}
                  style={{
                    flex: 1,
                    fontSize: '9px',
                    padding: '4px',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    background: pocketMode === 'fpocket' ? 'var(--color-brand-100)' : 'transparent',
                    border: '0.5px solid var(--color-border)',
                    color: pocketMode === 'fpocket' ? 'var(--color-brand-900)' : 'var(--color-text-600)'
                  }}
                >
                  🔍 fpocket
                </button>
                <button
                  onClick={() => setPocketMode('manual')}
                  style={{
                    flex: 1,
                    fontSize: '9px',
                    padding: '4px',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    background: pocketMode === 'manual' ? 'var(--color-brand-100)' : 'transparent',
                    border: '0.5px solid var(--color-border)',
                    color: pocketMode === 'manual' ? 'var(--color-brand-900)' : 'var(--color-text-600)'
                  }}
                >
                  🛠️ Coordinates
                </button>
              </div>

              {pocketMode === 'cocrystal' && preparedReceptor.cocrystal_ligands && preparedReceptor.cocrystal_ligands.length > 0 && (
                <div style={{ padding: '6px', background: 'var(--color-bg)', borderRadius: '4px', fontSize: '10px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <strong>Ligand Name:</strong>
                    <span>{preparedReceptor.cocrystal_ligands[0].residue_name}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '4px' }}>
                    <strong>Center coordinates:</strong>
                    <span style={{ fontFamily: 'var(--font-mono)' }}>
                      [{preparedReceptor.cocrystal_ligands[0].centroid_xyz.map((c: number) => c.toFixed(2)).join(', ')}]
                    </span>
                  </div>
                </div>
              )}

              {pocketMode === 'fpocket' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  {detectingPockets && (
                    <div style={{ fontSize: '10px', color: 'var(--color-text-600)', padding: '8px', textAlign: 'center' }}>
                      <RefreshCw style={{ animation: 'spin 2s linear infinite', width: '12px', height: '12px', display: 'inline', marginRight: '6px' }} />
                      Detecting binding pockets...
                    </div>
                  )}
                  {fpocketResults.length > 0 ? (
                    fpocketResults.slice(0, 4).map((p) => (
                      <button
                        key={p.pocket_id}
                        onClick={() => {
                          setSelectedPocketId(p.pocket_id);
                          setBoxCenterX(p.centroid[0]);
                          setBoxCenterY(p.centroid[1]);
                          setBoxCenterZ(p.centroid[2]);
                          highlightPocket(p);
                        }}
                        style={{
                          width: '100%',
                          textAlign: 'left',
                          padding: '6px 8px',
                          border: selectedPocketId === p.pocket_id ? '1px solid var(--color-brand-700)' : '0.5px solid var(--color-border)',
                          background: selectedPocketId === p.pocket_id ? 'var(--color-brand-50)' : 'var(--color-bg)',
                          borderRadius: '4px',
                          cursor: 'pointer',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center'
                        }}
                      >
                        <div style={{ display: 'flex', flexDirection: 'column' }}>
                          <span style={{ fontSize: '10px', fontWeight: 600, color: 'var(--color-text-900)' }}>Pocket #{p.pocket_id} (Rank {p.rank})</span>
                          <span style={{ fontSize: '8px', color: 'var(--color-text-400)' }}>Vol: {Math.round(p.volume_angstrom_cubed)} Å³</span>
                        </div>
                        <span style={{
                          fontSize: '9px',
                          fontWeight: 700,
                          background: 'var(--color-brand-100)',
                          color: 'var(--color-brand-900)',
                          padding: '1px 6px',
                          borderRadius: '10px'
                        }}>
                          Druggability: {p.druggability_score.toFixed(2)}
                        </span>
                      </button>
                    ))
                  ) : !detectingPockets && (
                    <span style={{ fontSize: '10px', color: 'var(--color-text-400)' }}>No pockets found.</span>
                  )}
                </div>
              )}

              {/* Box Configuration Inputs */}
              {(pocketMode === 'manual' || pocketMode === 'cocrystal' || pocketMode === 'fpocket') && (
                <div style={{ marginTop: '10px', borderTop: '0.5px solid var(--color-border)', paddingTop: '10px' }}>
                  <span style={{ fontSize: '10px', fontWeight: 600, color: 'var(--color-text-600)', display: 'inline-flex', alignItems: 'center', gap: '4px', marginBottom: '6px' }}>
                    Grid Box Bounds
                    <ContextualHelp topicId="docking.box_size" />
                  </span>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '6px', marginBottom: '8px' }}>
                    <div>
                      <label style={{ fontSize: '8px', color: 'var(--color-text-400)' }}>Center X</label>
                      <input
                        type="number"
                        value={boxCenterX}
                        step="0.5"
                        onChange={(e) => setBoxCenterX(parseFloat(e.target.value) || 0.0)}
                        style={{ width: '100%', fontSize: '10px', padding: '3px 4px', border: '0.5px solid var(--color-border)', borderRadius: '3px' }}
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: '8px', color: 'var(--color-text-400)' }}>Center Y</label>
                      <input
                        type="number"
                        value={boxCenterY}
                        step="0.5"
                        onChange={(e) => setBoxCenterY(parseFloat(e.target.value) || 0.0)}
                        style={{ width: '100%', fontSize: '10px', padding: '3px 4px', border: '0.5px solid var(--color-border)', borderRadius: '3px' }}
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: '8px', color: 'var(--color-text-400)' }}>Center Z</label>
                      <input
                        type="number"
                        value={boxCenterZ}
                        step="0.5"
                        onChange={(e) => setBoxCenterZ(parseFloat(e.target.value) || 0.0)}
                        style={{ width: '100%', fontSize: '10px', padding: '3px 4px', border: '0.5px solid var(--color-border)', borderRadius: '3px' }}
                      />
                    </div>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '6px' }}>
                    <div>
                      <label style={{ fontSize: '8px', color: 'var(--color-text-400)' }}>Size X (Å)</label>
                      <input
                        type="number"
                        value={boxSizeX}
                        onChange={(e) => {
                          const val = parseFloat(e.target.value) || 10.0;
                          setBoxSizeX(val);
                          if (linkSizes) { setBoxSizeY(val); setBoxSizeZ(val); }
                        }}
                        style={{ width: '100%', fontSize: '10px', padding: '3px 4px', border: '0.5px solid var(--color-border)', borderRadius: '3px' }}
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: '8px', color: 'var(--color-text-400)' }}>Size Y (Å)</label>
                      <input
                        type="number"
                        value={boxSizeY}
                        onChange={(e) => {
                          const val = parseFloat(e.target.value) || 10.0;
                          setBoxSizeY(val);
                          if (linkSizes) { setBoxSizeX(val); setBoxSizeZ(val); }
                        }}
                        style={{ width: '100%', fontSize: '10px', padding: '3px 4px', border: '0.5px solid var(--color-border)', borderRadius: '3px' }}
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: '8px', color: 'var(--color-text-400)' }}>Size Z (Å)</label>
                      <input
                        type="number"
                        value={boxSizeZ}
                        onChange={(e) => {
                          const val = parseFloat(e.target.value) || 10.0;
                          setBoxSizeZ(val);
                          if (linkSizes) { setBoxSizeX(val); setBoxSizeY(val); }
                        }}
                        style={{ width: '100%', fontSize: '10px', padding: '3px 4px', border: '0.5px solid var(--color-border)', borderRadius: '3px' }}
                      />
                    </div>
                  </div>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '9px', color: 'var(--color-text-600)', marginTop: '8px', cursor: 'pointer' }}>
                    <input type="checkbox" checked={linkSizes} onChange={(e) => setLinkSizes(e.target.checked)} style={{ transform: 'scale(0.8)' }} />
                    Link sizes (maintain cube)
                  </label>
                </div>
              )}
            </div>
          )}
        </div>

        {/* CENTER COLUMN: 3D VIEWPORT WITH FLOATING CONTROLS */}
        <div style={{ flex: 1, position: 'relative', display: 'flex', flexDirection: 'column', background: 'var(--color-bg)' }}>
          
          {loading && (
            <div style={{
              position: 'absolute',
              inset: 0,
              background: 'rgba(255,255,255,0.7)',
              zIndex: 10,
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
              alignItems: 'center',
              fontSize: '13px',
              fontWeight: 600,
              color: 'var(--color-brand-900)'
            }}>
              <RefreshCw style={{ animation: 'spin 2s linear infinite', width: '24px', height: '24px', marginBottom: '8px' }} />
              Loading prepared structure...
            </div>
          )}

          {error && (
            <div style={{
              position: 'absolute',
              top: '16px',
              left: '16px',
              right: '16px',
              padding: '12px 16px',
              background: 'var(--color-red-100)',
              border: '0.5px solid var(--color-red-500)',
              borderRadius: '8px',
              color: 'var(--color-red-700)',
              fontSize: '11px',
              zIndex: 5,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <AlertTriangle style={{ width: '16px', height: '16px' }} />
                <span>{error}</span>
              </div>
              <button onClick={() => setError(null)} style={{ border: 'none', background: 'transparent', cursor: 'pointer' }}>
                <X style={{ width: '14px', height: '14px', color: 'var(--color-red-700)' }} />
              </button>
            </div>
          )}

          {/* Atom Picking Indicator */}
          {measureMode && (
            <div style={{
              position: 'absolute',
              top: '16px',
              left: '50%',
              transform: 'translateX(-50%)',
              padding: '8px 16px',
              background: 'var(--color-blue-700)',
              color: '#ffffff',
              borderRadius: '20px',
              fontSize: '10px',
              zIndex: 5,
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              boxShadow: 'var(--shadow-md)'
            }}>
              <Compass style={{ animation: 'spin 4s linear infinite', width: '12px', height: '12px' }} />
              <span>Select two atoms to measure distance. ({selectedAtoms.length}/2 picked)</span>
              <button 
                onClick={toggleMeasureMode}
                style={{ background: 'transparent', border: 'none', color: '#ffffff', cursor: 'pointer' }}
              >
                <X style={{ width: '12px', height: '12px' }} />
              </button>
            </div>
          )}

          {/* Floating NGL control buttons */}
          <div style={{
            position: 'absolute',
            bottom: '16px',
            left: '16px',
            display: 'flex',
            gap: '6px',
            zIndex: 4,
            background: 'rgba(255,255,255,0.85)',
            padding: '4px',
            borderRadius: '6px',
            border: '0.5px solid var(--color-border)',
            boxShadow: 'var(--shadow-sm)'
          }}>
            <button
              onClick={() => setIsSpinning(!isSpinning)}
              title="Toggle Spin"
              style={{
                border: 'none',
                background: isSpinning ? 'var(--color-brand-100)' : 'transparent',
                color: isSpinning ? 'var(--color-brand-900)' : 'var(--color-text-600)',
                padding: '6px',
                borderRadius: '4px',
                cursor: 'pointer'
              }}
            >
              <Rotate3d style={{ width: '14px', height: '14px' }} />
            </button>
            
            <button
              onClick={() => {
                if (stageRef.current) stageRef.current.autoView();
              }}
              title="Reset View"
              style={{
                border: 'none',
                background: 'transparent',
                color: 'var(--color-text-600)',
                padding: '6px',
                borderRadius: '4px',
                cursor: 'pointer'
              }}
            >
              <Camera style={{ width: '14px', height: '14px' }} />
            </button>

            <div style={{ width: '1px', height: '18px', background: 'var(--color-border)', margin: 'auto 2px' }} />

            <button
              onClick={focusWholeProtein}
              title="Focus Whole Protein"
              style={{
                border: 'none',
                background: 'transparent',
                color: 'var(--color-text-600)',
                padding: '4px 8px',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '11px',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: '4px'
              }}
            >
              <span>Focus Protein</span>
            </button>

            <button
              onClick={focusBindingSite}
              title="Focus Binding Site (Ligand + 6Å)"
              style={{
                border: 'none',
                background: 'transparent',
                color: 'var(--color-text-600)',
                padding: '4px 8px',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '11px',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: '4px'
              }}
            >
              <span>Focus Binding Site</span>
            </button>
            
            {/* Camera Type Selector */}
            <select
              value={cameraType}
              onChange={(e: any) => setCameraType(e.target.value)}
              style={{
                fontSize: '10px',
                padding: '2px 4px',
                border: 'none',
                background: 'transparent',
                color: 'var(--color-text-600)',
                cursor: 'pointer'
              }}
            >
              <option value="perspective">Perspective</option>
              <option value="orthographic">Orthographic</option>
            </select>

            {/* BG Selector */}
            <select
              value={bgColor}
              onChange={(e: any) => setBgColor(e.target.value)}
              style={{
                fontSize: '10px',
                padding: '2px 4px',
                border: 'none',
                background: 'transparent',
                color: 'var(--color-text-600)',
                cursor: 'pointer'
              }}
            >
              <option value="pale-grey">Grey BG</option>
              <option value="white">White BG</option>
              <option value="black">Black BG</option>
            </select>

            {/* Repr Style Selector */}
            <select
              value={representation}
              onChange={async (e: any) => {
                setRepresentation(e.target.value);
                if (receptorComponentRef.current) {
                  receptorComponentRef.current.removeAllRepresentations();
                  receptorComponentRef.current.addRepresentation(e.target.value, { colorScheme: 'chainid' });
                  receptorComponentRef.current.addRepresentation('licorice', { sele: 'hetero and not (water or ion)', colorScheme: 'element' });
                  receptorComponentRef.current.addRepresentation('spacefill', { sele: 'ion', scale: 0.3 });
                }
              }}
              style={{
                fontSize: '10px',
                padding: '2px 4px',
                border: 'none',
                background: 'transparent',
                color: 'var(--color-text-600)',
                cursor: 'pointer'
              }}
            >
              <option value="cartoon">Cartoon</option>
              <option value="surface">Surface</option>
              <option value="sticks">Sticks</option>
            </select>
          </div>

          {/* Actual 3D Canvas rendering target */}
          <div 
            ref={viewportRef} 
            style={{ width: '100%', height: '100%', minHeight: '300px', display: preparedReceptor ? 'block' : 'none' }} 
          />

          {!preparedReceptor && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', width: '100%' }}>
              <EmptyState
                icon={<Rotate3d size={24} />}
                title="No receptor loaded"
                description="Choose a preset receptor target or upload a custom target file to initialize the workspace."
                primaryAction={{
                  label: "Load ALS Preset",
                  onClick: () => loadReceptor('preset', 'als')
                }}
              />
            </div>
          )}

          {/* HTML Overlay Container for Pocket Residue Labels */}
          <div
            id="ngl-html-labels-container"
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: '100%',
              pointerEvents: 'none',
              overflow: 'hidden',
              zIndex: 3
            }}
          >
            {pocketLabels.map((lbl) => (
              <div
                key={lbl.id}
                id={`ngl-label-${lbl.id}`}
                style={{
                  position: 'absolute',
                  transform: 'translate(-50%, -50%)',
                  background: 'rgba(15, 23, 42, 0.85)',
                  border: '1px solid rgba(51, 65, 85, 0.8)',
                  borderRadius: '4px',
                  padding: '2px 6px',
                  color: '#ffffff',
                  fontSize: '10px',
                  fontWeight: 'bold',
                  whiteSpace: 'nowrap',
                  fontFamily: 'Inter, Roboto, system-ui, sans-serif',
                  boxShadow: '0 2px 4px rgba(0,0,0,0.3)',
                  display: 'none',
                  pointerEvents: 'none'
                }}
              >
                {lbl.text}
              </div>
            ))}
          </div>
        </div>

        {/* RIGHT COLUMN: LIGAND PREPARATION & DOCKING CONTROLS */}
        <div style={{
          width: '350px',
          borderLeft: '0.5px solid var(--color-border)',
          background: 'var(--color-bg)',
          display: 'flex',
          flexDirection: 'column',
          overflowY: 'auto',
          padding: '16px',
          gap: '16px'
        }} className="changelog-scroll">
          
          {/* Ligand Prep Panel */}
          <div style={{
            background: 'var(--color-surface)',
            border: '0.5px solid var(--color-border)',
            borderRadius: '8px',
            padding: '12px'
          }}>
            <h3 style={{ fontSize: '12px', fontWeight: 700, color: 'var(--color-text-900)', marginBottom: '8px' }}>4. Ligand Formulation</h3>
            
            <div style={{ display: 'flex', gap: '4px', marginBottom: '8px' }}>
              <button
                onClick={() => setLigandSource('workspace')}
                style={{
                  flex: 1,
                  fontSize: '9px',
                  padding: '4px',
                  borderRadius: '4px',
                  background: ligandSource === 'workspace' ? 'var(--color-brand-100)' : 'transparent',
                  border: '0.5px solid var(--color-border)',
                  color: ligandSource === 'workspace' ? 'var(--color-brand-900)' : 'var(--color-text-600)',
                  cursor: 'pointer'
                }}
              >
                💼 Workspace
              </button>
              <button
                onClick={() => setLigandSource('smiles')}
                style={{
                  flex: 1,
                  fontSize: '9px',
                  padding: '4px',
                  borderRadius: '4px',
                  background: ligandSource === 'smiles' ? 'var(--color-brand-100)' : 'transparent',
                  border: '0.5px solid var(--color-border)',
                  color: ligandSource === 'smiles' ? 'var(--color-brand-900)' : 'var(--color-text-600)',
                  cursor: 'pointer'
                }}
              >
                ✏️ SMILES
              </button>
              <button
                onClick={() => setLigandSource('upload')}
                style={{
                  flex: 1,
                  fontSize: '9px',
                  padding: '4px',
                  borderRadius: '4px',
                  background: ligandSource === 'upload' ? 'var(--color-brand-100)' : 'transparent',
                  border: '0.5px solid var(--color-border)',
                  color: ligandSource === 'upload' ? 'var(--color-brand-900)' : 'var(--color-text-600)',
                  cursor: 'pointer'
                }}
              >
                📁 Local File
              </button>
            </div>

            {ligandSource === 'workspace' && (
              <div style={{ marginBottom: '8px' }}>
                {workspaceCompound ? (
                  <div style={{ padding: '6px', background: 'var(--color-bg)', borderRadius: '4px', border: '0.5px solid var(--color-border)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px' }}>
                      <strong>Active Name:</strong>
                      <span>{workspaceCompound.name}</span>
                    </div>
                    <div style={{ fontSize: '8px', color: 'var(--color-text-400)', marginTop: '2px', wordBreak: 'break-all', fontFamily: 'var(--font-mono)' }}>
                      {workspaceCompound.smiles}
                    </div>
                  </div>
                ) : (
                  <span style={{ fontSize: '10px', color: 'var(--color-text-400)' }}>
                    No active compound selected in the workspace. Select one in the Library view.
                  </span>
                )}
              </div>
            )}

            {ligandSource === 'smiles' && (
              <div style={{ marginBottom: '8px' }}>
                <input
                  type="text"
                  placeholder="Enter SMILES string"
                  value={customSmiles}
                  onChange={(e) => setCustomSmiles(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '6px 8px',
                    borderRadius: '4px',
                    border: '0.5px solid var(--color-border)',
                    fontSize: '10px',
                    fontFamily: 'var(--font-mono)'
                  }}
                />
              </div>
            )}

            {ligandSource === 'upload' && (
              <div style={{ marginBottom: '8px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ display: 'flex', gap: '6px' }}>
                  <button
                    onClick={handlePickLigandFile}
                    className="workflow-btn-configure"
                    style={{
                      flex: 1,
                      fontSize: '10px',
                      padding: '6px',
                      fontWeight: 600,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '4px'
                    }}
                  >
                    <span>Browse SDF / SMILES...</span>
                  </button>
                </div>

                {uploadedFileName && (
                  <div style={{
                    padding: '6px',
                    background: 'var(--color-bg)',
                    borderRadius: '4px',
                    border: '0.5px solid var(--color-border)',
                    fontSize: '10px'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                      <strong style={{ color: 'var(--color-text-700)' }}>File Name:</strong>
                      <span style={{ color: 'var(--color-text-900)' }}>{uploadedFileName}</span>
                    </div>

                    {fileMols.length > 0 ? (
                      <div>
                        {fileMols.length > 1 ? (
                          <div style={{ marginTop: '6px' }}>
                            <label style={{ fontSize: '9px', color: 'var(--color-text-600)', display: 'block', marginBottom: '2px' }}>
                              Select Compound from File ({fileMols.length} found):
                            </label>
                            <select
                              value={selectedFileMolIdx}
                              onChange={(e) => {
                                const idx = parseInt(e.target.value) || 0;
                                setSelectedFileMolIdx(idx);
                                if (fileMols[idx]) {
                                  setLigandDisplayName(fileMols[idx].name || `Compound ${idx + 1}`);
                                }
                              }}
                              style={{
                                width: '100%',
                                padding: '4px',
                                fontSize: '10px',
                                borderRadius: '4px',
                                border: '0.5px solid var(--color-border)',
                                background: 'var(--color-surface)',
                                cursor: 'pointer'
                              }}
                            >
                              {fileMols.map((mol, idx) => (
                                <option key={idx} value={idx}>
                                  {mol.name || `Compound ${idx + 1}`} ({mol.smiles.slice(0, 15)}...)
                                </option>
                              ))}
                            </select>
                          </div>
                        ) : (
                          <div style={{ marginTop: '4px', borderTop: '0.5px solid var(--color-border)', paddingTop: '4px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                              <strong>Compound:</strong>
                              <span>{fileMols[0].name || 'Unnamed Compound'}</span>
                            </div>
                          </div>
                        )}
                        
                        <div style={{
                          fontSize: '8px',
                          color: 'var(--color-text-400)',
                          marginTop: '4px',
                          wordBreak: 'break-all',
                          fontFamily: 'var(--font-mono)',
                          background: 'rgba(0,0,0,0.02)',
                          padding: '4px',
                          borderRadius: '2px'
                        }}>
                          {fileMols[selectedFileMolIdx]?.smiles}
                        </div>
                      </div>
                    ) : (
                      <span style={{ fontSize: '10px', color: 'var(--color-text-400)' }}>
                        No molecules found in file.
                      </span>
                    )}
                  </div>
                )}
              </div>
            )}

            <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
              <input
                type="text"
                placeholder="Ligand display name"
                value={ligandDisplayName}
                onChange={(e) => setLigandDisplayName(e.target.value)}
                style={{
                  flex: 1,
                  padding: '4px 6px',
                  borderRadius: '4px',
                  border: '0.5px solid var(--color-border)',
                  fontSize: '10px'
                }}
              />
              <button
                onClick={handlePrepareLigand}
                disabled={preparingLigand || (ligandSource === 'smiles' && !customSmiles) || (ligandSource === 'upload' && fileMols.length === 0)}
                className="workflow-btn-configure"
                style={{ fontSize: '10px', padding: '0 12px', height: '24px', fontWeight: 700 }}
              >
                {preparingLigand ? 'Prepping...' : 'Prepare Ligand'}
              </button>
            </div>

            {preparingLigand && (
              <div style={{ marginTop: '8px' }}>
                <ProgressIndicator
                  variant="indeterminate"
                  label="Preparing ligand 3D structure and conformers..."
                />
              </div>
            )}

            {preparedLigand && (
              <div style={{
                marginTop: '8px',
                padding: '6px',
                background: 'var(--color-brand-100)',
                color: 'var(--color-brand-900)',
                borderRadius: '4px',
                fontSize: '9px',
                border: '0.5px solid var(--color-brand-50)'
              }}>
                ✅ Ligand prepared successfully! Rotatable bonds: {preparedLigand.metadata.rotatable_bonds}
              </div>
            )}
          </div>

          {/* Docking Controls */}
          <div style={{
            background: 'var(--color-surface)',
            border: '0.5px solid var(--color-border)',
            borderRadius: '8px',
            padding: '12px'
          }}>
            <h3 style={{ fontSize: '12px', fontWeight: 700, color: 'var(--color-text-900)', marginBottom: '8px' }}>5. Calculation Settings</h3>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '12px' }}>
              <div>
                <label style={{ fontSize: '9px', color: 'var(--color-text-600)', display: 'inline-flex', alignItems: 'center', gap: '4px', marginBottom: '3px' }}>
                  Exhaustiveness (Vina Accuracy)
                  <ContextualHelp topicId="docking.exhaustiveness" />
                </label>
                <div style={{ display: 'flex', gap: '4px' }}>
                  {[
                    { label: 'Fast (4)', value: 4 },
                    { label: 'Default (8)', value: 8 },
                    { label: 'Premium (32)', value: 32 }
                  ].map((item) => (
                    <button
                      key={item.value}
                      onClick={() => setExhaustiveness(item.value)}
                      style={{
                        flex: 1,
                        fontSize: '9px',
                        padding: '4px 6px',
                        borderRadius: '4px',
                        border: '0.5px solid var(--color-border)',
                        cursor: 'pointer',
                        background: exhaustiveness === item.value ? 'var(--color-brand-100)' : 'transparent',
                        color: exhaustiveness === item.value ? 'var(--color-brand-900)' : 'var(--color-text-600)',
                        fontWeight: exhaustiveness === item.value ? 700 : 500
                      }}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label style={{ fontSize: '9px', color: 'var(--color-text-600)', display: 'block', marginBottom: '3px' }}>Maximum Modes</label>
                <select
                  value={numModes}
                  onChange={(e) => setNumModes(parseInt(e.target.value))}
                  className="config-select"
                  style={{ fontSize: '10px', width: '100%', padding: '4px' }}
                >
                  <option value={1}>1 Pose</option>
                  <option value={3}>3 Poses</option>
                  <option value={5}>5 Poses</option>
                  <option value={9}>9 Poses</option>
                  <option value={15}>15 Poses</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: '9px', color: 'var(--color-text-600)', display: 'block', marginBottom: '3px' }}>Docking Algorithm Engine</label>
                <div style={{ display: 'flex', gap: '4px' }}>
                  <button
                    onClick={() => setDockingEngine('vina')}
                    style={{
                      flex: 1,
                      fontSize: '9px',
                      padding: '4px',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      background: dockingEngine === 'vina' ? 'var(--color-brand-100)' : 'transparent',
                      border: '0.5px solid var(--color-border)',
                      color: dockingEngine === 'vina' ? 'var(--color-brand-900)' : 'var(--color-text-600)'
                    }}
                  >
                    AutoDock Vina (Apache)
                  </button>
                  <button
                    onClick={() => setDockingEngine('gnina')}
                    style={{
                      flex: 1,
                      fontSize: '9px',
                      padding: '4px',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      background: dockingEngine === 'gnina' ? 'var(--color-brand-100)' : 'transparent',
                      border: '0.5px solid var(--color-border)',
                      color: dockingEngine === 'gnina' ? 'var(--color-brand-900)' : 'var(--color-text-600)'
                    }}
                  >
                    GNINA (CNN Rescore)
                  </button>
                </div>
              </div>
            </div>

            {isDocking ? (
              <div style={{ background: 'var(--color-bg)', padding: '10px', borderRadius: '6px', border: '0.5px solid var(--color-border)' }}>
                <ProgressIndicator
                  variant="determinate"
                  value={dockingProgress}
                  label="Docking Calculation..."
                  cancelable={true}
                  onCancel={handleCancelDocking}
                />
              </div>
            ) : (
              <button
                onClick={handleDock}
                disabled={!preparedReceptor || !preparedLigand}
                style={{
                  width: '100%',
                  padding: '8px 16px',
                  borderRadius: '6px',
                  background: 'linear-gradient(135deg, var(--color-brand-700), var(--color-brand-600))',
                  color: '#ffffff',
                  fontWeight: 700,
                  fontSize: '12px',
                  border: 'none',
                  cursor: 'pointer',
                  boxShadow: 'var(--shadow-sm)',
                  opacity: (!preparedReceptor || !preparedLigand) ? 0.6 : 1
                }}
              >
                🚀 Run Molecular Docking
              </button>
            )}
          </div>

          {/* Distance Measurements Panel */}
          {preparedReceptor && (
            <div style={{
              background: 'var(--color-surface)',
              border: '0.5px solid var(--color-border)',
              borderRadius: '8px',
              padding: '12px'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                <h3 style={{ fontSize: '12px', fontWeight: 700, color: 'var(--color-text-900)' }}>📏 Distance Meter</h3>
                <button
                  onClick={toggleMeasureMode}
                  className={measureMode ? 'workflow-btn-stop' : 'workflow-btn-configure'}
                  style={{ fontSize: '9px', padding: '2px 8px', height: '20px' }}
                >
                  {measureMode ? 'Cancel' : 'Measure Atoms'}
                </button>
              </div>

              {measuredDistances.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  {measuredDistances.map((dist) => (
                    <div 
                      key={dist.id}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        background: 'var(--color-bg)',
                        padding: '4px 8px',
                        borderRadius: '4px',
                        border: '0.5px solid var(--color-border)',
                        fontSize: '9px'
                      }}
                    >
                      <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <span>{dist.a1}</span>
                        <span style={{ color: 'var(--color-text-400)' }}>to {dist.a2}</span>
                      </div>
                      <span style={{ fontWeight: 700, color: 'var(--color-brand-900)', fontFamily: 'var(--font-mono)' }}>
                        {dist.value} Å
                      </span>
                    </div>
                  ))}
                  <button
                    onClick={() => setMeasuredDistances([])}
                    style={{
                      border: 'none',
                      background: 'transparent',
                      color: 'var(--color-red-700)',
                      fontSize: '8px',
                      cursor: 'pointer',
                      textAlign: 'right',
                      marginTop: '4px'
                    }}
                  >
                    Clear All
                  </button>
                </div>
              ) : (
                <span style={{ fontSize: '10px', color: 'var(--color-text-400)' }}>No active measurements.</span>
              )}
            </div>
          )}

          {/* Docking Poses List */}
          {dockingResult && (
            <div style={{
              background: 'var(--color-surface)',
              border: '0.5px solid var(--color-border)',
              borderRadius: '8px',
              padding: '12px'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <h3 style={{ fontSize: '12px', fontWeight: 700, color: 'var(--color-text-900)' }}>
                  Docked Pose Modes
                </h3>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '9px', color: 'var(--color-text-600)', cursor: 'pointer' }}>
                    <input 
                      type="checkbox" 
                      checked={clusterMode} 
                      onChange={(e) => setClusterMode(e.target.checked)} 
                      style={{ transform: 'scale(0.85)', cursor: 'pointer' }}
                    />
                    Cluster
                  </label>
                  {clusterMode && (
                    <select
                      value={rmsdCutoff}
                      onChange={(e) => setRmsdCutoff(parseFloat(e.target.value) || 2.0)}
                      style={{
                        fontSize: '9px',
                        padding: '2px 4px',
                        borderRadius: '3px',
                        border: '0.5px solid var(--color-border)',
                        background: 'var(--color-surface)',
                        cursor: 'pointer'
                      }}
                    >
                      <option value="1.0">1.0 Å</option>
                      <option value="1.5">1.5 Å</option>
                      <option value="2.0">2.0 Å</option>
                      <option value="3.0">3.0 Å</option>
                    </select>
                  )}
                  <button
                    onClick={() => setShowScoreInterpretation(true)}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: 'var(--color-text-400)',
                      cursor: 'pointer',
                      display: 'flex',
                      padding: 0
                    }}
                  >
                    <Info style={{ width: '13px', height: '13px' }} />
                  </button>
                </div>
              </div>

              {/* Energy caveats info label */}
              <div style={{
                fontSize: '9px',
                background: 'var(--color-blue-100)',
                color: 'var(--color-blue-700)',
                padding: '6px 8px',
                borderRadius: '4px',
                border: '0.5px solid var(--color-blue-50)',
                marginBottom: '8px',
                lineHeight: '1.3',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between'
              }}>
                <span>💡 kcal/mol scores are empirical free energy estimates, not absolute K<sub>d</sub> values.</span>
                <ContextualHelp topicId="docking.vina_score" />
              </div>

              {clusterMode && poseClusters.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {poseClusters.map((cluster, cIdx) => {
                    const clusterPoses = cluster.map(pIdx => {
                      const idx = dockingResult.poses.findIndex((p: any) => p.pose_index === pIdx);
                      return { pose: dockingResult.poses[idx], index: idx };
                    }).filter(item => item.pose !== undefined);

                    if (clusterPoses.length === 0) return null;
                    const representative = clusterPoses[0];

                    return (
                      <div key={cIdx} style={{
                        border: '0.5px solid var(--color-border)',
                        borderRadius: '6px',
                        background: 'rgba(0,0,0,0.01)',
                        padding: '6px'
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                          <span style={{ fontSize: '9px', fontWeight: 700, color: 'var(--color-brand-800)' }}>
                            Cluster #{cIdx + 1} ({clusterPoses.length} {clusterPoses.length === 1 ? 'mode' : 'modes'})
                          </span>
                          <span style={{ fontSize: '8px', color: 'var(--color-text-400)' }}>
                            Seed: Pose #{representative.pose.pose_index}
                          </span>
                        </div>
                        
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                          {clusterPoses.map(({ pose, index }) => {
                            const pScoreConfig = getScoreColor(pose.score_kcal_per_mol);
                            return (
                              <button
                                key={pose.pose_index}
                                onClick={() => loadPose(pose, index)}
                                style={{
                                  width: '100%',
                                  padding: '5px 8px',
                                  border: selectedPoseIndex === index ? '1.5px solid var(--color-brand-700)' : '0.5px solid var(--color-border)',
                                  background: selectedPoseIndex === index ? 'var(--color-brand-100)' : 'var(--color-surface)',
                                  borderRadius: '4px',
                                  cursor: 'pointer',
                                  display: 'flex',
                                  justifyContent: 'space-between',
                                  alignItems: 'center'
                                }}
                              >
                                <span style={{ fontSize: '9px', fontWeight: 600, color: 'var(--color-text-900)' }}>
                                  Pose #{pose.pose_index} {index === 0 && ' (Top Fit)'}
                                </span>
                                <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                                  {pose.rmsd_to_top !== null && (
                                    <span style={{ fontSize: '8px', color: 'var(--color-text-400)' }}>
                                      RMSD: {pose.rmsd_to_top.toFixed(2)} Å
                                    </span>
                                  )}
                                  <span className={`px-1.5 py-0.5 text-8px font-700 border rounded ${pScoreConfig.color}`}>
                                    {pose.score_kcal_per_mol.toFixed(1)} kcal/mol
                                  </span>
                                </div>
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  {dockingResult.poses.map((pose: any, idx: number) => {
                    const scoreConfig = getScoreColor(pose.score_kcal_per_mol);
                    return (
                      <button
                        key={pose.pose_index}
                        onClick={() => loadPose(pose, idx)}
                        style={{
                          width: '100%',
                          padding: '6px 8px',
                          border: selectedPoseIndex === idx ? '1.5px solid var(--color-brand-700)' : '0.5px solid var(--color-border)',
                          background: selectedPoseIndex === idx ? 'var(--color-brand-100)' : 'var(--color-bg)',
                          borderRadius: '4px',
                          cursor: 'pointer',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center'
                        }}
                      >
                        <span style={{ fontSize: '10px', fontWeight: 600, color: 'var(--color-text-900)' }}>
                          Pose #{pose.pose_index} {idx === 0 && ' (Top Fit)'}
                        </span>
                        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                          {pose.rmsd_to_top !== null && (
                            <span style={{ fontSize: '8px', color: 'var(--color-text-400)' }}>
                              RMSD: {pose.rmsd_to_top.toFixed(2)} Å
                            </span>
                          )}
                          <span className={`px-2 py-0.5 text-9px font-700 border rounded ${scoreConfig.color}`}>
                            {pose.score_kcal_per_mol.toFixed(1)} kcal/mol ({scoreConfig.label})
                          </span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* Interaction Fingerprint Details */}
          {selectedPoseIndex !== null && (
            <div style={{
              background: 'var(--color-surface)',
              border: '0.5px solid var(--color-border)',
              borderRadius: '8px',
              padding: '12px'
            }}>
              <h3 style={{ fontSize: '12px', fontWeight: 700, color: 'var(--color-text-900)', marginBottom: '8px' }}>
                Receptor-Ligand Contacts
              </h3>

              {loadingInteractions ? (
                <div style={{ fontSize: '10px', color: 'var(--color-text-600)', textAlign: 'center' }}>
                  <RefreshCw style={{ animation: 'spin 2s linear infinite', width: '12px', height: '12px', display: 'inline', marginRight: '6px' }} />
                  Computing interaction fingerprint...
                </div>
              ) : interactionFingerprint ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  
                  {/* HBonds Acc */}
                  {interactionFingerprint.hbond_acceptor && interactionFingerprint.hbond_acceptor.length > 0 && (
                    <div>
                      <span style={{ fontSize: '9px', fontWeight: 700, color: 'var(--color-text-900)' }}>Hydrogen Bond Acceptors</span>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', marginTop: '2px' }}>
                        {interactionFingerprint.hbond_acceptor.map((hb: any, i: number) => (
                          <button
                            key={i}
                            onClick={() => focusResidue(hb.residue)}
                            style={{
                              border: 'none',
                              background: 'var(--color-bg)',
                              textAlign: 'left',
                              padding: '3px 6px',
                              borderRadius: '3px',
                              fontSize: '9px',
                              cursor: 'pointer',
                              display: 'flex',
                              justifyContent: 'space-between',
                              color: 'var(--color-text-600)'
                            }}
                          >
                            <span>{hb.residue} ({hb.ligand_atom})</span>
                            <span style={{ fontFamily: 'var(--font-mono)' }}>{hb.distance.toFixed(2)} Å</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* HBonds Don */}
                  {interactionFingerprint.hbond_donor && interactionFingerprint.hbond_donor.length > 0 && (
                    <div>
                      <span style={{ fontSize: '9px', fontWeight: 700, color: 'var(--color-text-900)' }}>Hydrogen Bond Donors</span>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', marginTop: '2px' }}>
                        {interactionFingerprint.hbond_donor.map((hb: any, i: number) => (
                          <button
                            key={i}
                            onClick={() => focusResidue(hb.residue)}
                            style={{
                              border: 'none',
                              background: 'var(--color-bg)',
                              textAlign: 'left',
                              padding: '3px 6px',
                              borderRadius: '3px',
                              fontSize: '9px',
                              cursor: 'pointer',
                              display: 'flex',
                              justifyContent: 'space-between',
                              color: 'var(--color-text-600)'
                            }}
                          >
                            <span>{hb.residue} ({hb.ligand_atom})</span>
                            <span style={{ fontFamily: 'var(--font-mono)' }}>{hb.distance.toFixed(2)} Å</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Hydrophobic */}
                  {interactionFingerprint.hydrophobic && interactionFingerprint.hydrophobic.length > 0 && (
                    <div>
                      <span style={{ fontSize: '9px', fontWeight: 700, color: 'var(--color-text-900)' }}>Hydrophobic Contacts</span>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', marginTop: '2px' }}>
                        {interactionFingerprint.hydrophobic.map((hp: any, i: number) => (
                          <button
                            key={i}
                            onClick={() => focusResidue(hp.residue)}
                            style={{
                              border: 'none',
                              background: 'var(--color-bg)',
                              textAlign: 'left',
                              padding: '3px 6px',
                              borderRadius: '3px',
                              fontSize: '9px',
                              cursor: 'pointer',
                              display: 'flex',
                              justifyContent: 'space-between',
                              color: 'var(--color-text-600)'
                            }}
                          >
                            <span>{hp.residue} ({hp.ligand_atom})</span>
                            <span style={{ fontFamily: 'var(--font-mono)' }}>{hp.distance.toFixed(2)} Å</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Empty warning */}
                  {(!interactionFingerprint.hbond_acceptor?.length && 
                    !interactionFingerprint.hbond_donor?.length && 
                    !interactionFingerprint.hydrophobic?.length) && (
                    <span style={{ fontSize: '10px', color: 'var(--color-text-400)' }}>No close interactions mapped.</span>
                  )}
                </div>
              ) : (
                <span style={{ fontSize: '10px', color: 'var(--color-text-400)' }}>No interaction data loaded.</span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* BOTTOM COLLAPSIBLE DRAWER: JOB HISTORY */}
      {historyOpen && (
        <div style={{
          height: '240px',
          borderTop: '0.5px solid var(--color-border)',
          background: 'var(--color-surface)',
          display: 'flex',
          flexDirection: 'column',
          flexShrink: 0
        }}>
          {/* Header */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '8px 16px',
            borderBottom: '0.5px solid var(--color-border)',
            background: 'var(--color-bg)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--color-text-900)' }}>SQLite Calculation History Drawer</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <input
                  type="text"
                  placeholder="Search ligand SMILES..."
                  value={historySearch}
                  onChange={(e) => setHistorySearch(e.target.value)}
                  style={{
                    padding: '2px 6px',
                    borderRadius: '4px',
                    border: '0.5px solid var(--color-border)',
                    fontSize: '10px',
                    width: '180px'
                  }}
                />
              </div>
              <label style={{ display: 'flex', alignItems: 'center', gap: '3px', fontSize: '10px', cursor: 'pointer', color: 'var(--color-text-600)' }}>
                <input
                  type="checkbox"
                  checked={historyStarredOnly}
                  onChange={(e) => setHistoryStarredOnly(e.target.checked)}
                />
                Starred Only
              </label>
            </div>
            <button 
              onClick={() => setHistoryOpen(false)}
              style={{ border: 'none', background: 'transparent', cursor: 'pointer' }}
            >
              <ChevronDown style={{ width: '16px', height: '16px', color: 'var(--color-text-600)' }} />
            </button>
          </div>

          {/* List Scroll */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '8px 16px' }} className="changelog-scroll">
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--color-border)', textAlign: 'left', color: 'var(--color-text-400)' }}>
                  <th style={{ padding: '6px' }}>Receptor</th>
                  <th style={{ padding: '6px' }}>Ligand smiles</th>
                  <th style={{ padding: '6px' }}>Top Score</th>
                  <th style={{ padding: '6px' }}>Poses</th>
                  <th style={{ padding: '6px' }}>Time</th>
                  <th style={{ padding: '6px' }}>Completed At</th>
                  <th style={{ padding: '6px', textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {jobHistory.length === 0 ? (
                  <tr>
                    <td colSpan={7} style={{ textAlign: 'center', padding: '24px', color: 'var(--color-text-400)' }}>No docking records found.</td>
                  </tr>
                ) : (
                  jobHistory.map((job) => (
                    <tr key={job.job_id} style={{ borderBottom: '0.5px solid var(--color-border)' }} className="settings-tab-btn">
                      <td style={{ padding: '6px', fontWeight: 600, color: 'var(--color-text-900)' }}>
                        {job.receptor_display_name || job.receptor_id}
                      </td>
                      <td style={{ padding: '6px', maxWidth: '150px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontFamily: 'var(--font-mono)' }} title={job.ligand_smiles}>
                        {job.ligand_display_name || job.ligand_smiles}
                      </td>
                      <td style={{ padding: '6px', fontWeight: 700, color: 'var(--color-brand-900)' }}>
                        {job.top_score.toFixed(1)} kcal/mol
                      </td>
                      <td style={{ padding: '6px' }}>{job.num_poses} poses</td>
                      <td style={{ padding: '6px' }}>{job.elapsed_seconds.toFixed(0)}s</td>
                      <td style={{ padding: '6px', color: 'var(--color-text-400)' }}>{job.completed_at.replace('T', ' ').slice(0, 19)}</td>
                      <td style={{ padding: '6px', textAlign: 'right', display: 'flex', gap: '4px', justifyContent: 'flex-end', alignItems: 'center' }}>
                        <button
                          onClick={() => handleReloadJob(job.job_id)}
                          className="workflow-btn-configure"
                          style={{ fontSize: '9px', height: '22px', padding: '0 8px' }}
                        >
                          Reload
                        </button>
                        <button
                          onClick={() => handleStarJob(job.job_id, !job.starred)}
                          style={{
                            border: 'none',
                            background: 'transparent',
                            cursor: 'pointer',
                            color: job.starred ? '#eab308' : 'var(--color-text-400)'
                          }}
                        >
                          <Star style={{ width: '14px', height: '14px', fill: job.starred ? '#eab308' : 'none' }} />
                        </button>
                        <button
                          onClick={() => handleDeleteJob(job.job_id)}
                          style={{
                            border: 'none',
                            background: 'transparent',
                            cursor: 'pointer',
                            color: 'var(--color-red-700)'
                          }}
                        >
                          <Trash2 style={{ width: '13px', height: '13px' }} />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Floating score explanation modal */}
      {showScoreInterpretation && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0,0,0,0.5)',
          zIndex: 100,
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center'
        }}>
          <div style={{
            background: 'var(--color-surface)',
            border: '0.5px solid var(--color-border)',
            borderRadius: '8px',
            padding: '20px',
            maxWidth: '450px',
            boxShadow: 'var(--shadow-md)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
              <h4 style={{ fontSize: '13px', fontWeight: 700, color: 'var(--color-brand-900)' }}>Vina Score Guidelines</h4>
              <button onClick={() => setShowScoreInterpretation(false)} style={{ border: 'none', background: 'transparent', cursor: 'pointer' }}>
                <X style={{ width: '16px', height: '16px', color: 'var(--color-text-600)' }} />
              </button>
            </div>
            
            <p style={{ fontSize: '11px', color: 'var(--color-text-600)', lineHeight: '1.5', marginBottom: '12px' }}>
              Vina's score is an empirical estimate of binding free energy in kcal/mol. It is not a measured K_d or IC50. 
              The scoring function has known limitations on metal complexes, highly polarisable systems, and entropy-driven binding. 
              Use scores for <strong>relative</strong> comparison of poses or compounds, not absolute affinity.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', borderTop: '0.5px solid var(--color-border)', paddingTop: '10px' }}>
              <span style={{ fontSize: '10px', fontWeight: 600, color: 'var(--color-text-900)', marginBottom: '4px' }}>Visual Scoring Ranges:</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '10px' }}>
                <span className="px-2 py-0.5 text-9px font-700 border rounded bg-emerald-900 border-emerald-600 text-emerald-100 min-w-[70px] text-center">≤ -10.0</span>
                <span style={{ color: 'var(--color-text-600)' }}>Strong Binding Fit (high predicted affinity)</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '10px' }}>
                <span className="px-2 py-0.5 text-9px font-700 border rounded bg-amber-800 border-amber-500 text-amber-100 min-w-[70px] text-center">-10.0 to -8.0</span>
                <span style={{ color: 'var(--color-text-600)' }}>Moderate Binding Fit (satisfactory target interactions)</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '10px' }}>
                <span className="px-2 py-0.5 text-9px font-700 border rounded bg-orange-800 border-orange-500 text-orange-100 min-w-[70px] text-center">-8.0 to -6.0</span>
                <span style={{ color: 'var(--color-text-600)' }}>Weak Binding Fit (minimal target contacts)</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '10px' }}>
                <span className="px-2 py-0.5 text-9px font-700 border rounded bg-rose-950 border-rose-800 text-rose-100 min-w-[70px] text-center">&gt; -6.0</span>
                <span style={{ color: 'var(--color-text-600)' }}>Unfavorable (insufficient binding score)</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
