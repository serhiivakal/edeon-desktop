import { useState, useEffect } from 'react';
import { useWorkflowStore } from '../../store/workflowStore';
import { useCompoundStore } from '../../store/compoundStore';
import { useProjectStore } from '../../store/projectStore';
import { useUIStore } from '../../store/uiStore';
import { RiskBadge } from '../shared/RiskBadge';
import { UqBadge } from '../uq/UqBadge';
import { IntervalBar } from '../uq/IntervalBar';
import { useResizableColumns } from '../../hooks/useResizableColumns';
import type { RiskLevel, PropertyFilters } from '../../types';
import { invoke } from '@tauri-apps/api/core';
import { useFateStore } from '../../store/fateStore';

export function ResultsTable() {
  const { widths, tableRef, handleMouseDown } = useResizableColumns([12, 20, 9, 9, 9, 9, 12, 10, 10]);
  const results = useWorkflowStore((s) => s.results);
  const isRunning = useWorkflowStore((s) => s.isRunning);
  const activeWorkflow = useWorkflowStore((s) => s.activeWorkflow);
  const fetchResults = useWorkflowStore((s) => s.fetchResults);
  const selectedWorkflowType = useWorkflowStore((s) => s.selectedWorkflowType);

  const fatePredictions = useFateStore((s) => s.predictions);
  const computeEnvironmentalFate = useFateStore((s) => s.computeEnvironmentalFate);

  useEffect(() => {
    if (results.length > 0 && selectedWorkflowType !== 'library_prep') {
      const smilesList = results.map(r => r.smiles);
      computeEnvironmentalFate(smilesList).catch(err => {
        console.error('Failed to compute environmental fate:', err);
      });
    }
  }, [results, selectedWorkflowType, computeEnvironmentalFate]);

  const selectedReceptorPreset = useWorkflowStore((s) => s.selectedReceptorPreset);
  const selectedId = useUIStore((s) => s.selectedCompoundId);
  const setSelected = useUIStore((s) => s.setSelectedCompound);
  const mcsActive = useUIStore((s) => s.mcsActive);
  const mcsLoading = useUIStore((s) => s.mcsLoading);
  const computeMcs = useUIStore((s) => s.computeMcs);
  const clearMcs = useUIStore((s) => s.clearMcs);

  const isMaximized = useUIStore((s) => s.isResultsTableMaximized);
  const tableHeight = useUIStore((s) => s.resultsTableHeight);
  const setTableHeight = useUIStore((s) => s.setResultsTableHeight);
  const toggleMaximized = useUIStore((s) => s.toggleResultsTableMaximized);

  const handleDragStart = (e: React.MouseEvent) => {
    e.preventDefault();
    const startY = e.clientY;
    const startHeight = tableHeight;

    const handleMouseMove = (moveEvent: MouseEvent) => {
      const deltaY = moveEvent.clientY - startY;
      const newHeight = Math.max(150, Math.min(window.innerHeight - 250, startHeight - deltaY));
      setTableHeight(newHeight);
    };

    const handleMouseUp = () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  };

  const activeProjectId = useProjectStore((s) => s.activeProjectId);
  const fetchProjects = useProjectStore((s) => s.fetchProjects);
  const deleteCompounds = useCompoundStore((s) => s.deleteCompounds);

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [lastSelectedId, setLastSelectedId] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const setActiveInteractionJobId = useWorkflowStore((s) => s.setActiveInteractionJobId);
  const storeDockingJobId = useWorkflowStore((s) => s.dockingJobId);
  const [hasDockingJob, setHasDockingJob] = useState<boolean>(false);
  const [dockingJobId, setDockingJobId] = useState<string | null>(null);

  const selectedCompound = results.find((r) => r.id === selectedId);

  useEffect(() => {
    if (!selectedCompound) {
      // Still allow fallback to store's dockingJobId for bioisostere workflow
      if (storeDockingJobId && selectedWorkflowType === 'bioisostere_opt') {
        setHasDockingJob(true);
        setDockingJobId(storeDockingJobId);
      } else {
        setHasDockingJob(false);
        setDockingJobId(null);
      }
      return;
    }
    
    // Check if there's any docking job in history for this compound's SMILES
    invoke<any[]>('history_list', {
      receptorId: null,
      starredOnly: null,
      searchQuery: selectedCompound.smiles
    }).then(jobs => {
      const presetMap: Record<string, string> = {
        als: 'ALS',
        accase: 'ACCase',
        epsps: 'EPSPS',
        gs: 'GS',
        hppd: 'HPPD',
        ppo: 'PPO',
        ps2: 'PSII',
        sdh: 'SDH',
      };
      const targetReceptorName = (presetMap[selectedReceptorPreset.toLowerCase()] || selectedReceptorPreset).toUpperCase();
      
      const match = jobs.find(j => 
        j.ligand_smiles === selectedCompound.smiles &&
        j.receptor_display_name?.toUpperCase() === targetReceptorName
      );
      if (match) {
        setHasDockingJob(true);
        setDockingJobId(match.job_id);
      } else if (storeDockingJobId && selectedWorkflowType === 'bioisostere_opt') {
        // Fallback: use the store's cached dockingJobId from the bioisostere workflow
        setHasDockingJob(true);
        setDockingJobId(storeDockingJobId);
      } else {
        setHasDockingJob(false);
        setDockingJobId(null);
      }
    }).catch(err => {
      console.error('Failed to search docking history:', err);
      // Fallback: use the store's cached dockingJobId
      if (storeDockingJobId && selectedWorkflowType === 'bioisostere_opt') {
        setHasDockingJob(true);
        setDockingJobId(storeDockingJobId);
      } else {
        setHasDockingJob(false);
        setDockingJobId(null);
      }
    });
  }, [selectedCompound, storeDockingJobId, selectedWorkflowType, selectedReceptorPreset]);
  const [contextMenu, setContextMenu] = useState<{
    ids: string[];
    name: string;
    x: number;
    y: number;
  } | null>(null);
  const [showExportDropdown, setShowExportDropdown] = useState(false);

  const handleExportCSV = () => {
    if (results.length === 0) return;
    const headers = [
      'Rank', 'Name', 'SMILES', 'MW', 'LogP', 'TPSA', 'HBD', 'HBA', 'RotBonds',
      'Pesticide Likeness', 'Toxicity Level', 'Selectivity Index', 'Resistance Level', 'MPO Score'
    ];
    const csvRows = [headers.join(',')];
    sortedResults.forEach((r, index) => {
      const esc = (val: any) => {
        const s = val === null || val === undefined ? '' : String(val);
        if (s.includes(',') || s.includes('"') || s.includes('\n')) {
          return `"${s.replace(/"/g, '""')}"`;
        }
        return s;
      };
      const row = [
        index + 1,
        esc(r.name),
        esc(r.smiles),
        r.mol_weight ?? '',
        r.logp ?? '',
        r.tpsa ?? '',
        r.hbd ?? '',
        r.hba ?? '',
        r.rotatable_bonds ?? '',
        esc(r.pesticide_likeness_disabled ? 'Excluded' : r.pesticide_likeness),
        esc(r.toxicity?.disabled ? 'Excluded' : r.toxicity?.overall_level),
        r.selectivity?.disabled ? 'Excluded' : (r.selectivity?.min_selectivity ? `${r.selectivity.min_selectivity}x` : ''),
        esc(r.resistance?.disabled ? 'Excluded' : r.resistance?.level),
        r.score ?? ''
      ];
      csvRows.push(row.join(','));
    });
    const csvContent = csvRows.join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `edeon_workflow_results_${activeWorkflow?.name?.toLowerCase().replace(/[^a-z0-9]+/g, '_') || 'export'}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setToast({ message: 'CSV exported successfully!', type: 'success' });
  };

  const handleExportSDF = async () => {
    if (!activeWorkflow) return;
    setToast({ message: 'Generating SDF conformers via RDKit...', type: 'success' });
    try {
      const sdfString = await invoke<string>('export_results_sdf', {
        workflowId: activeWorkflow.id
      });
      const blob = new Blob([sdfString], { type: 'text/plain;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.setAttribute('href', url);
      link.setAttribute('download', `edeon_workflow_results_${activeWorkflow.name.toLowerCase().replace(/[^a-z0-9]+/g, '_')}.sdf`);
      link.style.visibility = 'hidden';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      setToast({ message: 'SDF exported successfully!', type: 'success' });
    } catch (e) {
      console.error('SDF export failed:', e);
      setToast({ message: `SDF export failed: ${String(e)}`, type: 'error' });
    }
  };

  const [sortCol, setSortCol] = useState<string>('score');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  const handleSort = (column: string) => {
    if (sortCol === column) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortCol(column);
      setSortDir('desc');
    }
  };

  const getSortedResults = (list: typeof results) => {
    const sorted = [...list];
    sorted.sort((a, b) => {
      let valA: any = null;
      let valB: any = null;

      if (sortCol === 'name') {
        valA = (a.name || '').toLowerCase();
        valB = (b.name || '').toLowerCase();
      } else if (sortCol === 'smiles') {
        valA = (a.smiles || '').toLowerCase();
        valB = (b.smiles || '').toLowerCase();
      } else if (sortCol === 'pesticide_likeness') {
        const map: Record<string, number> = { 'high': 3, 'med': 2, 'low': 1 };
        valA = map[(a.pesticide_likeness || 'low').toLowerCase()] || 0;
        valB = map[(b.pesticide_likeness || 'low').toLowerCase()] || 0;
      } else if (sortCol === 'toxicity') {
        const map: Record<string, number> = { 'high': 3, 'med': 2, 'low': 1 };
        valA = map[(a.toxicity?.overall_level || 'low').toLowerCase()] || 0;
        valB = map[(b.toxicity?.overall_level || 'low').toLowerCase()] || 0;
      } else if (sortCol === 'selectivity') {
        valA = a.selectivity?.min_selectivity ?? 0;
        valB = b.selectivity?.min_selectivity ?? 0;
      } else if (sortCol === 'resistance') {
        const map: Record<string, number> = { 'high': 3, 'med': 2, 'low': 1 };
        valA = map[(a.resistance?.level || 'low').toLowerCase()] || 0;
        valB = map[(b.resistance?.level || 'low').toLowerCase()] || 0;
      } else if (sortCol === 'rank') {
        const map: Record<string, number> = { 'lead': 3, 'candidate': 2, 'deprioritize': 1 };
        valA = map[(a.mpo?.rank_category || 'deprioritize').toLowerCase()] || 0;
        valB = map[(b.mpo?.rank_category || 'deprioritize').toLowerCase()] || 0;
      } else if (sortCol === 'mol_weight') {
        valA = a.mol_weight ?? 0;
        valB = b.mol_weight ?? 0;
      } else if (sortCol === 'logp') {
        valA = a.logp ?? 0;
        valB = b.logp ?? 0;
      } else if (sortCol === 'tpsa') {
        valA = a.tpsa ?? 0;
        valB = b.tpsa ?? 0;
      } else if (sortCol === 'score') {
        valA = a.score ?? 0;
        valB = b.score ?? 0;
      } else if (sortCol === 'fate') {
        const fateA = fatePredictions[a.smiles];
        const fateB = fatePredictions[b.smiles];
        valA = fateA?.gus?.value?.kind === 'numeric' && fateA.gus.value.numeric != null ? fateA.gus.value.numeric : 0;
        valB = fateB?.gus?.value?.kind === 'numeric' && fateB.gus.value.numeric != null ? fateB.gus.value.numeric : 0;
      }


      if (valA < valB) return sortDir === 'asc' ? -1 : 1;
      if (valA > valB) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });
    return sorted;
  };

  const sortIndicator = (column: string) => {
    if (sortCol !== column) return '';
    return sortDir === 'asc' ? ' ▴' : ' ▾';
  };

  const [showFilters, setShowFilters] = useState(false);
  const [localFilters, setLocalFilters] = useState<PropertyFilters & { score_min?: number | null; score_max?: number | null }>({});

  const filteredResults = results.filter((r) => {
    if (localFilters.mw_min != null && (r.mol_weight == null || r.mol_weight < localFilters.mw_min)) return false;
    if (localFilters.mw_max != null && (r.mol_weight == null || r.mol_weight > localFilters.mw_max)) return false;
    if (localFilters.logp_min != null && (r.logp == null || r.logp < localFilters.logp_min)) return false;
    if (localFilters.logp_max != null && (r.logp == null || r.logp > localFilters.logp_max)) return false;
    if (localFilters.tpsa_min != null && (r.tpsa == null || r.tpsa < localFilters.tpsa_min)) return false;
    if (localFilters.tpsa_max != null && (r.tpsa == null || r.tpsa > localFilters.tpsa_max)) return false;
    if (localFilters.hbd_min != null && (r.hbd == null || r.hbd < localFilters.hbd_min)) return false;
    if (localFilters.hbd_max != null && (r.hbd == null || r.hbd > localFilters.hbd_max)) return false;
    if (localFilters.score_min != null && (r.score == null || r.score < localFilters.score_min)) return false;
    if (localFilters.score_max != null && (r.score == null || r.score > localFilters.score_max)) return false;
    return true;
  });

  const sortedResults = getSortedResults(filteredResults);

  // Close context menu on click outside
  useEffect(() => {
    if (!contextMenu) return;
    const handler = () => setContextMenu(null);
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, [contextMenu]);

  // Close export dropdown on click outside
  useEffect(() => {
    if (!showExportDropdown) return;
    const handler = () => setShowExportDropdown(false);
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, [showExportDropdown]);

  // Auto-select first compound if none selected or selection is invalid for these results
  useEffect(() => {
    if (sortedResults.length > 0) {
      const exists = sortedResults.some(r => r.id === selectedId);
      if (!exists) {
        setSelected(sortedResults[0].id);
      }
    }
  }, [filteredResults, sortCol, sortDir, selectedId, setSelected]);

  // Auto-dismiss toast
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(t);
  }, [toast]);

  useEffect(() => {
    if (selectedWorkflowType === 'library_prep' && sortCol === 'score') {
      setSortCol('name');
    }
  }, [selectedWorkflowType, sortCol]);

  if (!activeWorkflow && !isRunning) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center', color: 'var(--color-text-400)' }}>
          <div style={{ fontSize: '28px', marginBottom: '8px', opacity: 0.6 }}>🧪</div>
          <p style={{ fontSize: '12px' }}>Start a workflow to see results here</p>
        </div>
      </div>
    );
  }

  if (isRunning && results.length === 0) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center', color: 'var(--color-text-400)' }}>
          <div style={{ fontSize: '28px', marginBottom: '8px' }}>⏳</div>
          <p style={{ fontSize: '12px' }}>Workflow running... results will appear when complete</p>
        </div>
      </div>
    );
  }

  const toRisk = (level: string | null | undefined): RiskLevel => {
    if (level === 'High' || level === 'Med' || level === 'Low') return level;
    return 'Low';
  };

  return (
    <div 
      style={{ 
        flex: isMaximized ? 1 : 'none', 
        height: isMaximized ? '100%' : `${tableHeight}px`, 
        display: 'flex', 
        flexDirection: 'column', 
        minHeight: 0,
        position: 'relative',
        paddingTop: isMaximized ? 0 : '12px'
      }}
    >
      {/* Drag resize handle */}
      {!isMaximized && (
        <div
          onMouseDown={handleDragStart}
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            height: '12px',
            cursor: 'row-resize',
            background: 'transparent',
            zIndex: 50,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          className="table-row-resize-handle"
          title="Drag up or down to resize table height"
        >
          <div 
            style={{
              width: '36px',
              height: '4px',
              borderRadius: '2px',
              background: 'var(--color-border)',
              opacity: 0.5,
              transition: 'all 0.2s ease',
            }}
            className="resize-bar-visual"
          />
        </div>
      )}
      {/* Header */}
      <div className="results-header">
        <span className="results-title">
          RESULTS · {filteredResults.length} COMPOUNDS
        </span>
        <div className="results-actions">
          {selectedWorkflowType === 'library_prep' && (
            <>
              <button
                className="results-action active"
                style={{
                  background: 'var(--color-brand-600)',
                  color: 'white',
                  border: '0.5px solid var(--color-brand-700)',
                  borderRadius: '4px',
                  padding: '4px 12px',
                  fontWeight: 600,
                  boxShadow: 'var(--shadow-sm)',
                  cursor: 'pointer'
                }}
                onClick={() => {
                  const exportData = useWorkflowStore.getState().libraryPrepExportData;
                  const fileName = useWorkflowStore.getState().libraryPrepFileName;
                  if (!exportData || !fileName) return;

                  const blob = new Blob([exportData], { type: 'text/plain;charset=utf-8;' });
                  const url = URL.createObjectURL(blob);
                  const link = document.createElement('a');
                  link.setAttribute('href', url);
                  link.setAttribute('download', fileName);
                  link.style.visibility = 'hidden';
                  document.body.appendChild(link);
                  link.click();
                  document.body.removeChild(link);
                }}
                title="Download the fully parsed, filtered, and optimized 3D conformer library"
              >
                📥 Download Curated Library
              </button>
              <button
                className="results-action active"
                style={{
                  background: 'var(--color-blue-500)',
                  color: 'white',
                  border: '0.5px solid var(--color-blue-700)',
                  borderRadius: '4px',
                  padding: '4px 12px',
                  fontWeight: 600,
                  boxShadow: 'var(--shadow-sm)',
                  cursor: 'pointer'
                }}
                onClick={() => {
                  const exportData = useWorkflowStore.getState().libraryPrepExportData;
                  const fileName = useWorkflowStore.getState().libraryPrepFileName;
                  if (!exportData || !fileName) return;

                  const extension = fileName.split('.').pop() || 'smi';
                  useWorkflowStore.getState().reset();
                  useWorkflowStore.getState().setUploadedFile({
                    name: fileName,
                    contents: exportData,
                    extension: extension
                  });
                  useWorkflowStore.getState().setWorkflowType('active_learning');
                }}
                title="Send the prepared library directly to the Virtual Screening & Active Learning Gate"
              >
                🚀 Send to VS workflow
              </button>
            </>
          )}
          <button
            className={`results-action ${mcsActive ? 'active' : ''}`}
            onClick={() => {
              if (mcsActive) {
                clearMcs();
              } else {
                const smiles = results.map((r) => r.smiles).filter(Boolean);
                computeMcs(smiles);
              }
            }}
            disabled={mcsLoading || results.length < 2}
            title="Find Maximum Common Substructure across all compounds"
          >
            {mcsLoading ? '⏳ Computing...' : mcsActive ? '✕ Clear MCS' : '🔗 Find MCS'}
          </button>
          {hasDockingJob && (
            <button
              className="results-action active"
              style={{
                background: 'rgba(37, 99, 235, 0.08)',
                border: '0.5px solid rgba(37, 99, 235, 0.25)',
                color: '#2563eb',
                fontWeight: 500
              }}
              onClick={() => {
                if (dockingJobId) {
                  setActiveInteractionJobId(dockingJobId);
                }
              }}
              title="Inspect 3D binding poses and mapped non-covalent interactions in a separate window"
            >
              👁 View 3D Interactions
            </button>
          )}
          <button
            className={`results-action ${Object.keys(localFilters).length > 0 ? 'active' : ''}`}
            onClick={() => setShowFilters(!showFilters)}
            title="Filter workflow results by property ranges"
          >
            ⌕ Filter
          </button>
          {Object.keys(localFilters).length > 0 && (
            <button
              className="results-action"
              style={{ color: 'var(--color-red-600)' }}
              onClick={() => setLocalFilters({})}
              title="Discard all active range filters"
            >
              ✕ Clear Filters
            </button>
          )}
          <div style={{ position: 'relative' }}>
            <button
              className="results-action"
              onClick={(e) => {
                e.stopPropagation();
                setShowExportDropdown(!showExportDropdown);
              }}
              title="Export results to CSV or SDF format"
            >
              ↓ Export
            </button>
            {showExportDropdown && (
              <div className="context-menu" style={{
                position: 'absolute',
                right: 0,
                top: '100%',
                marginTop: '4px',
                display: 'flex',
                flexDirection: 'column',
                zIndex: 100,
                minWidth: '160px'
              }}>
                <div className="context-menu-item" onClick={handleExportCSV}>
                  📄 Export CSV (In-Memory)
                </div>
                <div className="context-menu-item" onClick={handleExportSDF}>
                  🧬 Export SDF (RDKit)
                </div>
              </div>
            )}
          </div>
          <button
            className="results-action"
            onClick={toggleMaximized}
            title={isMaximized ? "Restore layout" : "Enlarge table / Maximize"}
            style={{
              color: isMaximized ? 'var(--color-brand-600)' : 'var(--color-text-400)',
              fontWeight: isMaximized ? 600 : 400
            }}
          >
            {isMaximized ? '❐ Restore Layout' : '⛶ Enlarge Table'}
          </button>
          {selectedIds.size > 0 && activeProjectId && (
            <button
              className="results-action"
              style={{ color: 'var(--color-red-700)', fontWeight: 500 }}
              onClick={async () => {
                const list = Array.from(selectedIds);
                const count = list.length;
                if (confirm(`Are you sure you want to delete the ${count} selected compound${count !== 1 ? 's' : ''}?`)) {
                  try {
                    await deleteCompounds(activeProjectId, list);
                    setSelectedIds(new Set());
                    setLastSelectedId(null);
                    setSelected(null);
                    setToast({ message: `Deleted ${count} compound${count !== 1 ? 's' : ''} successfully`, type: 'success' });
                    fetchProjects();
                    if (activeWorkflow) {
                      await fetchResults(activeWorkflow.id);
                    }
                  } catch (e) {
                    console.error('Failed to delete:', e);
                    setToast({ message: 'Failed to delete compounds', type: 'error' });
                  }
                }
              }}
            >
              🗑 Delete ({selectedIds.size})
            </button>
          )}
        </div>
      </div>

      {/* Property Range Filters Collapsible Panel */}
      {showFilters && (
        <div className="filter-panel" style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(5, 1fr)',
          gap: '12px',
          padding: '12px 16px',
          background: 'var(--color-surface)',
          border: '0.5px solid var(--color-border)',
          borderRadius: '8px',
          marginBottom: '16px',
          boxShadow: 'var(--shadow-sm)'
        }}>
          {/* MW Filter */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontSize: '10px', fontWeight: 600, color: 'var(--color-text-500)', textTransform: 'uppercase' }}>MW</span>
            <div style={{ display: 'flex', gap: '6px' }}>
              <input
                type="number"
                placeholder="Min"
                style={{ flex: 1, padding: '2px 6px', borderRadius: '4px', border: '0.5px solid var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text-900)', height: '22px', fontSize: '11px' }}
                value={localFilters.mw_min ?? ''}
                onChange={(e) => {
                  const val = e.target.value ? parseFloat(e.target.value) : null;
                  setLocalFilters({ ...localFilters, mw_min: val });
                }}
              />
              <input
                type="number"
                placeholder="Max"
                style={{ flex: 1, padding: '2px 6px', borderRadius: '4px', border: '0.5px solid var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text-900)', height: '22px', fontSize: '11px' }}
                value={localFilters.mw_max ?? ''}
                onChange={(e) => {
                  const val = e.target.value ? parseFloat(e.target.value) : null;
                  setLocalFilters({ ...localFilters, mw_max: val });
                }}
              />
            </div>
          </div>

          {/* LogP Filter */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontSize: '10px', fontWeight: 600, color: 'var(--color-text-500)', textTransform: 'uppercase' }}>LogP</span>
            <div style={{ display: 'flex', gap: '6px' }}>
              <input
                type="number"
                step="0.1"
                placeholder="Min"
                style={{ flex: 1, padding: '2px 6px', borderRadius: '4px', border: '0.5px solid var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text-900)', height: '22px', fontSize: '11px' }}
                value={localFilters.logp_min ?? ''}
                onChange={(e) => {
                  const val = e.target.value ? parseFloat(e.target.value) : null;
                  setLocalFilters({ ...localFilters, logp_min: val });
                }}
              />
              <input
                type="number"
                step="0.1"
                placeholder="Max"
                style={{ flex: 1, padding: '2px 6px', borderRadius: '4px', border: '0.5px solid var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text-900)', height: '22px', fontSize: '11px' }}
                value={localFilters.logp_max ?? ''}
                onChange={(e) => {
                  const val = e.target.value ? parseFloat(e.target.value) : null;
                  setLocalFilters({ ...localFilters, logp_max: val });
                }}
              />
            </div>
          </div>

          {/* TPSA Filter */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontSize: '10px', fontWeight: 600, color: 'var(--color-text-500)', textTransform: 'uppercase' }}>TPSA</span>
            <div style={{ display: 'flex', gap: '6px' }}>
              <input
                type="number"
                placeholder="Min"
                style={{ flex: 1, padding: '2px 6px', borderRadius: '4px', border: '0.5px solid var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text-900)', height: '22px', fontSize: '11px' }}
                value={localFilters.tpsa_min ?? ''}
                onChange={(e) => {
                  const val = e.target.value ? parseFloat(e.target.value) : null;
                  setLocalFilters({ ...localFilters, tpsa_min: val });
                }}
              />
              <input
                type="number"
                placeholder="Max"
                style={{ flex: 1, padding: '2px 6px', borderRadius: '4px', border: '0.5px solid var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text-900)', height: '22px', fontSize: '11px' }}
                value={localFilters.tpsa_max ?? ''}
                onChange={(e) => {
                  const val = e.target.value ? parseFloat(e.target.value) : null;
                  setLocalFilters({ ...localFilters, tpsa_max: val });
                }}
              />
            </div>
          </div>

          {/* HBD Filter */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontSize: '10px', fontWeight: 600, color: 'var(--color-text-500)', textTransform: 'uppercase' }}>HBD</span>
            <div style={{ display: 'flex', gap: '6px' }}>
              <input
                type="number"
                placeholder="Min"
                style={{ flex: 1, padding: '2px 6px', borderRadius: '4px', border: '0.5px solid var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text-900)', height: '22px', fontSize: '11px' }}
                value={localFilters.hbd_min ?? ''}
                onChange={(e) => {
                  const val = e.target.value ? parseInt(e.target.value, 10) : null;
                  setLocalFilters({ ...localFilters, hbd_min: isNaN(val as number) ? null : val });
                }}
              />
              <input
                type="number"
                placeholder="Max"
                style={{ flex: 1, padding: '2px 6px', borderRadius: '4px', border: '0.5px solid var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text-900)', height: '22px', fontSize: '11px' }}
                value={localFilters.hbd_max ?? ''}
                onChange={(e) => {
                  const val = e.target.value ? parseInt(e.target.value, 10) : null;
                  setLocalFilters({ ...localFilters, hbd_max: isNaN(val as number) ? null : val });
                }}
              />
            </div>
          </div>

          {/* Score Filter */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontSize: '10px', fontWeight: 600, color: 'var(--color-text-500)', textTransform: 'uppercase' }}>Score</span>
            <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
              <input
                type="number"
                step="0.1"
                placeholder="Min"
                style={{ flex: 1, padding: '2px 6px', borderRadius: '4px', border: '0.5px solid var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text-900)', height: '22px', fontSize: '11px' }}
                value={localFilters.score_min ?? ''}
                onChange={(e) => {
                  const val = e.target.value ? parseFloat(e.target.value) : null;
                  setLocalFilters({ ...localFilters, score_min: val });
                }}
              />
              <input
                type="number"
                step="0.1"
                placeholder="Max"
                style={{ flex: 1, padding: '2px 6px', borderRadius: '4px', border: '0.5px solid var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text-900)', height: '22px', fontSize: '11px' }}
                value={localFilters.score_max ?? ''}
                onChange={(e) => {
                  const val = e.target.value ? parseFloat(e.target.value) : null;
                  setLocalFilters({ ...localFilters, score_max: val });
                }}
              />
              {Object.keys(localFilters).length > 0 && (
                <button
                  onClick={() => setLocalFilters({})}
                  style={{
                    padding: '4px 6px',
                    borderRadius: '4px',
                    background: 'var(--color-bg)',
                    border: '0.5px solid var(--color-red-200)',
                    color: 'var(--color-red-600)',
                    fontWeight: 500,
                    cursor: 'pointer',
                    fontSize: '10px',
                    height: '22px',
                    whiteSpace: 'nowrap'
                  }}
                >
                  Clear
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="results-table-wrap" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minHeight: 0 }}>
        <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
          <table ref={tableRef} className="results-table">
            <thead>
              {selectedWorkflowType === 'library_prep' ? (
                <tr>
                  <th className="sortable" onClick={() => handleSort('name')}>
                    NAME{sortIndicator('name')}
                  </th>
                  <th className="sortable" onClick={() => handleSort('smiles')}>
                    SMILES{sortIndicator('smiles')}
                  </th>
                  <th className="center sortable" onClick={() => handleSort('mol_weight')}>
                    MW (g/mol){sortIndicator('mol_weight')}
                  </th>
                  <th className="center sortable" onClick={() => handleSort('logp')}>
                    LOGP{sortIndicator('logp')}
                  </th>
                  <th className="center sortable" onClick={() => handleSort('tpsa')}>
                    TPSA (Å²){sortIndicator('tpsa')}
                  </th>
                  <th className="center">
                    HBD / HBA
                  </th>
                  <th className="center sortable" onClick={() => handleSort('pesticide_likeness')}>
                    HERBICIDE-LIKE{sortIndicator('pesticide_likeness')}
                  </th>
                  <th className="center">
                    PAINS ALERTS
                  </th>
                  <th className="center">
                    REACTIVE ALERTS
                  </th>
                </tr>
              ) : (
                <tr>
                  <th className="sortable" style={{ width: `${widths[0]}%`, position: 'relative' }} onClick={() => handleSort('name')}>
                    NAME{sortIndicator('name')}
                    <div className="col-resize-handle" onMouseDown={(e) => handleMouseDown(0, e)} onClick={(e) => e.stopPropagation()} />
                  </th>
                  <th className="sortable" style={{ width: `${widths[1]}%`, position: 'relative' }} onClick={() => handleSort('smiles')}>
                    SMILES{sortIndicator('smiles')}
                    <div className="col-resize-handle" onMouseDown={(e) => handleMouseDown(1, e)} onClick={(e) => e.stopPropagation()} />
                  </th>
                  <th className="center sortable" style={{ width: `${widths[2]}%`, position: 'relative' }} onClick={() => handleSort('pesticide_likeness')}>
                    PEST-LIKE{sortIndicator('pesticide_likeness')}
                    <div className="col-resize-handle" onMouseDown={(e) => handleMouseDown(2, e)} onClick={(e) => e.stopPropagation()} />
                  </th>
                  <th className="center sortable" style={{ width: `${widths[3]}%`, position: 'relative' }} onClick={() => handleSort('toxicity')}>
                    TOXICITY{sortIndicator('toxicity')}
                    <div className="col-resize-handle" onMouseDown={(e) => handleMouseDown(3, e)} onClick={(e) => e.stopPropagation()} />
                  </th>
                  <th className="center sortable" style={{ width: `${widths[4]}%`, position: 'relative' }} onClick={() => handleSort('selectivity')}>
                    SELECTIVITY{sortIndicator('selectivity')}
                    <div className="col-resize-handle" onMouseDown={(e) => handleMouseDown(4, e)} onClick={(e) => e.stopPropagation()} />
                  </th>
                  <th className="center sortable" style={{ width: `${widths[5]}%`, position: 'relative' }} onClick={() => handleSort('resistance')}>
                    RESISTANCE{sortIndicator('resistance')}
                    <div className="col-resize-handle" onMouseDown={(e) => handleMouseDown(5, e)} onClick={(e) => e.stopPropagation()} />
                  </th>
                  <th className="center sortable" style={{ width: `${widths[6]}%`, position: 'relative' }} onClick={() => handleSort('fate')}>
                    FATE{sortIndicator('fate')}
                    <div className="col-resize-handle" onMouseDown={(e) => handleMouseDown(6, e)} onClick={(e) => e.stopPropagation()} />
                  </th>
                  <th className="center sortable" style={{ width: `${widths[7]}%`, position: 'relative' }} onClick={() => handleSort('rank')}>
                    RANK{sortIndicator('rank')}
                    <div className="col-resize-handle" onMouseDown={(e) => handleMouseDown(7, e)} onClick={(e) => e.stopPropagation()} />
                  </th>
                  <th className="center sortable" style={{ width: `${widths[8]}%`, position: 'relative' }} onClick={() => handleSort('score')}>
                    SCORE{sortIndicator('score')}
                    <div className="col-resize-handle" onMouseDown={(e) => handleMouseDown(8, e)} onClick={(e) => e.stopPropagation()} />
                  </th>
                </tr>
              )}
            </thead>
            <tbody>
              {sortedResults.map((compound) => {
                const isSelected = selectedId === compound.id || selectedIds.has(compound.id);
                const isOOD = compound.uq
                  ? Object.values(compound.uq).some((envelope) => envelope?.ad_status === 'out_of_domain')
                  : false;
                const fate = fatePredictions[compound.smiles];

                
                if (selectedWorkflowType === 'library_prep') {
                  return (
                    <tr
                      key={compound.id}
                      className={isSelected ? 'selected' : ''}
                      onClick={(e) => {
                        let newSelected = new Set<string>();
                        if (e.ctrlKey || e.metaKey) {
                          newSelected = new Set(selectedIds);
                          if (newSelected.has(compound.id)) {
                            newSelected.delete(compound.id);
                          } else {
                            newSelected.add(compound.id);
                            setSelected(compound.id);
                            setLastSelectedId(compound.id);
                          }
                        } else if (e.shiftKey && lastSelectedId) {
                          const lastIdx = sortedResults.findIndex(r => r.id === lastSelectedId);
                          const curIdx = sortedResults.findIndex(r => r.id === compound.id);
                          if (lastIdx !== -1 && curIdx !== -1) {
                            const start = Math.min(lastIdx, curIdx);
                            const end = Math.max(lastIdx, curIdx);
                            newSelected = new Set();
                            for (let i = start; i <= end; i++) {
                              newSelected.add(sortedResults[i].id);
                            }
                            setSelected(compound.id);
                          } else {
                            newSelected.add(compound.id);
                            setSelected(compound.id);
                            setLastSelectedId(compound.id);
                          }
                        } else {
                          newSelected.add(compound.id);
                          setSelected(compound.id);
                          setLastSelectedId(compound.id);
                        }
                        setSelectedIds(newSelected);
                      }}
                      onContextMenu={(e) => {
                        e.preventDefault();
                        let newSelected = new Set(selectedIds);
                        if (!newSelected.has(compound.id)) {
                          newSelected = new Set([compound.id]);
                          setSelected(compound.id);
                          setLastSelectedId(compound.id);
                        }
                        setSelectedIds(newSelected);
                        setContextMenu({
                          ids: Array.from(newSelected),
                          name: newSelected.size === 1 ? compound.name : `${newSelected.size} compounds`,
                          x: e.clientX,
                          y: e.clientY,
                        });
                      }}
                      style={{ cursor: 'pointer' }}
                    >
                      <td>
                        <div className="compound-name">{compound.name}</div>
                      </td>
                      <td>
                        <span className="compound-smiles selectable">{compound.smiles}</span>
                      </td>
                      <td className="center">{compound.mol_weight?.toFixed(2) ?? '—'}</td>
                      <td className="center">{compound.logp?.toFixed(2) ?? '—'}</td>
                      <td className="center">{compound.tpsa?.toFixed(1) ?? '—'}</td>
                      <td className="center">{compound.hbd ?? 0} / {compound.hba ?? 0}</td>
                      <td className="center">
                        <RiskBadge
                          level={toRisk(compound.pesticide_likeness)}
                          context="good"
                        />
                      </td>
                      <td className="center">
                        {compound.pains_alerts && compound.pains_alerts.length > 0 ? (
                          <span className="rank-badge rank-deprioritize" title={compound.pains_alerts.join(', ')}>
                            ⚠️ {compound.pains_alerts.length} PAINS
                          </span>
                        ) : (
                          <span style={{ color: 'var(--color-brand-700)', fontSize: '10px' }}>✓ None</span>
                        )}
                      </td>
                      <td className="center">
                        {compound.reactive_alerts && compound.reactive_alerts.length > 0 ? (
                          <span className="rank-badge rank-candidate" title={compound.reactive_alerts.join(', ')}>
                            ⚡ {compound.reactive_alerts.length} Alerts
                          </span>
                        ) : (
                          <span style={{ color: 'var(--color-brand-700)', fontSize: '10px' }}>✓ None</span>
                        )}
                      </td>
                    </tr>
                  );
                }

                return (
                  <tr
                    key={compound.id}
                    className={isSelected ? 'selected' : ''}
                    onClick={(e) => {
                      let newSelected = new Set<string>();
                      if (e.ctrlKey || e.metaKey) {
                        newSelected = new Set(selectedIds);
                        if (newSelected.has(compound.id)) {
                          newSelected.delete(compound.id);
                        } else {
                          newSelected.add(compound.id);
                          setSelected(compound.id);
                          setLastSelectedId(compound.id);
                        }
                      } else if (e.shiftKey && lastSelectedId) {
                        const lastIdx = sortedResults.findIndex(r => r.id === lastSelectedId);
                        const curIdx = sortedResults.findIndex(r => r.id === compound.id);
                        if (lastIdx !== -1 && curIdx !== -1) {
                          const start = Math.min(lastIdx, curIdx);
                          const end = Math.max(lastIdx, curIdx);
                          newSelected = new Set();
                          for (let i = start; i <= end; i++) {
                            newSelected.add(sortedResults[i].id);
                          }
                          setSelected(compound.id);
                        } else {
                          newSelected.add(compound.id);
                          setSelected(compound.id);
                          setLastSelectedId(compound.id);
                        }
                      } else {
                        newSelected.add(compound.id);
                        setSelected(compound.id);
                        setLastSelectedId(compound.id);
                      }
                      setSelectedIds(newSelected);
                    }}
                    onContextMenu={(e) => {
                      e.preventDefault();
                      let newSelected = new Set(selectedIds);
                      if (!newSelected.has(compound.id)) {
                        newSelected = new Set([compound.id]);
                        setSelected(compound.id);
                        setLastSelectedId(compound.id);
                      }
                      setSelectedIds(newSelected);
                      setContextMenu({
                        ids: Array.from(newSelected),
                        name: newSelected.size === 1 ? compound.name : `${newSelected.size} compounds`,
                        x: e.clientX,
                        y: e.clientY,
                      });
                    }}
                    style={{
                      cursor: 'pointer',
                      borderLeft: isOOD ? '3px solid var(--color-red-500, #f43f5e)' : undefined
                    }}
                  >
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <div className="compound-name">{compound.name}</div>
                        {selectedWorkflowType === 'bioisostere_opt' && (
                          compound.name.includes('Analogue') ? (
                            <span style={{
                              padding: '1px 6px',
                              borderRadius: '4px',
                              background: 'rgba(37, 99, 235, 0.08)',
                              border: '0.5px solid rgba(37, 99, 235, 0.25)',
                              color: '#2563eb',
                              fontSize: '9px',
                              fontWeight: 600,
                              letterSpacing: '0.02em',
                              textTransform: 'uppercase',
                            }}>
                              Analogue
                            </span>
                          ) : (
                            <span style={{
                              padding: '1px 6px',
                              borderRadius: '4px',
                              background: 'rgba(16, 185, 129, 0.08)',
                              border: '0.5px solid rgba(16, 185, 129, 0.25)',
                              color: '#10b981',
                              fontSize: '9px',
                              fontWeight: 600,
                              letterSpacing: '0.02em',
                              textTransform: 'uppercase',
                            }}>
                              Lead
                            </span>
                          )
                        )}
                      </div>
                    </td>
                    <td>
                      <span className="compound-smiles selectable">
                        {compound.smiles}
                      </span>
                    </td>
                    <td className="center">
                      {compound.pesticide_likeness_disabled ? (
                        <span style={{ color: 'var(--color-text-400)', fontSize: '10px' }}>Excluded</span>
                      ) : (
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}>
                          <RiskBadge
                            level={toRisk(compound.pesticide_likeness)}
                            context="good"
                          />
                          {compound.uq?.pesticide_likeness && (
                            <UqBadge
                              status={compound.uq.pesticide_likeness.ad_status}
                              score={compound.uq.pesticide_likeness.ad_score}
                              coverage={compound.uq.pesticide_likeness.coverage}
                              modelId={compound.uq.pesticide_likeness.model_id}
                            />
                          )}
                        </div>
                      )}
                    </td>
                    <td className="center">
                      {compound.toxicity?.disabled ? (
                        <span style={{ color: 'var(--color-text-400)', fontSize: '10px' }}>Excluded</span>
                      ) : (
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}>
                          <RiskBadge
                            level={toRisk(compound.toxicity?.overall_level)}
                          />
                          {compound.uq?.toxicity && (
                            <UqBadge
                              status={compound.uq.toxicity.ad_status}
                              score={compound.uq.toxicity.ad_score}
                              coverage={compound.uq.toxicity.coverage}
                              modelId={compound.uq.toxicity.model_id}
                            />
                          )}
                        </div>
                      )}
                    </td>
                    <td className="center">
                      {compound.selectivity?.disabled ? (
                        <span style={{ color: 'var(--color-text-400)', fontSize: '10px' }}>Excluded</span>
                      ) : (
                        compound.uq?.selectivity && (compound.uq.selectivity.lower !== null || (compound.uq.selectivity as any).ci_lower !== null) ? (
                          <div style={{ display: 'flex', justifyContent: 'center' }}>
                            <IntervalBar
                              value={compound.selectivity?.min_selectivity ?? 0}
                              lower={compound.uq.selectivity.lower !== null ? compound.uq.selectivity.lower : (compound.uq.selectivity as any).ci_lower}
                              upper={compound.uq.selectivity.upper !== null ? compound.uq.selectivity.upper : (compound.uq.selectivity as any).ci_upper}
                              minVal={0}
                              maxVal={100}
                              units="×"
                            />
                          </div>
                        ) : (
                          <span
                            className="selectivity-value"
                            style={{
                              color: compound.selectivity?.overall_level === 'safe'
                                ? 'var(--color-brand-700)'
                                : compound.selectivity?.overall_level === 'moderate'
                                  ? 'var(--color-amber-700)'
                                  : 'var(--color-red-700)',
                              fontWeight: isSelected ? 500 : 400,
                            }}
                          >
                            {compound.selectivity
                              ? `${compound.selectivity.min_selectivity}×`
                              : '—'
                            }
                          </span>
                        )
                      )}
                    </td>
                    <td className="center">
                      {compound.resistance?.disabled ? (
                        <span style={{ color: 'var(--color-text-400)', fontSize: '10px' }}>Excluded</span>
                      ) : (
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}>
                          <RiskBadge
                            level={toRisk(compound.resistance?.level)}
                          />
                          {compound.uq?.resistance && (
                            <UqBadge
                              status={compound.uq.resistance.ad_status}
                              score={compound.uq.resistance.ad_score}
                              coverage={compound.uq.resistance.coverage}
                              modelId={compound.uq.resistance.model_id}
                            />
                          )}
                        </div>
                      )}
                    </td>
                    <td className="center">
                      {fate ? (
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '2px' }}>
                          <span className={`rank-badge rank-${fate.pbt.verdict === 'Not PBT/vPvB' || fate.pbt.verdict === 'Low Risk' ? 'candidate' : 'deprioritize'}`} style={{ fontSize: '9px', padding: '1px 4px' }}>
                            {fate.pbt.verdict}
                          </span>
                          <span style={{ 
                            fontSize: '9px', 
                            color: fate.gus.class === 'leacher' ? 'var(--color-red-600)' : fate.gus.class === 'transition' ? 'var(--color-amber-600)' : 'var(--color-brand-600)',
                            fontWeight: 500
                          }}>
                            GUS: {fate.gus.value.kind === 'numeric' && fate.gus.value.numeric != null ? fate.gus.value.numeric.toFixed(1) : '—'} ({fate.gus.class})
                          </span>
                        </div>
                      ) : (
                        <span style={{ color: 'var(--color-text-400)', fontSize: '10px' }}>—</span>
                      )}
                    </td>
                    <td className="center">
                      <span
                        className={`rank-badge rank-${compound.mpo?.rank_category?.toLowerCase() ?? 'deprioritize'}`}
                      >
                        {compound.mpo?.rank_category ?? '—'}
                      </span>
                    </td>
                    <td className="center">
                      {compound.uq?.score && (compound.uq.score.lower !== null || (compound.uq.score as any).ci_lower !== null) ? (
                        <div style={{ display: 'flex', justifyContent: 'center' }}>
                          <IntervalBar
                            value={compound.score ?? 0}
                            lower={compound.uq.score.lower !== null ? compound.uq.score.lower : (compound.uq.score as any).ci_lower}
                            upper={compound.uq.score.upper !== null ? compound.uq.score.upper : (compound.uq.score as any).ci_upper}
                            minVal={0}
                            maxVal={10}
                          />
                        </div>
                      ) : (
                        <span
                          className="score-value"
                          style={{
                            color: isSelected
                              ? 'var(--color-brand-900)'
                              : 'var(--color-text-600)',
                            fontWeight: 600,
                          }}
                        >
                          {compound.score != null ? compound.score.toFixed(1) : '—'}
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Footer */}
        <div className="results-footer">
          <span>
            Showing {filteredResults.length} compounds · sorted by {sortCol === 'score' ? 'MPO composite score' : sortCol}
          </span>
        </div>
      </div>

      {/* Context Menu */}
      {contextMenu && activeProjectId && (
        <div
          className="context-menu"
          style={{ top: contextMenu.y, left: contextMenu.x, zIndex: 1000 }}
        >
          <div
            className="context-menu-item"
            onClick={(e) => {
              e.stopPropagation();
              const targetId = contextMenu.ids[0];
              const targetComp = compounds.find(c => c.id === targetId);
              if (targetComp) {
                useUIStore.getState().exportToDeNovo(targetComp.smiles, targetComp.id);
              }
              setContextMenu(null);
            }}
          >
            🧪 Export to De Novo Design
          </div>
          <div
            className="context-menu-item danger"
            onClick={async (e) => {
              e.stopPropagation();
              const count = contextMenu.ids.length;
              if (confirm(`Are you sure you want to delete ${contextMenu.name}?`)) {
                try {
                  await deleteCompounds(activeProjectId, contextMenu.ids);
                  setSelectedIds(new Set());
                  setLastSelectedId(null);
                  setSelected(null);
                  setToast({ message: `Deleted ${count} compound${count !== 1 ? 's' : ''}`, type: 'success' });
                  fetchProjects();
                  if (activeWorkflow) {
                    await fetchResults(activeWorkflow.id);
                  }
                } catch (err) {
                  console.error('Failed to delete:', err);
                  setToast({ message: 'Failed to delete compound(s)', type: 'error' });
                }
              }
              setContextMenu(null);
            }}
          >
            🗑 Delete {contextMenu.ids.length > 1 ? `${contextMenu.ids.length} Compounds` : 'Compound'}
          </div>
        </div>
      )}

      {/* Toast notification */}
      {toast && (
        <div className={`toast toast-${toast.type}`}>
          {toast.message}
        </div>
      )}
    </div>
  );
}
