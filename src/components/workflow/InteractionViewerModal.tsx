import { useEffect, useRef, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore
import NglModule from 'ngl';
import * as NGL from 'ngl';
import { 
  Rotate3d, 
  Camera, 
  RefreshCw, 
  Maximize2,
  Activity,
  Sliders,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';
import { useUIStore } from '../../store/uiStore';

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

interface Pose {
  pose_index: number;
  score_kcal_per_mol: number;
  rmsd_to_top?: number;
  rmsd_to_prev?: number;
  pdbqt_block: string;
  sdf_block: string;
}

interface DockingJobResult {
  job_id: string;
  spec: {
    receptor_hash: string;
    ligand_hash: string;
    box_center: [number, number, number];
    box_size: [number, number, number];
  };
  poses: Pose[];
  elapsed_seconds: number;
  completed_at: string;
  receptor_display_name?: string;
  ligand_display_name?: string;
}

interface InteractionViewerModalProps {
  jobId: string;
  onClose: () => void;
  /** Optional: pass docking result directly to bypass history_load DB lookup */
  dockingResult?: any;
  /** Optional: receptor hash for file lookups when docking result is provided directly */
  receptorHash?: string;
}

export function InteractionViewerModal({ jobId, onClose, dockingResult: propDockingResult, receptorHash: propReceptorHash }: InteractionViewerModalProps) {
  const theme = useUIStore((s) => s.theme);
  const viewportRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<any>(null);
  const receptorCompRef = useRef<any>(null);
  const ligandCompRef = useRef<any>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fallbackMode, setFallbackMode] = useState(false);
  const [viewMode, setViewMode] = useState<'3d' | '2d'>('3d');
  const [interactionMapSvg, setInteractionMapSvg] = useState<string | null>(null);
  const [loading2dMap, setLoading2dMap] = useState(false);
  const [ligandSmiles, setLigandSmiles] = useState<string | null>(null);

  const [jobResult, setJobResult] = useState<DockingJobResult | null>(null);
  const [selectedPoseIndex, setSelectedPoseIndex] = useState<number>(0);
  const [interactions, setInteractions] = useState<any>(null);
  const [loadingInteractions, setLoadingInteractions] = useState(false);

  // Viewport settings
  const [isSpinning, setIsSpinning] = useState(false);
  const [cameraType, setCameraType] = useState<'perspective' | 'orthographic'>('perspective');
  const [bgColor, setBgColor] = useState<'white' | 'pale-grey' | 'black'>('pale-grey');

  const [showHBonds] = useState(true);

  const [clusters, setClusters] = useState<number[][] | null>(null);
  const [showRepresentativesOnly, setShowRepresentativesOnly] = useState(false);
  const [clustering, setClustering] = useState(false);

  // Load Job details and Poses
  useEffect(() => {
    let active = true;
    const loadJob = async () => {
      try {
        setLoading(true);
        setError(null);
        setFallbackMode(false);
        setClusters(null);
        setShowRepresentativesOnly(false);

        // 1. Load job JSON — try DB first, fall back to prop
        let data: DockingJobResult;
        try {
          data = await invoke<DockingJobResult>('history_load', { jobId });
        } catch (historyErr) {
          // DB lookup failed — try the directly-passed docking result
          if (propDockingResult && propDockingResult.poses) {
            data = propDockingResult as DockingJobResult;
          } else {
            throw historyErr;
          }
        }
        if (!active) return;
        setJobResult(data);

        // 2. Load receptor metadata & cleaned PDB from cache folder using receptor hash
        const receptorHash = data.spec?.receptor_hash || propReceptorHash || '';
        
        let metadata;
        try {
          const metadataContent = await invoke<string>('read_text_file', {
            path: `data/docking/cache/receptors/${receptorHash}/metadata.json`
          });
          metadata = JSON.parse(metadataContent);
        } catch (err) {
          console.error('Failed to read receptor metadata, fallback to preset lookup:', err);
        }

        const rawPdbPath = metadata?.raw_pdb_path || '';
        
        // 3. Try to load NGL 3D stage
        if (!NglObj) {
          console.warn('NGL module not available, switching to 2D fallback');
          await load2dFallback(data, rawPdbPath || `data/docking/cache/receptors/${receptorHash}/cleaned.pdb`);
          if (active) {
            setLoading(false);
          }
          return;
        }

        // Wait a tick for viewport element to be fully sized in dialog
        await new Promise((resolve) => requestAnimationFrame(resolve));
        if (!active || !viewportRef.current) {
          // Viewport not available, use 2D fallback
          await load2dFallback(data, rawPdbPath || `data/docking/cache/receptors/${receptorHash}/cleaned.pdb`);
          if (active) setLoading(false);
          return;
        }

        // Clean up previous stage
        if (stageRef.current) {
          try { stageRef.current.dispose(); } catch (e) {}
          stageRef.current = null;
        }

        const initialTheme = useUIStore.getState().theme;
        const colorHex = bgColor === 'white' ? '#ffffff' : bgColor === 'pale-grey' ? (initialTheme === 'dark' ? '#09090b' : '#f1f5f9') : '#000000';
        
        let stage: any;
        try {
          stage = new NglObj.Stage(viewportRef.current, {
            backgroundColor: colorHex,
            tooltip: true
          });
        } catch (nglErr) {
          console.error('NGL Stage creation failed:', nglErr);
          await load2dFallback(data, rawPdbPath || `data/docking/cache/receptors/${receptorHash}/cleaned.pdb`);
          if (active) setLoading(false);
          return;
        }
        stageRef.current = stage;

        // Load cleaned receptor PDB
        let cleanedPdbContent: string;
        try {
          cleanedPdbContent = await invoke<string>('read_text_file', {
            path: `data/docking/cache/receptors/${receptorHash}/cleaned.pdb`
          });
        } catch (pdbErr) {
          console.error('Failed to load receptor PDB:', pdbErr);
          await load2dFallback(data, rawPdbPath || `data/docking/cache/receptors/${receptorHash}/cleaned.pdb`);
          if (active) setLoading(false);
          return;
        }

        const receptorBlob = new Blob([cleanedPdbContent], { type: 'text/plain' });
        const receptorComp = await stage.loadFile(receptorBlob, { ext: 'pdb', defaultRepresentation: false });
        receptorCompRef.current = receptorComp;

        // Add standard cartoon representation
        receptorComp.addRepresentation('cartoon', { colorScheme: 'chainid' });
        // Show cofactors
        receptorComp.addRepresentation('licorice', { sele: 'hetero and not (water or ion)', colorScheme: 'element' });
        // Show ions
        receptorComp.addRepresentation('spacefill', { sele: 'ion', scale: 0.3 });

        // Load default pose
        if (data.poses && data.poses.length > 0) {
          const defaultPose = data.poses[0];
          const ligandBlob = new Blob([defaultPose.sdf_block || defaultPose.pdbqt_block], { type: 'text/plain' });
          const ligandExt = defaultPose.sdf_block ? 'sdf' : 'pdbqt';
          const ligandComp = await stage.loadFile(ligandBlob, { ext: ligandExt, defaultRepresentation: false });
          ligandCompRef.current = ligandComp;

          ligandComp.addRepresentation('ball+stick', { colorValue: '#10b981', multipleBond: 'offset' });
          
          if (showHBonds) {
            ligandComp.addRepresentation('contact', {
              contactType: 'polar',
              colorValue: '#10b981',
              dashed: true
            });
          }

          stage.autoView(800);

          // Retrieve interactions
          const pdbPathForInteractions = rawPdbPath || `data/docking/cache/receptors/${receptorHash}/cleaned.pdb`;
          await loadInteractions(defaultPose.sdf_block || defaultPose.pdbqt_block, defaultPose.pose_index, pdbPathForInteractions);
          await load2dInteractionMap(defaultPose.sdf_block || defaultPose.pdbqt_block, defaultPose.pose_index, pdbPathForInteractions);
        } else {
          stage.autoView(800);
        }

        setLoading(false);
      } catch (err: any) {
        console.error('3D viewer load error, attempting 2D fallback:', err);
        if (active) {
          // Try 2D fallback before giving up
          try {
            const fallbackData = propDockingResult || jobResult;
            if (fallbackData?.poses?.length > 0) {
              const receptorHash = fallbackData.spec?.receptor_hash || propReceptorHash || '';
              const pdbPath = `data/docking/cache/receptors/${receptorHash}/cleaned.pdb`;
              await load2dFallback(fallbackData, pdbPath);
              setLoading(false);
            } else {
              setError(err?.message || String(err));
              setLoading(false);
            }
          } catch (fallbackErr) {
            setError(err?.message || String(err));
            setLoading(false);
          }
        }
      }
    };

    loadJob();

    return () => {
      active = false;
      if (stageRef.current) {
        try { stageRef.current.dispose(); } catch (e) {}
        stageRef.current = null;
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  // Handle background color update
  useEffect(() => {
    if (!stageRef.current) return;
    const colorHex = bgColor === 'white' ? '#ffffff' : bgColor === 'pale-grey' ? (theme === 'dark' ? '#09090b' : '#f1f5f9') : '#000000';
    stageRef.current.setParameters({ backgroundColor: colorHex });
  }, [bgColor, theme]);

  // Handle spin state
  useEffect(() => {
    if (!stageRef.current) return;
    stageRef.current.setSpin(isSpinning);
  }, [isSpinning]);

  // Handle camera type update
  useEffect(() => {
    if (!stageRef.current) return;
    stageRef.current.setParameters({ cameraType });
  }, [cameraType]);

  // Resize handler
  useEffect(() => {
    const handleResize = () => {
      if (stageRef.current) {
        stageRef.current.handleResize();
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const loadInteractions = async (sdfBlock: string, poseIdx: number, pdbPath: string) => {
    setLoadingInteractions(true);
    try {
      const data = await invoke<any>('analysis_interactions', {
        receptorPdbPath: pdbPath,
        poseSdfBlock: sdfBlock,
        poseIndex: poseIdx
      });
      setInteractions(data);
    } catch (err) {
      console.error('Failed to compute interaction fingerprint:', err);
    } finally {
      setLoadingInteractions(false);
    }
  };

  const load2dInteractionMap = async (sdfBlock: string, poseIdx: number, pdbPath: string) => {
    setLoading2dMap(true);
    try {
      const svg = await invoke<string>('generate_2d_interaction_map', {
        receptorPdbPath: pdbPath,
        poseSdfBlock: sdfBlock,
        poseIndex: poseIdx
      });
      setInteractionMapSvg(svg);
    } catch (err) {
      console.error('Failed to generate 2D interaction map:', err);
      // Fallback to plain depiction if 2D map generation fails
      try {
        const smiles = jobResult?.ligand_display_name || (jobResult as any)?.ligand_smiles || (jobResult?.spec as any)?.ligand_smiles;
        if (smiles) {
          const svg = await invoke<string>('depict_compound', { smiles });
          setInteractionMapSvg(svg);
        }
      } catch (depictErr) {
        console.error('Plain 2D depiction fallback failed:', depictErr);
      }
    } finally {
      setLoading2dMap(false);
    }
  };

  /** Load 2D fallback: SVG depiction + interaction fingerprint (no NGL/3D required) */
  const load2dFallback = async (data: any, pdbPath: string) => {
    setFallbackMode(true);
    setViewMode('2d');
    setJobResult(data);

    // Try to get SMILES of the ligand
    const smiles = data.ligand_display_name || data.spec?.ligand_smiles;
    if (smiles) {
      setLigandSmiles(smiles);
    }

    // Load interactions and 2D map for the best pose
    if (data.poses && data.poses.length > 0) {
      const bestPose = data.poses[0];
      await loadInteractions(
        bestPose.sdf_block || bestPose.pdbqt_block,
        bestPose.pose_index,
        pdbPath
      );
      await load2dInteractionMap(
        bestPose.sdf_block || bestPose.pdbqt_block,
        bestPose.pose_index,
        pdbPath
      );
    }
  };

  const handleClusterPoses = async () => {
    if (!jobResult || !jobResult.poses || jobResult.poses.length === 0) return;
    setClustering(true);
    try {
      const res = await invoke<number[][]>('cluster_poses', {
        poses: jobResult.poses,
        rmsdCutoff: 2.0
      });
      setClusters(res);
      setShowRepresentativesOnly(true);
      
      if (res.length > 0) {
        const representatives = res.map(c => c[0]);
        const currentPoseNum = jobResult.poses[selectedPoseIndex].pose_index;
        if (!representatives.includes(currentPoseNum)) {
          const matchingCluster = res.find(c => c.includes(currentPoseNum));
          const targetPoseNum = matchingCluster ? matchingCluster[0] : representatives[0];
          const targetIdx = jobResult.poses.findIndex(p => p.pose_index === targetPoseNum);
          if (targetIdx !== -1) {
            handlePoseChange(targetIdx);
          }
        }
      }
    } catch (err) {
      console.error('Pose clustering failed:', err);
      alert('Failed to cluster poses: ' + String(err));
    } finally {
      setClustering(false);
    }
  };

  const handlePoseChange = async (idx: number) => {
    if (!jobResult) return;
    setSelectedPoseIndex(idx);
    setInteractions(null);
    setInteractionMapSvg(null);

    const pose = jobResult.poses[idx];
    const receptorHash = jobResult.spec.receptor_hash || propReceptorHash || '';
    const pdbPath = `data/docking/cache/receptors/${receptorHash}/cleaned.pdb`;

    // Only update NGL if stage is active and we're not in fallback mode
    if (stageRef.current && !fallbackMode) {
      // Remove old ligand component
      if (ligandCompRef.current) {
        try {
          stageRef.current.removeComponent(ligandCompRef.current);
        } catch (e) {}
        ligandCompRef.current = null;
      }

      try {
        const ligandBlob = new Blob([pose.sdf_block || pose.pdbqt_block], { type: 'text/plain' });
        const ligandExt = pose.sdf_block ? 'sdf' : 'pdbqt';
        const ligandComp = await stageRef.current.loadFile(ligandBlob, { ext: ligandExt, defaultRepresentation: false });
        ligandCompRef.current = ligandComp;

        ligandComp.addRepresentation('ball+stick', { colorValue: '#10b981', multipleBond: 'offset' });
        
        if (showHBonds) {
          ligandComp.addRepresentation('contact', {
            contactType: 'polar',
            colorValue: '#10b981',
            dashed: true
          });
        }

        // Smooth transition to ligand centroid
        const center = ligandComp.getCenter();
        if (center) {
          stageRef.current.animationControls.zoomMove(
            center,
            stageRef.current.getZoom() * 0.45,
            1000
          );
        }
      } catch (err: any) {
        console.error('Failed to load pose in 3D viewport:', err);
      }
    }

    // Always load interactions and 2D interaction map
    await loadInteractions(pose.sdf_block || pose.pdbqt_block, pose.pose_index, pdbPath);
    await load2dInteractionMap(pose.sdf_block || pose.pdbqt_block, pose.pose_index, pdbPath);
  };

  const getVisiblePoseIndices = (): number[] => {
    if (!jobResult || !jobResult.poses) return [];
    return jobResult.poses
      .map((p, idx) => {
        const isSeed = !clusters || clusters.some(c => c[0] === p.pose_index);
        if (showRepresentativesOnly && !isSeed) return null;
        return idx;
      })
      .filter((idx): idx is number => idx !== null);
  };

  const visibleIndices = getVisiblePoseIndices();
  const currentVisibleIdx = visibleIndices.indexOf(selectedPoseIndex);
  const hasPrev = currentVisibleIdx > 0;
  const hasNext = currentVisibleIdx >= 0 && currentVisibleIdx < visibleIndices.length - 1;

  const handlePrevPose = () => {
    if (hasPrev) {
      handlePoseChange(visibleIndices[currentVisibleIdx - 1]);
    }
  };

  const handleNextPose = () => {
    if (hasNext) {
      handlePoseChange(visibleIndices[currentVisibleIdx + 1]);
    }
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (document.activeElement?.tagName === 'INPUT' || document.activeElement?.tagName === 'TEXTAREA') {
        return;
      }
      if (e.key === 'ArrowLeft') {
        if (hasPrev) {
          e.preventDefault();
          handlePoseChange(visibleIndices[currentVisibleIdx - 1]);
        }
      } else if (e.key === 'ArrowRight') {
        if (hasNext) {
          e.preventDefault();
          handlePoseChange(visibleIndices[currentVisibleIdx + 1]);
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [visibleIndices, currentVisibleIdx, hasPrev, hasNext, handlePoseChange]);

  const focusResidue = (residue: string) => {
    if (!stageRef.current) return;
    const parts = residue.split(':');
    if (parts.length < 2) return;
    const chain = parts[0];
    const rest = parts[1].split('-');
    const resnum = rest[1] || rest[0];
    
    // Zoom/center NGL on residue selection
    stageRef.current.autoView(`:${chain} and ${resnum}`, 800);
  };

  const focusLigand = () => {
    if (!stageRef.current || !ligandCompRef.current) return;
    const center = ligandCompRef.current.getCenter();
    if (center) {
      stageRef.current.animationControls.zoomMove(
        center,
        stageRef.current.getZoom() * 0.45,
        1000
      );
    }
  };

  const resetCamera = () => {
    if (stageRef.current) {
      stageRef.current.autoView(500);
    }
  };

  const captureScreenshot = () => {
    if (!stageRef.current || !jobResult) return;
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
        link.download = `interaction_map_${jobResult.poses[selectedPoseIndex]?.score_kcal_per_mol.toFixed(1)}_kcal.png`;
        link.click();
        URL.revokeObjectURL(url);
      });
    } catch (err) {
      console.error('Failed to capture screenshot:', err);
    }
  };

  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose();
  };

  const currentPose = jobResult?.poses[selectedPoseIndex];

  return (
    <div className="dialog-overlay" onClick={handleOverlayClick}>
      <div className="dialog-xl">
        {/* Header */}
        <div className="dialog-header">
          <div>
            <h3 style={{ fontSize: '14px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px', margin: 0 }}>
              <span>🛰️ {viewMode === '3d' ? '3D Viewport' : '2D Interaction Map'}</span>
              {currentPose && (
                <span style={{
                  fontSize: '9px',
                  fontWeight: 600,
                  color: 'var(--color-brand-700)',
                  background: 'var(--color-brand-100)',
                  padding: '2px 8px',
                  borderRadius: '10px',
                  border: '0.5px solid var(--color-brand-50)'
                }}>
                  Pose #{currentPose.pose_index} · {currentPose.score_kcal_per_mol.toFixed(1)} kcal/mol
                </span>
              )}
            </h3>
            {jobResult && (
              <p style={{ fontSize: '11px', color: 'var(--color-text-500)', marginTop: '2px', marginBottom: 0 }}>
                Receptor: <b>{jobResult.receptor_display_name || 'ALS'}</b> · Ligand: <b>{jobResult.ligand_display_name || 'Analogue'}</b>
              </p>
            )}
          </div>

          {/* Premium Glassmorphic Segmented View Mode Toggle */}
          {!fallbackMode && (
            <div className="view-mode-toggle" style={{
              display: 'flex',
              background: 'var(--color-bg)',
              border: '0.5px solid var(--color-border)',
              borderRadius: '6px',
              padding: '2px',
              marginRight: '16px'
            }}>
              <button
                className={`view-mode-btn ${viewMode === '3d' ? 'active' : ''}`}
                onClick={() => setViewMode('3d')}
                style={{
                  padding: '4px 12px',
                  fontSize: '11px',
                  fontWeight: 500,
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  background: viewMode === '3d' ? 'var(--color-surface)' : 'transparent',
                  color: viewMode === '3d' ? 'var(--color-brand-700)' : 'var(--color-text-600)',
                  boxShadow: viewMode === '3d' ? 'var(--shadow-sm)' : 'none',
                  transition: 'all 0.2s'
                }}
              >
                3D View
              </button>
              <button
                className={`view-mode-btn ${viewMode === '2d' ? 'active' : ''}`}
                onClick={() => setViewMode('2d')}
                style={{
                  padding: '4px 12px',
                  fontSize: '11px',
                  fontWeight: 500,
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  background: viewMode === '2d' ? 'var(--color-surface)' : 'transparent',
                  color: viewMode === '2d' ? 'var(--color-brand-700)' : 'var(--color-text-600)',
                  boxShadow: viewMode === '2d' ? 'var(--shadow-sm)' : 'none',
                  transition: 'all 0.2s'
                }}
              >
                2D Map
              </button>
            </div>
          )}

          <button className="dialog-close" onClick={onClose}>×</button>
        </div>

        {/* Body */}
        <div className="dialog-body">
          {error && (
            <div style={{ padding: '20px', color: 'var(--color-red-600)', background: 'var(--color-red-50)', border: '0.5px solid var(--color-red-200)', borderRadius: '6px', margin: '16px', fontSize: '12px' }}>
              <b>Error:</b> {error}
            </div>
          )}

          <div className="interaction-viewer-layout">
            {/* Viewport — 3D or 2D fallback / map */}
            <div className="interaction-viewer-viewport-container">
              {viewMode === '2d' ? (
                /* 2D Interaction Map View */
                <div style={{
                  width: '100%',
                  height: '100%',
                  flex: 1,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'flex-start',
                  overflowY: 'auto',
                  gap: '16px',
                  padding: '12px 24px',
                  boxSizing: 'border-box',
                  background: bgColor === 'white' ? '#ffffff' : bgColor === 'pale-grey' ? (theme === 'dark' ? '#09090b' : '#f8fafc') : '#0f172a'
                }}>
                  {fallbackMode && (
                    <div style={{
                      padding: '10px 16px',
                      background: 'rgba(37, 99, 235, 0.06)',
                      border: '0.5px solid rgba(37, 99, 235, 0.2)',
                      borderRadius: '8px',
                      fontSize: '11px',
                      color: 'var(--color-text-600)',
                      textAlign: 'center',
                      maxWidth: '400px'
                    }}>
                      <b style={{ color: '#2563eb' }}>ℹ 2D Interaction View</b>
                      <br />
                      <span style={{ fontSize: '10px', opacity: 0.85 }}>
                        3D visualization is unavailable. Showing 2D depiction with binding interaction data.
                      </span>
                    </div>
                  )}

                  {loading2dMap ? (
                    <div style={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      gap: '8px',
                      color: 'var(--color-text-500)',
                      fontSize: '11px'
                    }}>
                      <RefreshCw style={{ animation: 'spin 2s linear infinite' }} size={16} />
                      <span>Generating 2D Map...</span>
                    </div>
                  ) : interactionMapSvg ? (
                    <div
                      style={{
                        width: '100%',
                        maxWidth: '480px',
                        maxHeight: '75%',
                        height: 'auto',
                        aspectRatio: '450 / 350',
                        background: 'white',
                        borderRadius: '12px',
                        padding: '16px',
                        boxShadow: 'var(--shadow-sm)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        transition: 'all 0.3s ease'
                      }}
                      dangerouslySetInnerHTML={{
                        __html: interactionMapSvg
                          .replace(/width=['"][^'"]*['"]/, 'width="100%"')
                          .replace(/height=['"][^'"]*['"]/, 'height="100%"')
                      }}
                    />
                  ) : (
                    <div style={{
                      width: '300px',
                      height: '220px',
                      background: 'var(--color-bg)',
                      borderRadius: '12px',
                      border: '0.5px solid var(--color-border)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '11px',
                      color: 'var(--color-text-400)'
                    }}>
                      2D structure not available
                    </div>
                  )}

                  {ligandSmiles && (
                    <div style={{
                      fontSize: '10px',
                      color: 'var(--color-text-500)',
                      fontFamily: 'var(--font-mono, monospace)',
                      wordBreak: 'break-all',
                      maxWidth: '380px',
                      textAlign: 'center',
                      background: 'var(--color-bg)',
                      padding: '6px 12px',
                      borderRadius: '6px',
                      border: '0.5px solid var(--color-border)'
                    }}>
                      {ligandSmiles}
                    </div>
                  )}

                  {currentPose && (
                    <div style={{
                      display: 'flex',
                      gap: '12px',
                      fontSize: '10px',
                      color: 'var(--color-text-600)'
                    }}>
                      <span>Pose #{currentPose.pose_index}</span>
                      <span>•</span>
                      <span style={{ fontWeight: 600 }}>{currentPose.score_kcal_per_mol.toFixed(1)} kcal/mol</span>
                    </div>
                  )}
                </div>
              ) : (
                /* 3D NGL Viewport */
                <>
                  <div ref={viewportRef} style={{ width: '100%', height: '100%', position: 'relative' }} />

              {/* Viewport Toolbar */}
              <div className="viewport-floating-toolbar">
                <button 
                  className={`toolbar-float-btn ${isSpinning ? 'active' : ''}`}
                  onClick={() => setIsSpinning(p => !p)}
                  title="Toggle orbital camera spin"
                >
                  <Rotate3d size={13} className={isSpinning ? 'animate-spin' : ''} />
                  <span>Spin</span>
                </button>
                <button 
                  className="toolbar-float-btn"
                  onClick={focusLigand}
                  title="Focus camera on ligand"
                >
                  <Maximize2 size={13} />
                  <span>Focus Pose</span>
                </button>
                <button 
                  className="toolbar-float-btn"
                  onClick={resetCamera}
                  title="Reset global view"
                >
                  <RefreshCw size={13} />
                  <span>Reset</span>
                </button>
                <div style={{ width: '1px', height: '14px', background: 'rgba(255,255,255,0.15)' }} />
                <button 
                  className={`toolbar-float-btn ${cameraType === 'orthographic' ? 'active' : ''}`}
                  onClick={() => setCameraType(p => p === 'perspective' ? 'orthographic' : 'perspective')}
                  title="Toggle perspective/orthographic view"
                >
                  <span>{cameraType === 'perspective' ? 'Perspective' : 'Orthographic'}</span>
                </button>
                <button 
                  className="toolbar-float-btn highlight-capture"
                  onClick={captureScreenshot}
                  title="Take a high-resolution snapshot"
                >
                  <Camera size={13} />
                  <span>Snapshot</span>
                </button>
              </div>

              {/* Status Overlay */}
              {loading && (
                <div className="viewport-status-overlay">
                  <div className="spinner"></div>
                  <span>Loading structures...</span>
                </div>
              )}
                </>
              )}
            </div>

            {/* Sidebar */}
            <div className="interaction-viewer-sidebar">
              {/* Pose Selection */}
              {jobResult && jobResult.poses && jobResult.poses.length > 0 && (
                <div>
                  <div className="interaction-viewer-sidebar-title">
                    <Sliders size={12} className="text-brand-500" />
                    <span>Select Docked Pose</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <button
                      onClick={handlePrevPose}
                      disabled={!hasPrev}
                      className="workflow-btn-configure"
                      style={{
                        padding: '6px 8px',
                        fontSize: '11px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        cursor: hasPrev ? 'pointer' : 'default',
                        opacity: hasPrev ? 1 : 0.4,
                        minWidth: '28px',
                        height: '28px',
                        border: '0.5px solid var(--color-border)',
                        borderRadius: '6px'
                      }}
                      title="Previous Pose (Left Arrow)"
                    >
                      <ChevronLeft size={14} />
                    </button>
                    <select
                      value={selectedPoseIndex}
                      onChange={(e) => handlePoseChange(parseInt(e.target.value))}
                      className="preset-select"
                      style={{ flex: 1, padding: '6px', fontSize: '11px', height: '28px' }}
                    >
                      {jobResult.poses.map((p, i) => {
                        const isSeed = !clusters || clusters.some(c => c[0] === p.pose_index);
                        const clusterIdx = clusters ? clusters.findIndex(c => c.includes(p.pose_index)) : -1;
                        
                        if (showRepresentativesOnly && !isSeed) return null;
                        
                        let label = `Pose #${p.pose_index}`;
                        if (clusters && clusterIdx !== -1) {
                          label += ` (Cluster ${clusterIdx + 1}${isSeed ? ' Seed' : ''})`;
                        }
                        label += ` (${p.score_kcal_per_mol.toFixed(1)} kcal/mol)`;
                        
                        return (
                          <option key={i} value={i}>
                            {label}
                          </option>
                        );
                      })}
                    </select>
                    <button
                      onClick={handleNextPose}
                      disabled={!hasNext}
                      className="workflow-btn-configure"
                      style={{
                        padding: '6px 8px',
                        fontSize: '11px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        cursor: hasNext ? 'pointer' : 'default',
                        opacity: hasNext ? 1 : 0.4,
                        minWidth: '28px',
                        height: '28px',
                        border: '0.5px solid var(--color-border)',
                        borderRadius: '6px'
                      }}
                      title="Next Pose (Right Arrow)"
                    >
                      <ChevronRight size={14} />
                    </button>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '8px' }}>
                    <button
                      onClick={handleClusterPoses}
                      disabled={clustering || !jobResult || !jobResult.poses || jobResult.poses.length < 2}
                      className="workflow-btn-configure"
                      style={{
                        width: '100%',
                        padding: '6px 12px',
                        fontSize: '11px',
                        fontWeight: 600,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '6px',
                        cursor: 'pointer'
                      }}
                    >
                      {clustering ? '⏳ Clustering...' : '⚡ Cluster Poses (2.0 Å)'}
                    </button>
                    
                    {clusters && (
                      <label style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        fontSize: '10px',
                        fontWeight: 500,
                        color: 'var(--color-text-600)',
                        cursor: 'pointer',
                        marginTop: '4px'
                      }}>
                        <input
                          type="checkbox"
                          checked={showRepresentativesOnly}
                          onChange={(e) => {
                            const active = e.target.checked;
                            setShowRepresentativesOnly(active);
                            if (active) {
                              const representatives = clusters.map(c => c[0]);
                              const currentPoseNum = jobResult.poses[selectedPoseIndex].pose_index;
                              if (!representatives.includes(currentPoseNum)) {
                                const matchingCluster = clusters.find(c => c.includes(currentPoseNum));
                                const targetPoseNum = matchingCluster ? matchingCluster[0] : representatives[0];
                                const targetIdx = jobResult.poses.findIndex(p => p.pose_index === targetPoseNum);
                                if (targetIdx !== -1) {
                                  handlePoseChange(targetIdx);
                                }
                              }
                            }
                          }}
                          style={{ accentColor: 'var(--color-brand-600)', cursor: 'pointer' }}
                        />
                        Show cluster seeds (representatives) only
                      </label>
                    )}
                  </div>
                </div>
              )}

              {/* Interactions list */}
              <div>
                <div className="interaction-viewer-sidebar-title">
                  <Activity size={12} className="text-brand-500" />
                  <span>Receptor Contacts</span>
                </div>

                {loadingInteractions ? (
                  <div style={{ fontSize: '10px', color: 'var(--color-text-500)', padding: '10px 0', textAlign: 'center' }}>
                    <RefreshCw style={{ animation: 'spin 2s linear infinite', width: '12px', height: '12px', display: 'inline', marginRight: '6px' }} />
                    Calculating maps...
                  </div>
                ) : interactions ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {/* H-Bond Donors */}
                    {interactions.hbond_donor && interactions.hbond_donor.length > 0 && (
                      <div className="interaction-group-box">
                        <div style={{ fontSize: '9px', fontWeight: 700, color: 'var(--color-text-800)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.02em' }}>Hydrogen Bond Donors</div>
                        <div className="interaction-group-items">
                          {interactions.hbond_donor.map((hb: any, i: number) => (
                            <button key={i} className="interaction-item-btn" onClick={() => focusResidue(hb.residue)}>
                              <span>{hb.residue} ({hb.ligand_atom})</span>
                              <span className="interaction-item-distance">{hb.distance.toFixed(2)} Å</span>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* H-Bond Acceptors */}
                    {interactions.hbond_acceptor && interactions.hbond_acceptor.length > 0 && (
                      <div className="interaction-group-box">
                        <div style={{ fontSize: '9px', fontWeight: 700, color: 'var(--color-text-800)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.02em' }}>Hydrogen Bond Acceptors</div>
                        <div className="interaction-group-items">
                          {interactions.hbond_acceptor.map((hb: any, i: number) => (
                            <button key={i} className="interaction-item-btn" onClick={() => focusResidue(hb.residue)}>
                              <span>{hb.residue} ({hb.ligand_atom})</span>
                              <span className="interaction-item-distance">{hb.distance.toFixed(2)} Å</span>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Hydrophobic Contacts */}
                    {interactions.hydrophobic && interactions.hydrophobic.length > 0 && (
                      <div className="interaction-group-box">
                        <div style={{ fontSize: '9px', fontWeight: 700, color: 'var(--color-text-800)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.02em' }}>Hydrophobic Contacts</div>
                        <div className="interaction-group-items">
                          {interactions.hydrophobic.map((hp: any, i: number) => (
                            <button key={i} className="interaction-item-btn" onClick={() => focusResidue(hp.residue)}>
                              <span>{hp.residue} ({hp.ligand_atom})</span>
                              <span className="interaction-item-distance">{hp.distance.toFixed(2)} Å</span>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Pi Stacking */}
                    {interactions.pi_stacking && interactions.pi_stacking.length > 0 && (
                      <div className="interaction-group-box">
                        <div style={{ fontSize: '9px', fontWeight: 700, color: 'var(--color-text-800)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.02em' }}>Pi-Stacking Interactions</div>
                        <div className="interaction-group-items">
                          {interactions.pi_stacking.map((pi: any, i: number) => (
                            <button key={i} className="interaction-item-btn" onClick={() => focusResidue(pi.residue)}>
                              <span>{pi.residue} ({pi.ligand_atom})</span>
                              <span className="interaction-item-distance">{pi.distance.toFixed(2)} Å</span>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Salt Bridges */}
                    {interactions.salt_bridge && interactions.salt_bridge.length > 0 && (
                      <div className="interaction-group-box">
                        <div style={{ fontSize: '9px', fontWeight: 700, color: 'var(--color-text-800)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.02em' }}>Salt Bridges</div>
                        <div className="interaction-group-items">
                          {interactions.salt_bridge.map((sb: any, i: number) => (
                            <button key={i} className="interaction-item-btn" onClick={() => focusResidue(sb.residue)}>
                              <span>{sb.residue} ({sb.ligand_atom})</span>
                              <span className="interaction-item-distance">{sb.distance.toFixed(2)} Å</span>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {(!interactions.hbond_donor?.length &&
                      !interactions.hbond_acceptor?.length &&
                      !interactions.hydrophobic?.length &&
                      !interactions.pi_stacking?.length &&
                      !interactions.salt_bridge?.length) && (
                      <div style={{ fontSize: '10px', color: 'var(--color-text-400)', textAlign: 'center', padding: '10px 0' }}>
                        No close binding pocket interactions detected.
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={{ fontSize: '10px', color: 'var(--color-text-400)', textAlign: 'center', padding: '10px 0' }}>
                    No interaction data available.
                  </div>
                )}
              </div>

              {/* Theme Settings */}
              <div>
                <div className="interaction-viewer-sidebar-title">
                  <span>Background Theme</span>
                </div>
                <div className="bg-theme-switcher" style={{ marginTop: '4px' }}>
                  <button className={`theme-btn ${bgColor === 'white' ? 'active' : ''}`} onClick={() => setBgColor('white')}>
                    <span className="color-swatch swatch-white" />
                    <span>White</span>
                  </button>
                  <button className={`theme-btn ${bgColor === 'pale-grey' ? 'active' : ''}`} onClick={() => setBgColor('pale-grey')}>
                    <span className="color-swatch swatch-pale-grey" />
                    <span>Grey</span>
                  </button>
                  <button className={`theme-btn ${bgColor === 'black' ? 'active' : ''}`} onClick={() => setBgColor('black')}>
                    <span className="color-swatch swatch-black" />
                    <span>Black</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
