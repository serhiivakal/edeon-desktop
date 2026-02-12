import { useEffect, useRef, useState, useMemo, useCallback, useReducer } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { useUIStore } from '../store/uiStore';
import { useCompoundStore } from '../store/compoundStore';
import { useWorkflowStore } from '../store/workflowStore';
import { SceneOutliner } from '../components/viewer3d/SceneOutliner';
import type { SceneEntry, SceneSubEntry, ReprStyle } from '../types';

// NGL is a UMD build aliased in vite.config.ts — esbuild always wraps it as a default export
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore
import NglModule from 'ngl';
import * as NGL from 'ngl';

// Attach debug window logger for easy Tauri DevTools inspections
(window as any).__nglDebug = { default: NglModule, namespace: NGL };

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
if (!NglObj) {
  console.error('[3D Viewer] NGL module did not resolve. Module shapes:', {
    NglModule, NGL, windowNGL: (window as any).NGL,
  });
}

import { 
  Dna, 
  Rotate3d, 
  Camera, 
  RefreshCw, 
  Maximize2, 
  Sliders, 
  Activity,
  Layers,
  Sparkles,
  Info,
  Target
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

const ION_RESNAMES = new Set([
  'NA','K','MG','CA','ZN','FE','FE2','FE3','MN','CU','CO','NI','CL','BR','I','SO4','PO4'
]);
const COFACTOR_RESNAMES = new Set([
  'HEM','HEC','FAD','FMN','NAD','NAP','NDP','SAM','COA','PLP','BTN','TPP'
]);

function parseStructureToSubEntries(component: any): SceneSubEntry[] {
  const out: SceneSubEntry[] = [];
  const struct = component.structure;
  if (!struct) return out;

  // ---- 1. Protein chains ----
  const chains = new Map<string, number>();   // chainname -> residueCount
  struct.eachChain((cp: any) => {
    let proteinResidues = 0;
    cp.eachResidue((rp: any) => { if (rp.isProtein()) proteinResidues++; });
    if (proteinResidues > 0) {
      chains.set(cp.chainname || 'X', proteinResidues);
    }
  });
  for (const [cn, count] of chains) {
    out.push({
      id: `chain-${cn}-${crypto.randomUUID()}`,
      type: 'chain',
      name: `Chain ${cn}`,
      selection: `:${cn} and protein`,
      visible: true,
      repr: 'cartoon',
      color: '__chainid',     // sentinel: use chainid color scheme
      count,
    });
  }

  // ---- 2. Ligands & cofactors (grouped by resname) ----
  const ligandGroups = new Map<string, number>();
  const cofactorGroups = new Map<string, number>();
  struct.eachResidue((rp: any) => {
    if (!rp.hetero || rp.isWater()) return;
    const rn = rp.resname;
    if (ION_RESNAMES.has(rn)) return;
    if (COFACTOR_RESNAMES.has(rn)) {
      cofactorGroups.set(rn, (cofactorGroups.get(rn) || 0) + 1);
    } else {
      ligandGroups.set(rn, (ligandGroups.get(rn) || 0) + 1);
    }
  });
  for (const [rn, n] of ligandGroups) {
    out.push({
      id: `lig-${rn}-${crypto.randomUUID()}`,
      type: 'ligand',
      name: n > 1 ? `${rn} (×${n})` : rn,
      selection: `[${rn}]`,
      visible: true,
      repr: 'ball+stick',
      color: '#10b981',
      count: n,
    });
  }
  for (const [rn, n] of cofactorGroups) {
    out.push({
      id: `cof-${rn}-${crypto.randomUUID()}`,
      type: 'cofactor',
      name: n > 1 ? `${rn} (×${n})` : rn,
      selection: `[${rn}]`,
      visible: true,
      repr: 'licorice',
      color: '#a855f7',
      count: n,
    });
  }

  // ---- 3. Ions ----
  const ions = new Map<string, number>();
  struct.eachResidue((rp: any) => {
    if (rp.hetero && ION_RESNAMES.has(rp.resname)) {
      ions.set(rp.resname, (ions.get(rp.resname) || 0) + 1);
    }
  });
  for (const [rn, n] of ions) {
    out.push({
      id: `ion-${rn}-${crypto.randomUUID()}`,
      type: 'ion',
      name: `${rn}${n > 1 ? ` (×${n})` : ''}`,
      selection: `[${rn}]`,
      visible: true,
      repr: 'spacefill',
      color: '#fbbf24',
      count: n,
    });
  }

  // ---- 4. Waters (single bucket, off by default) ----
  let waterCount = 0;
  struct.eachResidue((rp: any) => { if (rp.isWater()) waterCount++; });
  if (waterCount > 0) {
    out.push({
      id: `water-${crypto.randomUUID()}`,
      type: 'water',
      name: `Water (${waterCount})`,
      selection: 'water',
      visible: false,
      repr: 'spacefill',
      color: '#38bdf8',
      count: waterCount,
    });
  }

  return out;
}

type SceneAction =
  | { t: 'add';     entry: SceneEntry }
  | { t: 'remove';  id: string }
  | { t: 'clear';   stageId?: 1 | 2 }
  | { t: 'toggleEntry';   id: string }
  | { t: 'toggleSub';     entryId: string; subId: string }
  | { t: 'expand';        id: string }
  | { t: 'setRepr';       entryId: string; subId: string; repr: ReprStyle }
  | { t: 'setColor';      entryId: string; subId: string; color: string }
  | { t: 'setEntryName';  id: string; name: string };

function sceneReducer(state: SceneEntry[], a: SceneAction): SceneEntry[] {
  switch (a.t) {
    case 'add':    return [...state, a.entry];
    case 'remove': return state.filter(e => e.id !== a.id);
    case 'clear':  return a.stageId ? state.filter(e => e.stageId !== a.stageId) : [];
    case 'toggleEntry':
      return state.map(e => e.id === a.id ? { ...e, visible: !e.visible } : e);
    case 'expand':
      return state.map(e => e.id === a.id ? { ...e, expanded: !e.expanded } : e);
    case 'toggleSub':
      return state.map(e => e.id !== a.entryId ? e : {
        ...e,
        children: e.children.map(c =>
          c.id === a.subId ? { ...c, visible: !c.visible } : c),
      });
    case 'setRepr':
      return state.map(e => e.id !== a.entryId ? e : {
        ...e,
        children: e.children.map(c =>
          c.id === a.subId ? { ...c, repr: a.repr } : c),
      });
    case 'setColor':
      return state.map(e => e.id !== a.entryId ? e : {
        ...e,
        children: e.children.map(c =>
          c.id === a.subId ? { ...c, color: a.color } : c),
      });
    case 'setEntryName':
      return state.map(e => e.id === a.id ? { ...e, name: a.name } : e);
    default: return state;
  }
}

export function Viewer3dView() {
  const selectedCompoundId = useUIStore((s) => s.selectedCompoundId);
  const theme = useUIStore((s) => s.theme);
  const libraryCompounds = useCompoundStore((s) => s.compounds);
  const workflowResults = useWorkflowStore((s) => s.results);

  // Retrieve selected compound details
  const activeCompound = useMemo(() => {
    const fromWorkflows = workflowResults.find((c) => c.id === selectedCompoundId);
    if (fromWorkflows) return fromWorkflows;
    return libraryCompounds.find((c) => c.id === selectedCompoundId) || null;
  }, [selectedCompoundId, libraryCompounds, workflowResults]);

  // Viewport and NGL instance references with 'any' types to prevent compiler mismatches
  const viewportRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<any>(null);
  const proteinCompRef = useRef<any>(null);
  const ligandCompRef = useRef<any>(null);
  const pharmacophoreShapesRef = useRef<any>(null);

  // Split Screen viewports and coordinate refs
  const viewport2Ref = useRef<HTMLDivElement>(null);
  const stage2Ref = useRef<any>(null);
  const protein2CompRef = useRef<any>(null);
  const ligand2CompRef = useRef<any>(null);
  const pharmacophore2ShapesRef = useRef<any>(null);

  // Split Screen states
  const [splitScreen, setSplitScreen] = useState(false);
  const [comparisonCompoundId, setComparisonCompoundId] = useState<string | null>(null);
  const [docking2Loading, setDocking2Loading] = useState(false);
  const [hasDocked2Ligand, setHasDocked2Ligand] = useState(false);

  // Retrieve comparison compound details
  const comparisonCompound = useMemo(() => {
    if (!comparisonCompoundId) return null;
    const fromWorkflows = workflowResults.find((c) => c.id === comparisonCompoundId);
    if (fromWorkflows) return fromWorkflows;
    return libraryCompounds.find((c) => c.id === comparisonCompoundId) || null;
  }, [comparisonCompoundId, libraryCompounds, workflowResults]);

  // Gather all available library and workflow compounds for side-by-side split screen
  const allAvailableCompounds = useMemo(() => {
    const seenSmiles = new Set<string>();
    const list: any[] = [];
    
    workflowResults.forEach((c) => {
      if (c.smiles && !seenSmiles.has(c.smiles)) {
        seenSmiles.add(c.smiles);
        list.push(c);
      }
    });

    libraryCompounds.forEach((c) => {
      if (c.smiles && !seenSmiles.has(c.smiles)) {
        seenSmiles.add(c.smiles);
        list.push(c);
      }
    });

    return list;
  }, [libraryCompounds, workflowResults]);
  
  // Race-condition guard: monotonically increasing load ID
  const loadIdRef = useRef(0);

  // 3D Visual States
  const [selectedPresetId, setSelectedPresetId] = useState('als');
  const [loading, setLoading] = useState(false);
  const [dockingLoading, setDockingLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Scene tree outliner state & NGL handles
  const [scene, dispatch] = useReducer(sceneReducer, []);
  const componentMap = useRef<Map<string, any>>(new Map());
  const reprMap = useRef<Map<string, any>>(new Map()); // key = `${entryId}::${subId}`

  // Interaction Solvers
  const [showHBonds, setShowHBonds] = useState(true);
  const [showHydrophobic, setShowHydrophobic] = useState(true);
  const [showAromaticStacking, setShowAromaticStacking] = useState(true);

  // Pharmacophore Overlays
  const [showPharmacophores, setShowPharmacophores] = useState(false);

  // Viewport Settings
  const [isSpinning, setIsSpinning] = useState(false);
  const [cameraType, setCameraType] = useState<'perspective' | 'orthographic'>('perspective');
  const [bgColor, setBgColor] = useState<'white' | 'pale-grey' | 'black'>('pale-grey');
  const [customPdbId, setCustomPdbId] = useState('');
  const [customLoadedPdb, setCustomLoadedPdb] = useState<string | null>(null);
  const [localPdbName, setLocalPdbName] = useState<string | null>(null);
  // Track whether a ligand has been docked (for UI state, since useRef doesn't trigger re-renders)
  const [hasDockedLigand, setHasDockedLigand] = useState(false);

  const activePreset = useMemo(() => {
    if (selectedPresetId === 'custom' && customLoadedPdb) {
      return {
        id: 'custom',
        name: `Custom Target (${customLoadedPdb})`,
        pdbId: customLoadedPdb,
        target: 'User Custom Protein',
        description: 'Successfully downloaded and rendered custom macromolecular coordinate structure from RCSB PDB.'
      };
    }
    if (selectedPresetId === 'local' && localPdbName) {
      return {
        id: 'local',
        name: `Local: ${localPdbName}`,
        pdbId: 'LOCAL',
        target: 'Local PDB File',
        description: 'Rendered local macromolecular target structure loaded from your computer drive.'
      };
    }
    return RECEPTOR_PRESETS.find(p => p.id === selectedPresetId) || RECEPTOR_PRESETS[0];
  }, [selectedPresetId, customLoadedPdb, localPdbName]);

  // Scene Graph Representation Reconciler
  const reprKey = useCallback((entryId: string, subId: string) => `${entryId}::${subId}`, []);

  const syncScene = useCallback((currentScene: SceneEntry[]) => {
    for (const entry of currentScene) {
      const comp = componentMap.current.get(entry.id);
      if (!comp) continue;

      for (const sub of entry.children) {
        const key = reprKey(entry.id, sub.id);
        const existing = reprMap.current.get(key);
        const shouldShow = entry.visible && sub.visible && sub.repr !== 'hidden';

        // Always remove first — simpler than diffing parameters.
        if (existing) {
          try { comp.removeRepresentation(existing); } catch (e) {
            console.warn('[3D Viewer] removeRepresentation failed:', e);
          }
          reprMap.current.delete(key);
        }

        if (!shouldShow) continue;

        const params: any = { sele: sub.selection, opacity: 1.0 };
        if (sub.color === '__chainid') {
          params.colorScheme = 'chainid';
        } else if (sub.color === '__element') {
          params.colorScheme = 'element';
        } else {
          params.colorValue = sub.color;
        }

        if (sub.repr === 'surface') {
          params.colorScheme = 'electrostatic';
          params.opacity = 0.45;
        }

        try {
          const r = comp.addRepresentation(sub.repr, params);
          reprMap.current.set(key, r);
        } catch (err) {
          console.warn(`[Scene] addRepresentation failed for ${sub.name}:`, err);
        }
      }
    }
  }, [reprKey]);

  useEffect(() => {
    syncScene(scene);
  }, [scene, syncScene]);

  // Remove Entry Handler
  const removeEntry = useCallback((entryId: string) => {
    const comp = componentMap.current.get(entryId);
    if (comp && stageRef.current) {
      try { 
        stageRef.current.removeComponent(comp); 
      } catch (e) {
        console.warn('[3D Viewer] removeComponent from stage 1 failed:', e);
      }
    }
    if (comp && stage2Ref.current) {
      try { 
        stage2Ref.current.removeComponent(comp); 
      } catch (e) {
        console.warn('[3D Viewer] removeComponent from stage 2 failed:', e);
      }
    }
    componentMap.current.delete(entryId);
    for (const key of [...reprMap.current.keys()]) {
      if (key.startsWith(`${entryId}::`)) {
        reprMap.current.delete(key);
      }
    }

    if (proteinCompRef.current === comp) proteinCompRef.current = null;
    if (ligandCompRef.current === comp) ligandCompRef.current = null;
    if (protein2CompRef.current === comp) protein2CompRef.current = null;
    if (ligand2CompRef.current === comp) ligand2CompRef.current = null;

    dispatch({ t: 'remove', id: entryId });
  }, []);


  // Initialize NGL Stage 1
  useEffect(() => {
    if (!viewportRef.current) return;

    if (!NglObj || typeof NglObj.Stage !== 'function') {
      setError(
        'NGL.js failed to load. Check tauri.conf.json — the UMD alias for "ngl" might not expose Stage, ' +
        'or Tauri CSP might be blocking Web Workers. Open DevTools console for details.'
      );
      return;
    }

    let stage: any;
    let cancelled = false;

    // Wait for the browser to commit layout before measuring
    const raf = requestAnimationFrame(() => {
      if (cancelled || !viewportRef.current) return;

      const rect = viewportRef.current.getBoundingClientRect();
      console.log('[3D Viewer] Viewport size at init:', rect.width, '×', rect.height);

      if (rect.width < 10 || rect.height < 10) {
        setError(
          `Viewport has near-zero size (${rect.width.toFixed(0)}×${rect.height.toFixed(0)}). ` +
          `Check that .viewer-3d-layout has a non-zero parent height.`
        );
        return;
      }

      try {
        // Clean up previous stage
        if (stageRef.current) {
          try { stageRef.current.dispose(); } catch (e) { console.warn('[3D Viewer] Stage 1 dispose failed:', e); }
        }

        const initialTheme = useUIStore.getState().theme;
        const hex = bgColor === 'white' ? '#ffffff' : bgColor === 'pale-grey' ? (initialTheme === 'dark' ? '#09090b' : '#f1f5f9') : '#000000';
        stage = new NglObj.Stage(viewportRef.current, {
          backgroundColor: hex,
          tooltip: true,
        });
        stageRef.current = stage;
        
        // Initial load of default preset
        loadReceptorFromUrl(RECEPTOR_PRESETS[0].pdbId);
      } catch (err: any) {
        console.error('[3D Viewer] Stage 1 constructor threw:', err);
        setError(`NGL Stage 1 init failed: ${err?.message ?? err}`);
      }
    });

    // Handle viewport resize
    const handleResize = () => {
      if (stageRef.current) {
        stageRef.current.handleResize();
      }
      if (stage2Ref.current) {
        stage2Ref.current.handleResize();
      }
    };
    window.addEventListener('resize', handleResize);

    // Also listen for ResizeObserver on the container for layout changes
    let resizeObserver: ResizeObserver | null = null;
    if (viewportRef.current) {
      resizeObserver = new ResizeObserver(() => {
        if (stageRef.current) {
          stageRef.current.handleResize();
        }
        if (stage2Ref.current) {
          stage2Ref.current.handleResize();
        }
      });
      resizeObserver.observe(viewportRef.current);
    }

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', handleResize);
      resizeObserver?.disconnect();
      if (stageRef.current) {
        try { stageRef.current.dispose(); } catch (e) { console.warn('[3D Viewer] Stage 1 cleanup dispose failed:', e); }
        stageRef.current = null;
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Initialize NGL Stage 2 (when splitScreen is active)
  useEffect(() => {
    if (!splitScreen) {
      if (stage2Ref.current) {
        try { stage2Ref.current.dispose(); } catch (e) { console.warn('[3D Viewer] Stage 2 split-screen disable dispose failed:', e); }
        stage2Ref.current = null;
      }
      protein2CompRef.current = null;
      ligand2CompRef.current = null;
      pharmacophore2ShapesRef.current = null;
      setHasDocked2Ligand(false);
      return;
    }

    if (!viewport2Ref.current) return;

    if (!NglObj || typeof NglObj.Stage !== 'function') return;

    let stage2: any;
    let cancelled = false;

    const raf2 = requestAnimationFrame(() => {
      if (cancelled || !viewport2Ref.current) return;

      const rect = viewport2Ref.current.getBoundingClientRect();
      if (rect.width < 10 || rect.height < 10) return;

      try {
        if (stage2Ref.current) {
          try { stage2Ref.current.dispose(); } catch (e) { console.warn('[3D Viewer] Stage 2 pre-init dispose failed:', e); }
        }

        const initialTheme = useUIStore.getState().theme;
        const hex = bgColor === 'white' ? '#ffffff' : bgColor === 'pale-grey' ? (initialTheme === 'dark' ? '#09090b' : '#f1f5f9') : '#000000';
        stage2 = new NglObj.Stage(viewport2Ref.current, {
          backgroundColor: hex,
          tooltip: true
        });
        stage2Ref.current = stage2;

        const syncReceptorToStage2 = async () => {
          try {
            const pdbIdToLoad = activePreset.pdbId === 'CUSTOM' && customLoadedPdb ? customLoadedPdb : activePreset.pdbId;
            if (pdbIdToLoad === 'LOCAL') return;

            const { content, ext } = await fetchPdbContent(pdbIdToLoad);
            if (!stage2Ref.current || !splitScreen) return;

            const blob = new Blob([content], { type: 'text/plain' });
            const component = await stage2Ref.current.loadFile(blob, {
              ext,
              defaultRepresentation: false
            });

            protein2CompRef.current = component;

            const oldStage2Protein = scene.find(e => e.stageId === 2 && e.type === 'protein');
            if (oldStage2Protein) {
              removeEntry(oldStage2Protein.id);
            }

            const entryId2 = crypto.randomUUID();
            componentMap.current.set(entryId2, component);
            dispatch({
              t: 'add',
              entry: {
                id: entryId2,
                type: 'protein',
                name: activePreset.name || pdbIdToLoad,
                pdbId: pdbIdToLoad,
                expanded: true,
                visible: true,
                stageId: 2,
                children: parseStructureToSubEntries(component),
              },
            });

            setTimeout(() => {
              try {
                focusPocket();
              } catch (e) {
                console.warn('[3D Viewer] Stage 2 sync focusPocket failed:', e);
              }
            }, 150);

            if (comparisonCompoundId) {
              dockComparisonCompound();
            }
          } catch (err) {
            console.warn('[3D Viewer] Stage 2 sync receptor error:', err);
          }
        };

        syncReceptorToStage2();
      } catch (err) {
        console.warn('[3D Viewer] Stage 2 init failed:', err);
      }
    });

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf2);
      if (stage2Ref.current) {
        try { stage2Ref.current.dispose(); } catch (e) { console.warn('[3D Viewer] Stage 2 cleanup dispose failed:', e); }
        stage2Ref.current = null;
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [splitScreen]);

  // Synchronous Camera Rotation (Stage 1 <-> Stage 2)
  useEffect(() => {
    if (!stageRef.current || !stage2Ref.current || !splitScreen) return;

    let isSyncing = false;

    const handleOrientation1 = (orientation: any) => {
      if (isSyncing) return;
      isSyncing = true;
      try {
        stage2Ref.current.viewer.setOrientation(orientation);
      } catch (e) { console.warn('[3D Viewer] Synchronize stage 2 camera failed:', e); }
      isSyncing = false;
    };

    const handleOrientation2 = (orientation: any) => {
      if (isSyncing) return;
      isSyncing = true;
      try {
        stageRef.current.viewer.setOrientation(orientation);
      } catch (e) { console.warn('[3D Viewer] Synchronize stage 1 camera failed:', e); }
      isSyncing = false;
    };

    stageRef.current.viewer.signals.orientationChanged.add(handleOrientation1);
    stage2Ref.current.viewer.signals.orientationChanged.add(handleOrientation2);

    return () => {
      try {
        stageRef.current?.viewer.signals.orientationChanged.remove(handleOrientation1);
        stage2Ref.current?.viewer.signals.orientationChanged.remove(handleOrientation2);
      } catch (e) { console.warn('[3D Viewer] Remove orientation signals failed:', e); }
    };
  }, [splitScreen, loading]);

  // Update Spin
  useEffect(() => {
    if (stageRef.current) {
      try { stageRef.current.setSpin(isSpinning); } catch (e) { console.warn('[3D Viewer] Stage 1 setSpin failed:', e); }
    }
    if (stage2Ref.current && splitScreen) {
      try { stage2Ref.current.setSpin(isSpinning); } catch (e) { console.warn('[3D Viewer] Stage 2 setSpin failed:', e); }
    }
  }, [isSpinning, splitScreen]);

  // Update Camera Type
  useEffect(() => {
    if (stageRef.current) {
      try { stageRef.current.setParameters({ cameraType }); } catch (e) { console.warn('[3D Viewer] Stage 1 cameraType setParameters failed:', e); }
    }
    if (stage2Ref.current && splitScreen) {
      try { stage2Ref.current.setParameters({ cameraType }); } catch (e) { console.warn('[3D Viewer] Stage 2 cameraType setParameters failed:', e); }
    }
  }, [cameraType, splitScreen]);

  // Update Background Color
  useEffect(() => {
    const hex = bgColor === 'white' ? '#ffffff' : bgColor === 'pale-grey' ? (theme === 'dark' ? '#09090b' : '#f1f5f9') : '#000000';
    if (stageRef.current) {
      try { stageRef.current.setParameters({ backgroundColor: hex }); } catch (e) { console.warn('[3D Viewer] Stage 1 backgroundColor setParameters failed:', e); }
    }
    if (stage2Ref.current && splitScreen) {
      try { stage2Ref.current.setParameters({ backgroundColor: hex }); } catch (e) { console.warn('[3D Viewer] Stage 2 backgroundColor setParameters failed:', e); }
    }
  }, [bgColor, splitScreen, theme]);

  // Attempt to fetch a PDB structure with fallback formats
  const fetchPdbContent = async (pdbId: string): Promise<{ content: string; ext: string }> => {
    const pdbIdUpper = pdbId.toUpperCase();
    
    // Try PDB format first (smaller, more compatible)
    const urls = [
      { url: `https://files.rcsb.org/download/${pdbIdUpper}.pdb`, ext: 'pdb' },
      { url: `https://files.rcsb.org/download/${pdbIdUpper}.cif`, ext: 'cif' },
      // Fallback to compressed formats
      { url: `https://files.rcsb.org/download/${pdbIdUpper}.pdb.gz`, ext: 'pdb' },
    ];

    let lastError = '';
    for (const { url, ext } of urls) {
      try {
        const response = await fetch(url);
        if (response.ok) {
          const text = await response.text();
          if (text && text.length > 100) {
            return { content: text, ext };
          }
        }
        lastError = `HTTP ${response.status} from ${url}`;
      } catch (err: any) {
        lastError = `Network error fetching ${url}: ${err.message || err}`;
        continue;
      }
    }

    throw new Error(`Could not download structure ${pdbIdUpper}. ${lastError}`);
  };

  // Focus camera on the whole protein (all atoms currently loaded)
  const focusWholeProtein = () => {
    if (!stageRef.current) return;
    try {
      stageRef.current.autoView(800);
      if (stage2Ref.current && splitScreen) {
        stage2Ref.current.autoView(800);
      }
    } catch (err) {
      console.warn('[3D Viewer] focusWholeProtein failed:', err);
    }
  };

  // Focus camera on ligand plus a 6 Angstrom surrounding pocket
  const focusBindingSite = () => {
    if (!stageRef.current) return;
    try {
      const targetComps: any[] = [];
      if (ligandCompRef.current) targetComps.push(ligandCompRef.current);
      if (proteinCompRef.current) targetComps.push(proteinCompRef.current);

      if (targetComps.length === 0) {
        stageRef.current.autoView(800);
      } else {
        // Build a selection that covers ligand atoms + 6A around them,
        // then focus on the bounding box of that selection.
        const seleParts: string[] = [];
        targetComps.forEach((comp) => {
          const struct = comp?.structure;
          if (!struct) return;
          // For each ligand-like residue in this component, create an `around` clause
          const ligandResnames = new Set<string>();
          struct.eachResidue((rp: any) => {
            if (rp.hetero && !rp.isWater() && !ION_RESNAMES.has(rp.resname)) {
              ligandResnames.add(rp.resname);
            }
          });
          if (ligandResnames.size > 0) {
            const resList = Array.from(ligandResnames).map(r => `[${r}]`).join(' or ');
            seleParts.push(`((${resList}) around 6)`);
          }
        });

        const sele = seleParts.length > 0 ? seleParts.join(' or ') : '*';
        const selectionObj = new NglObj.Selection(sele);
        // Use first component's structure view as the spatial reference
        const refComp = ligandCompRef.current || proteinCompRef.current;
        const view = refComp.structure.getView(selectionObj);
        if (view && view.center && !isNaN(view.center.x)) {
          stageRef.current.animationControls.zoomMove(view.center, 30.0, 800);
        } else {
          stageRef.current.autoView(800);
        }
      }

      if (stage2Ref.current && splitScreen) {
        const targetComps2: any[] = [];
        if (ligand2CompRef.current) targetComps2.push(ligand2CompRef.current);
        if (protein2CompRef.current) targetComps2.push(protein2CompRef.current);

        if (targetComps2.length === 0) {
          stage2Ref.current.autoView(800);
        } else {
          const seleParts2: string[] = [];
          targetComps2.forEach((comp) => {
            const struct = comp?.structure;
            if (!struct) return;
            const ligandResnames = new Set<string>();
            struct.eachResidue((rp: any) => {
              if (rp.hetero && !rp.isWater() && !ION_RESNAMES.has(rp.resname)) {
                ligandResnames.add(rp.resname);
              }
            });
            if (ligandResnames.size > 0) {
              const resList = Array.from(ligandResnames).map(r => `[${r}]`).join(' or ');
              seleParts2.push(`((${resList}) around 6)`);
            }
          });

          const sele2 = seleParts2.length > 0 ? seleParts2.join(' or ') : '*';
          const selectionObj2 = new NglObj.Selection(sele2);
          const refComp2 = ligand2CompRef.current || protein2CompRef.current;
          const view2 = refComp2.structure.getView(selectionObj2);
          if (view2 && view2.center && !isNaN(view2.center.x)) {
            stage2Ref.current.animationControls.zoomMove(view2.center, 30.0, 800);
          } else {
            stage2Ref.current.autoView(800);
          }
        }
      }
    } catch (err) {
      try { stageRef.current.autoView(500); } catch (e) { console.warn('[3D Viewer] focusBindingSite fallback autoView failed:', e); }
      if (stage2Ref.current && splitScreen) {
        try { stage2Ref.current.autoView(500); } catch (e) { console.warn('[3D Viewer] focusBindingSite stage 2 fallback autoView failed:', e); }
      }
    }
  };

  // Zoom to Pocket center (legacy convenience: now focuses the binding site)
  const focusPocket = () => {
    focusBindingSite();
  };

  // Load target receptor structure from RCSB PDB
  const loadReceptorFromUrl = async (pdbId: string) => {
    if (!stageRef.current) return;
    
    const thisLoadId = ++loadIdRef.current;
    setLoading(true);
    setError(null);

    try {
      // Clear all existing components
      stageRef.current.removeAllComponents();
      proteinCompRef.current = null;
      ligandCompRef.current = null;
      pharmacophoreShapesRef.current = null;
      setHasDockedLigand(false);

      if (stage2Ref.current) {
        stage2Ref.current.removeAllComponents();
        protein2CompRef.current = null;
        ligand2CompRef.current = null;
        pharmacophore2ShapesRef.current = null;
        setHasDocked2Ligand(false);
      }

      dispatch({ t: 'clear' });
      componentMap.current.clear();
      reprMap.current.clear();

      // Fetch the PDB content with fallbacks
      const { content, ext } = await fetchPdbContent(pdbId);

      // Guard against stale loads (user switched preset while fetching)
      if (thisLoadId !== loadIdRef.current) {
        console.log(`[3D Viewer] Discarding stale load for ${pdbId} (id ${thisLoadId} vs ${loadIdRef.current})`);
        return;
      }
      
      if (!stageRef.current) return;

      // Load from Blob to avoid any CORS issues
      const blob = new Blob([content], { type: 'text/plain' });
      const component = await stageRef.current.loadFile(blob, { 
        ext,
        defaultRepresentation: false 
      });
      
      // Guard again after async
      if (thisLoadId !== loadIdRef.current || !stageRef.current) return;

      proteinCompRef.current = component;

      const entryId = crypto.randomUUID();
      componentMap.current.set(entryId, component);
      dispatch({
        t: 'add',
        entry: {
          id: entryId,
          type: 'protein',
          name: activePreset.name || pdbId,
          pdbId,
          expanded: true,
          visible: true,
          stageId: 1,
          children: parseStructureToSubEntries(component),
        },
      });

      // Load into Stage 2 if active and available
      if (stage2Ref.current && splitScreen) {
        const blob2 = new Blob([content], { type: 'text/plain' });
        const component2 = await stage2Ref.current.loadFile(blob2, {
          ext,
          defaultRepresentation: false
        });
        
        if (thisLoadId !== loadIdRef.current || !stage2Ref.current) return;
        protein2CompRef.current = component2;
        
        const entryId2 = crypto.randomUUID();
        componentMap.current.set(entryId2, component2);
        dispatch({
          t: 'add',
          entry: {
            id: entryId2,
            type: 'protein',
            name: activePreset.name || pdbId,
            pdbId,
            expanded: true,
            visible: true,
            stageId: 2,
            children: parseStructureToSubEntries(component2),
          },
        });
      }

      setTimeout(() => {
        try {
          focusWholeProtein();
        } catch (e) {
          console.warn('[3D Viewer] delayed focusWholeProtein failed:', e);
        }
      }, 150);
    } catch (err: any) {
      // Only show error if this is still the current load
      if (thisLoadId === loadIdRef.current) {
        console.error('[3D Viewer] Load receptor failed:', err);
        setError(`Failed to load structure for ${pdbId}: ${err.message || err}`);
      }
    } finally {
      if (thisLoadId === loadIdRef.current) {
        setLoading(false);
      }
    }
  };

  // Compute 3D Conformer and Dock Ligand
  const dockActiveCompound = async () => {
    if (!activeCompound) return;
    if (!stageRef.current) return;

    setDockingLoading(true);
    setError(null);

    try {
      // 1. Call Rust Tauri command to generate optimized force-field conformers
      const sdfBlock = await invoke<string>('generate_3d_conformer', { 
        smiles: activeCompound.smiles 
      });

      if (!stageRef.current) return;

      // Remove previous docked ligand from scene state and maps if existing
      const oldLigandEntry = scene.find(e => e.stageId === 1 && e.type === 'ligand');
      if (oldLigandEntry) {
        removeEntry(oldLigandEntry.id);
      }

      // 2. Load the SDF file format coordinate string into memory as a Blob
      const sdfBlob = new Blob([sdfBlock], { type: 'text/plain' });
      const ligandComponent = await stageRef.current.loadFile(sdfBlob, { 
        ext: 'sdf', 
        defaultRepresentation: false 
      });

      if (!ligandComponent || !stageRef.current) return;

      ligandCompRef.current = ligandComponent;
      setHasDockedLigand(true);

      const entryId = crypto.randomUUID();
      componentMap.current.set(entryId, ligandComponent);
      dispatch({
        t: 'add',
        entry: {
          id: entryId,
          type: 'ligand',
          name: activeCompound.name,
          expanded: true,
          visible: true,
          stageId: 1,
          children: [
            {
              id: `lig-sub-${crypto.randomUUID()}`,
              type: 'ligand',
              name: activeCompound.name,
              selection: '*',
              visible: true,
              repr: 'ball+stick',
              color: '#3b82f6',
            }
          ]
        }
      });

      // 4. Solve Hydrogen bonding non-covalent contacts between ligand and protein pocket
      if (showHBonds && proteinCompRef.current) {
        try {
          ligandComponent.addRepresentation('contact', {
            contactType: 'polar',
            colorValue: '#10b981',
            dashed: true
          });
        } catch (err) {
          console.warn('[3D Viewer] Contact representation error:', err);
        }
      }

      // 5. Generate Pharmacophore overlay spheres on top of active ligand conformer
      if (showPharmacophores) {
        generatePharmacophoreLayer();
      }

      // 6. Zoom camera directly into the ligand
      try {
        const center = ligandComponent.getCenter();
        if (center) {
          stageRef.current.animationControls.zoomMove(
            center,
            stageRef.current.getZoom() * 0.5,
            1000
          );
        }
      } catch (err) {
        // Fallback: just auto-view
        try {
          stageRef.current.autoView(500);
        } catch (e) { console.warn('[3D Viewer] Docking autoView failed:', e); }
      }

    } catch (err: any) {
      console.error('[3D Viewer] Docking failed:', err);
      setError(`Failed to compute 3D conformer coordinates: ${err.message || err}`);
    } finally {
      setDockingLoading(false);
    }
  };

  // Generate Pharmacophore shape overlays directly in 3D canvas space
  const generatePharmacophoreLayer = () => {
    if (!stageRef.current) return;
    
    // Clear previous pharmacophore overlays
    if (pharmacophoreShapesRef.current) {
      try {
        stageRef.current.removeComponent(pharmacophoreShapesRef.current);
      } catch (e) { console.warn('[3D Viewer] Remove pharmacophore shapes failed:', e); }
      pharmacophoreShapesRef.current = null;
    }

    try {
      const shape = new NglObj.Shape('pharmacophore-layer');

      if (ligandCompRef.current && (ligandCompRef.current as any).structure) {
        const struct = (ligandCompRef.current as any).structure;
        const aromaticCoords: [number, number, number][] = [];

        struct.eachAtom((atom: any) => {
          const elem = (atom.element || '').toUpperCase();
          const coords: [number, number, number] = [atom.x, atom.y, atom.z];
          if (elem === 'O' || elem === 'N' || elem === 'F') {
            shape.addSphere(coords, [0.9, 0.1, 0.1], 0.6, `Hydrogen Bond Acceptor (${elem})`);
          }
          if (elem === 'N' || elem === 'O') {
            shape.addSphere([atom.x, atom.y + 0.2, atom.z], [0.1, 0.9, 0.1], 0.6, `Hydrogen Bond Donor (${elem})`);
          }
          if (elem === 'C' && activeCompound?.logp && activeCompound.logp > 2.0) {
            shape.addSphere(coords, [0.9, 0.9, 0.1], 0.7, 'Hydrophobic Contact');
          }
          if (atom.aromatic || (typeof atom.isAromatic === 'function' && atom.isAromatic())) {
            aromaticCoords.push(coords);
          }
        });

        if (aromaticCoords.length > 0) {
          const sum = aromaticCoords.reduce((acc, curr) => [acc[0] + curr[0], acc[1] + curr[1], acc[2] + curr[2]], [0, 0, 0]);
          const centroid: [number, number, number] = [sum[0] / aromaticCoords.length, sum[1] / aromaticCoords.length, sum[2] / aromaticCoords.length];
          shape.addSphere(centroid, [0.1, 0.5, 0.9], 1.2, 'Aromatic Core Centroid');
        }
      }

      const shapeComp = stageRef.current.addComponentFromObject(shape);
      if (shapeComp) {
        shapeComp.addRepresentation('buffer', { opacity: 0.45 });
        pharmacophoreShapesRef.current = shapeComp;
      }
    } catch (err) {
      console.warn('[3D Viewer] Pharmacophore layer error:', err);
    }
  };

  // Re-generate pharmacophore when toggle switches
  useEffect(() => {
    if (showPharmacophores && ligandCompRef.current) {
      generatePharmacophoreLayer();
    } else if (!showPharmacophores && pharmacophoreShapesRef.current) {
      try {
        stageRef.current?.removeComponent(pharmacophoreShapesRef.current);
      } catch (e) { console.warn('[3D Viewer] Hide pharmacophore shapes failed:', e); }
      pharmacophoreShapesRef.current = null;
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showPharmacophores]);

  // Handle Preset dropdown shifts
  const handlePresetChange = (presetId: string) => {
    setSelectedPresetId(presetId);
    const selected = RECEPTOR_PRESETS.find(p => p.id === presetId);
    if (selected) {
      loadReceptorFromUrl(selected.pdbId);
    }
  };

  // Fetch custom PDB structure
  const handleCustomPdbFetch = () => {
    const trimmed = customPdbId.trim().toUpperCase();
    if (trimmed.length === 4) {
      setSelectedPresetId('custom');
      setCustomLoadedPdb(trimmed);
      loadReceptorFromUrl(trimmed);
    }
  };

  // Generate Pharmacophore shape overlays for comparison compound in Stage 2
  const generatePharmacophore2Layer = () => {
    if (!stage2Ref.current || !comparisonCompound) return;
    
    if (pharmacophore2ShapesRef.current) {
      try {
        stage2Ref.current.removeComponent(pharmacophore2ShapesRef.current);
      } catch (e) { console.warn('[3D Viewer] Remove pharmacophore 2 shapes failed:', e); }
      pharmacophore2ShapesRef.current = null;
    }

    try {
      const shape = new NglObj.Shape('pharmacophore-layer-2');

      if (ligand2CompRef.current && (ligand2CompRef.current as any).structure) {
        const struct = (ligand2CompRef.current as any).structure;
        const aromaticCoords: [number, number, number][] = [];

        struct.eachAtom((atom: any) => {
          const elem = (atom.element || '').toUpperCase();
          const coords: [number, number, number] = [atom.x, atom.y, atom.z];
          if (elem === 'O' || elem === 'N' || elem === 'F') {
            shape.addSphere(coords, [0.9, 0.1, 0.1], 0.6, `Hydrogen Bond Acceptor (${elem})`);
          }
          if (elem === 'N' || elem === 'O') {
            shape.addSphere([atom.x, atom.y + 0.2, atom.z], [0.1, 0.9, 0.1], 0.6, `Hydrogen Bond Donor (${elem})`);
          }
          if (elem === 'C' && comparisonCompound.logp && comparisonCompound.logp > 2.0) {
            shape.addSphere(coords, [0.9, 0.9, 0.1], 0.7, 'Hydrophobic Contact');
          }
          if (atom.aromatic || (typeof atom.isAromatic === 'function' && atom.isAromatic())) {
            aromaticCoords.push(coords);
          }
        });

        if (aromaticCoords.length > 0) {
          const sum = aromaticCoords.reduce((acc, curr) => [acc[0] + curr[0], acc[1] + curr[1], acc[2] + curr[2]], [0, 0, 0]);
          const centroid: [number, number, number] = [sum[0] / aromaticCoords.length, sum[1] / aromaticCoords.length, sum[2] / aromaticCoords.length];
          shape.addSphere(centroid, [0.1, 0.5, 0.9], 1.2, 'Aromatic Core Centroid');
        }
      }

      const shapeComp = stage2Ref.current.addComponentFromObject(shape);
      if (shapeComp) {
        shapeComp.addRepresentation('buffer', { opacity: 0.45 });
        pharmacophore2ShapesRef.current = shapeComp;
      }
    } catch (err) {
      console.warn('[3D Viewer] Pharmacophore 2 layer error:', err);
    }
  };

  // Dock comparison compound in Stage 2
  const dockComparisonCompound = async () => {
    if (!comparisonCompound) return;
    if (!stage2Ref.current) return;

    setDocking2Loading(true);
    setError(null);

    try {
      const sdfBlock = await invoke<string>('generate_3d_conformer', { 
        smiles: comparisonCompound.smiles 
      });

      if (!stage2Ref.current) return;

      // Remove previous comparison docked ligand from scene state and maps if existing
      const oldComparisonEntry = scene.find(e => e.stageId === 2 && e.type === 'ligand');
      if (oldComparisonEntry) {
        removeEntry(oldComparisonEntry.id);
      }

      const sdfBlob = new Blob([sdfBlock], { type: 'text/plain' });
      const ligandComponent = await stage2Ref.current.loadFile(sdfBlob, { 
        ext: 'sdf', 
        defaultRepresentation: false 
      });

      if (!ligandComponent || !stage2Ref.current) return;

      ligand2CompRef.current = ligandComponent;
      setHasDocked2Ligand(true);

      const entryId2 = crypto.randomUUID();
      componentMap.current.set(entryId2, ligandComponent);
      dispatch({
        t: 'add',
        entry: {
          id: entryId2,
          type: 'ligand',
          name: comparisonCompound.name,
          expanded: true,
          visible: true,
          stageId: 2,
          children: [
            {
              id: `lig2-sub-${crypto.randomUUID()}`,
              type: 'ligand',
              name: comparisonCompound.name,
              selection: '*',
              visible: true,
              repr: 'ball+stick',
              color: '#f59e0b',
            }
          ]
        }
      });

      if (showHBonds && protein2CompRef.current) {
        try {
          ligandComponent.addRepresentation('contact', {
            contactType: 'polar',
            colorValue: '#10b981',
            dashed: true
          });
        } catch (e) { console.warn('[3D Viewer] Add Stage 2 polar contact failed:', e); }
      }

      if (showPharmacophores) {
        generatePharmacophore2Layer();
      }

      try {
        const center = ligandComponent.getCenter();
        if (center) {
          stage2Ref.current.animationControls.zoomMove(
            center,
            stage2Ref.current.getZoom() * 0.5,
            1000
          );
        }
      } catch (err) {
        try { stage2Ref.current.autoView(500); } catch (e) { console.warn('[3D Viewer] Zoom 2 fallback autoView failed:', e); }
      }

    } catch (err: any) {
      console.error('[3D Viewer] Docking 2 failed:', err);
      setError(`Failed to compute 3D conformer for comparison compound: ${err.message || err}`);
    } finally {
      setDocking2Loading(false);
    }
  };

  // Load local PDB contents into NGL
  const loadLocalPdb = async (content: string, fileName: string) => {
    if (!stageRef.current) return;
    
    const thisLoadId = ++loadIdRef.current;
    setLoading(true);
    setError(null);

    try {
      stageRef.current.removeAllComponents();
      proteinCompRef.current = null;
      ligandCompRef.current = null;
      pharmacophoreShapesRef.current = null;
      setHasDockedLigand(false);

      if (stage2Ref.current) {
        stage2Ref.current.removeAllComponents();
        protein2CompRef.current = null;
        ligand2CompRef.current = null;
        pharmacophore2ShapesRef.current = null;
        setHasDocked2Ligand(false);
      }

      dispatch({ t: 'clear' });
      componentMap.current.clear();
      reprMap.current.clear();

      // Detect file extension for correct parser
      const ext = fileName.toLowerCase().endsWith('.cif') ? 'cif' : 'pdb';

      // Load standard PDB format from memory contents as Blob
      const pdbBlob = new Blob([content], { type: 'text/plain' });
      const component = await stageRef.current.loadFile(pdbBlob, { 
        ext,
        defaultRepresentation: false 
      });
      
      if (thisLoadId !== loadIdRef.current || !stageRef.current) return;

      proteinCompRef.current = component;

      const entryId = crypto.randomUUID();
      componentMap.current.set(entryId, component);
      dispatch({
        t: 'add',
        entry: {
          id: entryId,
          type: 'protein',
          name: fileName,
          pdbId: 'LOCAL',
          expanded: true,
          visible: true,
          stageId: 1,
          children: parseStructureToSubEntries(component),
        },
      });

      // Load into Stage 2 if active and available
      if (stage2Ref.current && splitScreen) {
        const pdbBlob2 = new Blob([content], { type: 'text/plain' });
        const component2 = await stage2Ref.current.loadFile(pdbBlob2, {
          ext,
          defaultRepresentation: false
        });
        
        if (thisLoadId !== loadIdRef.current || !stage2Ref.current) return;
        protein2CompRef.current = component2;
        
        const entryId2 = crypto.randomUUID();
        componentMap.current.set(entryId2, component2);
        dispatch({
          t: 'add',
          entry: {
            id: entryId2,
            type: 'protein',
            name: fileName,
            pdbId: 'LOCAL',
            expanded: true,
            visible: true,
            stageId: 2,
            children: parseStructureToSubEntries(component2),
          },
        });
      }

      setTimeout(() => {
        try {
          focusWholeProtein();
        } catch (e) {
          console.warn('[3D Viewer] delayed focusWholeProtein failed:', e);
        }
      }, 150);
    } catch (err: any) {
      if (thisLoadId === loadIdRef.current) {
        console.error('[3D Viewer] Load local PDB failed:', err);
        setError(`Failed to parse and render local PDB: ${err.message || err}`);
      }
    } finally {
      if (thisLoadId === loadIdRef.current) {
        setLoading(false);
      }
    }
  };

  // Handle local PDB file upload
  const handlePdbUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async (event) => {
      const contents = event.target?.result as string;
      if (contents) {
        setSelectedPresetId('local');
        setLocalPdbName(file.name);
        loadLocalPdb(contents, file.name);
      }
    };
    reader.readAsText(file);
  };

  // focusPocket has been moved up to component scope to be accessible during loading

  // Export Screenshot PNG
  const captureScreenshot = () => {
    if (!stageRef.current) return;
    try {
      stageRef.current.makeImage({
        factor: 2,
        antialias: true,
        trim: false,
        transparent: false
      }).then((blob: Blob) => {
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `edeon_3d_render_${activePreset.pdbId}.png`;
        link.click();
        URL.revokeObjectURL(url);
      });
    } catch (err) {
      console.error('[3D Viewer] Screenshot failed:', err);
    }
  };

  return (
    <div className="main-content viewer-3d-layout">
      {/* 1. Canvas Viewport (Takes up center-right) */}
      <div className={`viewer-canvas-container ${splitScreen ? 'split-active' : ''}`}>
        <div className="viewports-flex-row">
          <div ref={viewportRef} className={`ngl-viewport ${splitScreen ? 'split-pane' : ''}`} id="viewport" />
          {splitScreen && (
            <div ref={viewport2Ref} className="ngl-viewport split-pane" id="viewport2" />
          )}
        </div>

        {/* Floating Viewport Camera Toolbar */}
        <div className="viewport-floating-toolbar">
          <button 
            className={`toolbar-float-btn ${isSpinning ? 'active' : ''}`}
            title="Toggle Spin"
            onClick={() => setIsSpinning(p => !p)}
          >
            <Rotate3d size={14} className={isSpinning ? 'animate-spin' : ''} />
            <span>Spin</span>
          </button>

          <button 
            className="toolbar-float-btn"
            title="Focus on Whole Protein"
            onClick={focusWholeProtein}
          >
            <Maximize2 size={14} />
            <span>Focus</span>
          </button>

          <button 
            className="toolbar-float-btn"
            title="Focus on Binding Site (ligand + 6 Å)"
            onClick={focusBindingSite}
          >
            <Target size={14} />
            <span>Focus Site</span>
          </button>

          <button 
            className="toolbar-float-btn"
            title="Reset View"
            onClick={() => { try { stageRef.current?.autoView(500); } catch(e) { console.warn('[3D Viewer] Reset view failed:', e); } }}
          >
            <RefreshCw size={14} />
            <span>Reset</span>
          </button>

          <div className="toolbar-float-divider" />

          <button 
            className={`toolbar-float-btn ${cameraType === 'orthographic' ? 'active' : ''}`}
            title="Toggle Camera Mode"
            onClick={() => setCameraType(p => p === 'perspective' ? 'orthographic' : 'perspective')}
          >
            <span>{cameraType === 'perspective' ? 'Perspective' : 'Orthographic'}</span>
          </button>

          <button 
            className="toolbar-float-btn highlight-capture"
            title="Capture PNG Image"
            onClick={captureScreenshot}
          >
            <Camera size={14} />
            <span>Snapshot</span>
          </button>
        </div>

        {/* Status Indicators overlay */}
        {loading && (
          <div className="viewport-status-overlay">
            <div className="spinner"></div>
            <span>Downloading target {activePreset.pdbId} from PDB...</span>
          </div>
        )}

        {dockingLoading && (
          <div className="viewport-status-overlay">
            <div className="spinner"></div>
            <span>Calculating 3D Conformer coordinates (MMFF94)...</span>
          </div>
        )}

        {docking2Loading && (
          <div className="viewport-status-overlay">
            <div className="spinner"></div>
            <span>Calculating comparison conformer coordinates (MMFF94)...</span>
          </div>
        )}

        {error && (
          <div className="viewport-error-overlay">
            <span className="error-icon">✕</span>
            <span>{error}</span>
            <button className="error-dismiss" onClick={() => setError(null)}>Dismiss</button>
          </div>
        )}
      </div>

      {/* 2. Interactive Control Sidebar (Left sidebar of 3D panel) */}
      <div className="viewer-controls-sidebar">
        {/* Split Screen Toggler */}
        <button 
          className={`btn-split-toggle ${splitScreen ? 'active' : ''}`}
          onClick={() => setSplitScreen(p => !p)}
        >
          <Sliders size={14} />
          <span>{splitScreen ? 'Disable Split Screen' : 'Enable Split Screen (Comparative)'}</span>
        </button>

        {/* Section A: Target Protein Receptor Selector */}
        <div className="sidebar-group">
          <div className="group-title">
            <Dna size={14} className="text-brand-500" />
            <span>TARGET PROTEIN RECEPTOR</span>
          </div>
          
          <div className="selector-field">
            <select 
              value={selectedPresetId} 
              onChange={(e) => handlePresetChange(e.target.value)}
              className="preset-select"
            >
              {RECEPTOR_PRESETS.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
              {selectedPresetId === 'custom' && customLoadedPdb && (
                <option value="custom">Custom: {customLoadedPdb}</option>
              )}
              {selectedPresetId === 'local' && localPdbName && (
                <option value="local">Local: {localPdbName}</option>
              )}
            </select>
          </div>

          <div className="custom-pdb-field">
            <input 
              type="text" 
              placeholder="Or enter 4-letter PDB (e.g. 1ABC)"
              value={customPdbId}
              onChange={(e) => setCustomPdbId(e.target.value.toUpperCase())}
              className="custom-pdb-input"
              maxLength={4}
            />
            <button 
              className="btn-fetch-pdb"
              onClick={handleCustomPdbFetch}
              disabled={loading || customPdbId.trim().length !== 4}
            >
              Fetch
            </button>
          </div>

          <div className="local-pdb-field">
            <input 
              type="file" 
              accept=".pdb,.cif,.mmcif"
              id="local-pdb-upload"
              onChange={handlePdbUpload}
              className="hidden-file-input"
            />
            <label htmlFor="local-pdb-upload" className="btn-upload-pdb">
              Upload PDB File (.pdb, .cif)
            </label>
          </div>

          <div className="preset-description-box">
            <div className="desc-tag">PDB: {activePreset.pdbId} · {activePreset.target}</div>
            <p className="desc-text">{activePreset.description}</p>
          </div>
        </div>

        {/* Section B: Active Small Molecule workspace */}
        <div className="sidebar-group">
          <div className="group-title">
            <Sparkles size={14} className="text-brand-500" />
            <span>LIGAND LEAD WORKSPACE</span>
          </div>

          <div className="selector-field">
            <select
              value={selectedCompoundId || ''}
              onChange={(e) => useUIStore.getState().setSelectedCompound(e.target.value || null)}
              className="preset-select"
            >
              <option value="">-- Select a compound to dock --</option>
              {allAvailableCompounds.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}{c.smiles ? ` (${c.smiles.slice(0, 30)}${c.smiles.length > 30 ? '…' : ''})` : ''}
                </option>
              ))}
            </select>
          </div>

          {activeCompound ? (
            <div className="docking-compound-info" style={{ marginTop: '8px' }}>
              <div className="compound-meta">
                <span className="compound-name">{activeCompound.name}</span>
                <span className="compound-smiles selectable">{activeCompound.smiles}</span>
              </div>
              <button 
                className="btn-dock-conformer"
                disabled={dockingLoading || loading}
                onClick={dockActiveCompound}
              >
                {hasDockedLigand ? 'Re-calculate & Redock' : 'Compute conformer & Dock'}
              </button>
            </div>
          ) : (
            <div className="docking-compound-empty">
              <Info size={12} />
              <span>Pick a compound from the dropdown above, or select one in the Library/Workflows view.</span>
            </div>
          )}
        </div>

        {/* Section B-2: Comparison Ligand Workspace */}
        {splitScreen && (
          <div className="sidebar-group split-ligand-group">
            <div className="group-title">
              <Sparkles size={14} className="text-brand-500" />
              <span>COMPARISON LIGAND</span>
            </div>

            <div className="selector-field">
              <select
                value={comparisonCompoundId || ''}
                onChange={(e) => setComparisonCompoundId(e.target.value)}
                className="preset-select"
              >
                <option value="">-- Select Comparison Compound --</option>
                {allAvailableCompounds.map((c) => (
                  <option key={c.id} value={c.id} disabled={c.id === activeCompound?.id}>
                    {c.name} {c.id === activeCompound?.id ? '(Active)' : ''}
                  </option>
                ))}
              </select>
            </div>

            {comparisonCompound ? (
              <div className="docking-compound-info" style={{ marginTop: '8px' }}>
                <div className="compound-meta">
                  <span className="compound-name">{comparisonCompound.name}</span>
                  <span className="compound-smiles selectable">{comparisonCompound.smiles}</span>
                </div>
                <button 
                  className="btn-dock-conformer"
                  disabled={docking2Loading || loading}
                  onClick={dockComparisonCompound}
                >
                  {hasDocked2Ligand ? 'Re-calculate & Redock' : 'Compute conformer & Dock'}
                </button>
              </div>
            ) : (
              <div className="docking-compound-empty" style={{ marginTop: '8px' }}>
                <Info size={12} />
                <span>Select a comparison compound from the dropdown above to dock it side-by-side with the active lead.</span>
              </div>
            )}
          </div>
        )}

        {/* Section C: Scene Graph Outliner */}
        <div className="sidebar-group">
          <div className="group-title">
            <Layers size={14} className="text-brand-500" />
            <span>SCENE OUTLINER</span>
          </div>
          <SceneOutliner
            scene={scene}
            onToggleEntry={(id) => dispatch({ t: 'toggleEntry', id })}
            onToggleSub={(entryId, subId) => dispatch({ t: 'toggleSub', entryId, subId })}
            onExpand={(id) => dispatch({ t: 'expand', id })}
            onSetRepr={(entryId, subId, repr) => dispatch({ t: 'setRepr', entryId, subId, repr })}
            onSetColor={(entryId, subId, color) => dispatch({ t: 'setColor', entryId, subId, color })}
            onRemoveEntry={removeEntry}
            onFocusSub={(entryId, subId) => {
              const comp = componentMap.current.get(entryId);
              const sub = scene.find(e => e.id === entryId)?.children.find(c => c.id === subId);
              if (!comp || !sub || !stageRef.current) return;
              try {
                // Focus camera directly onto the bounds of this sub-selection
                const selectionObj = new NglObj.Selection(sub.selection);
                const view = comp.structure.getView(selectionObj);
                if (view && view.center) {
                  stageRef.current.animationControls.zoomMove(
                    view.center,
                    stageRef.current.getZoom() * 0.6,
                    800
                  );
                }
              } catch (e) { 
                console.warn('[3D Viewer] Focus sub-entry failed:', e); 
              }
            }}
          />
        </div>

        {/* Section D: Non-Covalent Binding Solver */}
        <div className="sidebar-group">
          <div className="group-title">
            <Activity size={14} className="text-brand-500" />
            <span>NON-COVALENT INTERACTIONS</span>
          </div>

          <div className="visibility-grid">
            <label className="checkbox-row">
              <input 
                type="checkbox" 
                checked={showHBonds} 
                onChange={(e) => setShowHBonds(e.target.checked)} 
                disabled={!hasDockedLigand}
              />
              <span className={!hasDockedLigand ? 'text-disabled' : ''}>Hydrogen Bonds (green)</span>
            </label>

            <label className="checkbox-row">
              <input 
                type="checkbox" 
                checked={showHydrophobic} 
                onChange={(e) => setShowHydrophobic(e.target.checked)} 
                disabled={!hasDockedLigand}
              />
              <span className={!hasDockedLigand ? 'text-disabled' : ''}>Hydrophobic Envelopes (yellow)</span>
            </label>

            <label className="checkbox-row">
              <input 
                type="checkbox" 
                checked={showAromaticStacking} 
                onChange={(e) => setShowAromaticStacking(e.target.checked)} 
                disabled={!hasDockedLigand}
              />
              <span className={!hasDockedLigand ? 'text-disabled' : ''}>Aromatic Stacking (blue)</span>
            </label>
          </div>
        </div>

        {/* Section E: 3D Pharmacophore Overlay Mapping */}
        <div className="sidebar-group">
          <div className="group-title">
            <Sliders size={14} className="text-brand-500" />
            <span>PHARMACOPHORE LAYER</span>
          </div>

          <div className="visibility-grid">
            <label className="checkbox-row highlight-pharmacophore">
              <input 
                type="checkbox" 
                checked={showPharmacophores} 
                onChange={(e) => setShowPharmacophores(e.target.checked)} 
                disabled={!hasDockedLigand}
              />
              <span className={!hasDockedLigand ? 'text-disabled' : ''}>Show Pharmacophore Features</span>
            </label>
          </div>

          {showPharmacophores && (
            <div className="pharmacophore-legend">
              <div className="legend-item"><span className="dot dot-red" /><span>Hydrogen Bond Acceptor (HBA)</span></div>
              <div className="legend-item"><span className="dot dot-green" /><span>Hydrogen Bond Donor (HBD)</span></div>
              <div className="legend-item"><span className="dot dot-yellow" /><span>Hydrophobic Center</span></div>
              <div className="legend-item"><span className="dot dot-blue" /><span>Aromatic Centroid</span></div>
            </div>
          )}
        </div>

        {/* Section F: Viewport Background Theme Switcher */}
        <div className="sidebar-group">
          <div className="group-title">
            <Layers size={14} className="text-brand-500" />
            <span>VIEWPORT BACKGROUND</span>
          </div>

          <div className="bg-theme-switcher">
            <button 
              className={`theme-btn ${bgColor === 'white' ? 'active' : ''}`}
              title="Set background to White"
              onClick={() => setBgColor('white')}
            >
              <span className="color-swatch swatch-white" />
              <span>White</span>
            </button>
            <button 
              className={`theme-btn ${bgColor === 'pale-grey' ? 'active' : ''}`}
              title="Set background to Pale Grey"
              onClick={() => setBgColor('pale-grey')}
            >
              <span className="color-swatch swatch-pale-grey" />
              <span>Pale Grey</span>
            </button>
            <button 
              className={`theme-btn ${bgColor === 'black' ? 'active' : ''}`}
              title="Set background to Black"
              onClick={() => setBgColor('black')}
            >
              <span className="color-swatch swatch-black" />
              <span>Black</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
