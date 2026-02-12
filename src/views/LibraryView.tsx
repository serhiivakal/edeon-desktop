import { useEffect, useState, useCallback } from 'react';
import { useProjectStore } from '../store/projectStore';
import { useCompoundStore } from '../store/compoundStore';
import { useUIStore } from '../store/uiStore';
import { open } from '@tauri-apps/plugin-dialog';
import { useResizableColumns } from '../hooks/useResizableColumns';
import { AddCompoundDialog } from '../components/library/AddCompoundDialog';
import { invoke } from '@tauri-apps/api/core';
import { EmptyState } from '../components/shared/EmptyState';
import { FolderOpen, Beaker } from 'lucide-react';

export function LibraryView() {
  const activeProjectId = useProjectStore((s) => s.activeProjectId);
  const projects = useProjectStore((s) => s.projects);
  const fetchProjects = useProjectStore((s) => s.fetchProjects);
  const activeProject = projects.find((p) => p.id === activeProjectId);

  const { widths, tableRef, handleMouseDown } = useResizableColumns([20, 30, 10, 10, 10, 10, 10]);

  const compounds = useCompoundStore((s) => s.compounds);
  const total = useCompoundStore((s) => s.total);
  const page = useCompoundStore((s) => s.page);
  const pageSize = useCompoundStore((s) => s.pageSize);
  const sortBy = useCompoundStore((s) => s.sortBy);
  const sortDir = useCompoundStore((s) => s.sortDir);
  const searchQuery = useCompoundStore((s) => s.searchQuery);
  const loading = useCompoundStore((s) => s.loading);
  const fetchCompounds = useCompoundStore((s) => s.fetchCompounds);
  const setPage = useCompoundStore((s) => s.setPage);
  const setSort = useCompoundStore((s) => s.setSort);
  const setSearch = useCompoundStore((s) => s.setSearch);
  const reset = useCompoundStore((s) => s.reset);
  const deleteCompounds = useCompoundStore((s) => s.deleteCompounds);
  const setSelectedCompound = useUIStore((s) => s.setSelectedCompound);
  const mcsActive = useUIStore((s) => s.mcsActive);
  const mcsLoading = useUIStore((s) => s.mcsLoading);
  const computeMcs = useUIStore((s) => s.computeMcs);
  const clearMcs = useUIStore((s) => s.clearMcs);

  const [showAddCompound, setShowAddCompound] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [lastSelectedId, setLastSelectedId] = useState<string | null>(null);
  const filters = useCompoundStore((s) => s.filters);
  const setFilters = useCompoundStore((s) => s.setFilters);
  const [showFilters, setShowFilters] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  const [contextMenu, setContextMenu] = useState<{
    ids: string[];
    name: string;
    x: number;
    y: number;
  } | null>(null);

  // Fetch compounds when project changes
  const handleLoadDemoImidacloprid = async () => {
    let targetProjectId = activeProjectId;
    if (!targetProjectId) {
      if (projects.length > 0) {
        targetProjectId = projects[0].id;
        await useProjectStore.getState().setActiveProject(targetProjectId);
      } else {
        const proj = await useProjectStore.getState().createProject('Demo Project');
        targetProjectId = proj.id;
      }
    }
    
    if (targetProjectId) {
      setToast({ message: 'Loading demo compound Imidacloprid...', type: 'success' });
      try {
        const addCompound = useCompoundStore.getState().addCompound;
        await addCompound(targetProjectId, 'Imidacloprid', 'C1=C(Cl)C=NC(=C1)CN2C(=N[N+](=O)[O-])NCC2');
        setToast({ message: 'Demo compound Imidacloprid loaded successfully!', type: 'success' });
        fetchProjects();
        fetchCompounds(targetProjectId);
      } catch (err) {
        console.error('Failed to load demo compound:', err);
        setToast({ message: `Failed to load demo: ${String(err)}`, type: 'error' });
      }
    }
  };

  useEffect(() => {
    if (activeProjectId) {
      reset();
      fetchCompounds(activeProjectId);
    }
  }, [activeProjectId, reset, fetchCompounds]);

  // Close context menu on click outside
  useEffect(() => {
    if (!contextMenu) return;
    const handler = () => setContextMenu(null);
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, [contextMenu]);

  // Auto-dismiss toast
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(t);
  }, [toast]);

  const totalPages = Math.ceil(total / pageSize);

  const handleSort = useCallback(
    (column: string) => {
      if (activeProjectId) setSort(column, activeProjectId);
    },
    [activeProjectId, setSort],
  );

  const handlePageChange = useCallback(
    (newPage: number) => {
      if (activeProjectId && newPage >= 1 && newPage <= totalPages) {
        setPage(newPage, activeProjectId);
      }
    },
    [activeProjectId, totalPages, setPage],
  );

  const handleSearch = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (activeProjectId) setSearch(e.target.value, activeProjectId);
    },
    [activeProjectId, setSearch],
  );

  const handleAddComplete = () => {
    setShowAddCompound(false);
    setToast({ message: 'Compound added', type: 'success' });
    fetchProjects();
  };

  const handleExportCSV = async () => {
    if (!activeProjectId) return;
    setToast({ message: 'Generating library CSV...', type: 'success' });
    try {
      const csvString = await invoke<string>('export_library_csv', {
        projectId: activeProjectId
      });
      const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.setAttribute('href', url);
      link.setAttribute('download', `edeon_library_${activeProject?.name.toLowerCase().replace(/[^a-z0-9]+/g, '_') || 'export'}.csv`);
      link.style.visibility = 'hidden';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      setToast({ message: 'Library CSV exported successfully!', type: 'success' });
    } catch (e) {
      console.error('Failed to export library CSV:', e);
      setToast({ message: `Export failed: ${String(e)}`, type: 'error' });
    }
  };

  const importCSV = useCompoundStore((s) => s.importCSV);
  const importSDF = useCompoundStore((s) => s.importSDF);

  const handleImportCSV = async () => {
    if (!activeProjectId) return;
    try {
      const selected = await open({
        multiple: false,
        filters: [{ name: 'CSV Files', extensions: ['csv', 'tsv', 'txt'] }],
      });
      if (selected) {
        setToast({ message: 'Importing CSV compounds...', type: 'success' });
        const count = await importCSV(activeProjectId, selected as string);
        setToast({ message: `Imported ${count} compound${count !== 1 ? 's' : ''} successfully!`, type: 'success' });
        fetchProjects(); // Refresh project compound counts
      }
    } catch (e) {
      console.error('CSV Import error:', e);
      setToast({ message: `Import failed: ${String(e)}`, type: 'error' });
    }
  };

  const handleImportSDF = async () => {
    if (!activeProjectId) return;
    try {
      const selected = await open({
        multiple: false,
        filters: [{ name: 'SDF Files', extensions: ['sdf'] }],
      });
      if (selected) {
        setToast({ message: 'Importing SDF compounds via RDKit...', type: 'success' });
        const count = await importSDF(activeProjectId, selected as string);
        setToast({ message: `Imported ${count} compound${count !== 1 ? 's' : ''} successfully!`, type: 'success' });
        fetchProjects(); // Refresh project compound counts
      }
    } catch (e) {
      console.error('SDF Import error:', e);
      setToast({ message: `Import failed: ${String(e)}`, type: 'error' });
    }
  };

  const sortIndicator = (column: string) => {
    if (sortBy !== column) return '';
    return sortDir === 'asc' ? ' ▴' : ' ▾';
  };

  if (!activeProjectId) {
    return (
      <div className="main-content" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
        <EmptyState
          icon={<FolderOpen size={20} />}
          title="No project selected"
          description="Create or select a project from the sidebar to get started, or initialize with a demo compound."
          primaryAction={{
            label: "Load Demo Imidacloprid",
            onClick: handleLoadDemoImidacloprid,
          }}
        />
      </div>
    );
  }

  return (
    <div className="main-content" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', boxSizing: 'border-box', padding: '16px' }}>
      {/* Toolbar */}
      <div className="library-toolbar">
        <div className="library-toolbar-left">
          <span className="library-title">
            {activeProject?.name ?? 'Library'} · {total} compound{total !== 1 ? 's' : ''}
          </span>
        </div>
        <div className="library-toolbar-right">
          <input
            className="library-search"
            type="text"
            placeholder="Search by name or SMILES..."
            value={searchQuery}
            onChange={handleSearch}
          />
          <button
            className={`library-btn ${Object.keys(filters).length > 0 ? 'active' : ''}`}
            onClick={() => setShowFilters(!showFilters)}
            title="Filter compounds by property ranges"
          >
            ⌕ Filter
          </button>
          {Object.keys(filters).length > 0 && (
            <button
              className="library-btn"
              style={{ color: 'var(--color-red-600)', borderColor: 'var(--color-red-200)' }}
              onClick={() => setFilters({}, activeProjectId)}
              title="Discard all active range filters"
            >
              ✕ Clear Filters
            </button>
          )}
          <button
            className={`library-btn ${mcsActive ? 'active' : ''}`}
            onClick={() => {
              if (mcsActive) {
                clearMcs();
              } else {
                const smiles = compounds.map((c) => c.smiles).filter(Boolean);
                computeMcs(smiles);
              }
            }}
            disabled={mcsLoading || compounds.length < 2}
            title="Find Maximum Common Substructure"
          >
            {mcsLoading ? '⏳' : mcsActive ? '✕ MCS' : '🔗 MCS'}
          </button>
          {selectedIds.size > 0 && (
            <button
              className="library-btn"
              style={{ color: 'var(--color-red-700)', borderColor: 'var(--color-red-400)' }}
              onClick={async () => {
                const list = Array.from(selectedIds);
                const count = list.length;
                if (confirm(`Are you sure you want to delete the ${count} selected compound${count !== 1 ? 's' : ''}?`)) {
                  try {
                    await deleteCompounds(activeProjectId, list);
                    setSelectedIds(new Set());
                    setLastSelectedId(null);
                    setSelectedCompound(null);
                    setToast({ message: `Deleted ${count} compound${count !== 1 ? 's' : ''} successfully`, type: 'success' });
                    fetchProjects();
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
          <button className="library-btn" onClick={() => setShowAddCompound(true)}>
            + Add
          </button>
          <button className="library-btn" onClick={handleExportCSV}>
            ↓ Export CSV
          </button>
          <button className="library-btn" onClick={handleImportCSV}>
            ↑ Import CSV
          </button>
          <button className="library-btn-primary" onClick={handleImportSDF}>
            ↑ Import SDF
          </button>
        </div>
      </div>

      {/* Property Range Filters Collapsible Panel */}
      {showFilters && (
        <div className="filter-panel" style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: '16px',
          padding: '16px',
          background: 'var(--color-surface)',
          border: '0.5px solid var(--color-border)',
          borderRadius: '8px',
          marginBottom: '16px',
          boxShadow: 'var(--shadow-sm)'
        }}>
          {/* MW Filter */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontSize: '10px', fontWeight: 600, color: 'var(--color-text-500)', textTransform: 'uppercase' }}>Mol Weight (MW)</span>
            <div style={{ display: 'flex', gap: '8px' }}>
              <input
                type="number"
                placeholder="Min"
                style={{ flex: 1, padding: '4px 8px', borderRadius: '4px', border: '0.5px solid var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text-900)', height: '24px' }}
                value={filters.mw_min ?? ''}
                onChange={(e) => {
                  const val = e.target.value ? parseFloat(e.target.value) : null;
                  setFilters({ ...filters, mw_min: val }, activeProjectId);
                }}
              />
              <input
                type="number"
                placeholder="Max"
                style={{ flex: 1, padding: '4px 8px', borderRadius: '4px', border: '0.5px solid var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text-900)', height: '24px' }}
                value={filters.mw_max ?? ''}
                onChange={(e) => {
                  const val = e.target.value ? parseFloat(e.target.value) : null;
                  setFilters({ ...filters, mw_max: val }, activeProjectId);
                }}
              />
            </div>
          </div>

          {/* LogP Filter */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontSize: '10px', fontWeight: 600, color: 'var(--color-text-500)', textTransform: 'uppercase' }}>LogP</span>
            <div style={{ display: 'flex', gap: '8px' }}>
              <input
                type="number"
                step="0.1"
                placeholder="Min"
                style={{ flex: 1, padding: '4px 8px', borderRadius: '4px', border: '0.5px solid var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text-900)', height: '24px' }}
                value={filters.logp_min ?? ''}
                onChange={(e) => {
                  const val = e.target.value ? parseFloat(e.target.value) : null;
                  setFilters({ ...filters, logp_min: val }, activeProjectId);
                }}
              />
              <input
                type="number"
                step="0.1"
                placeholder="Max"
                style={{ flex: 1, padding: '4px 8px', borderRadius: '4px', border: '0.5px solid var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text-900)', height: '24px' }}
                value={filters.logp_max ?? ''}
                onChange={(e) => {
                  const val = e.target.value ? parseFloat(e.target.value) : null;
                  setFilters({ ...filters, logp_max: val }, activeProjectId);
                }}
              />
            </div>
          </div>

          {/* TPSA Filter */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontSize: '10px', fontWeight: 600, color: 'var(--color-text-500)', textTransform: 'uppercase' }}>TPSA</span>
            <div style={{ display: 'flex', gap: '8px' }}>
              <input
                type="number"
                placeholder="Min"
                style={{ flex: 1, padding: '4px 8px', borderRadius: '4px', border: '0.5px solid var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text-900)', height: '24px' }}
                value={filters.tpsa_min ?? ''}
                onChange={(e) => {
                  const val = e.target.value ? parseFloat(e.target.value) : null;
                  setFilters({ ...filters, tpsa_min: val }, activeProjectId);
                }}
              />
              <input
                type="number"
                placeholder="Max"
                style={{ flex: 1, padding: '4px 8px', borderRadius: '4px', border: '0.5px solid var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text-900)', height: '24px' }}
                value={filters.tpsa_max ?? ''}
                onChange={(e) => {
                  const val = e.target.value ? parseFloat(e.target.value) : null;
                  setFilters({ ...filters, tpsa_max: val }, activeProjectId);
                }}
              />
            </div>
          </div>

          {/* HBD Filter */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontSize: '10px', fontWeight: 600, color: 'var(--color-text-500)', textTransform: 'uppercase' }}>HBD</span>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <input
                type="number"
                placeholder="Min"
                style={{ flex: 1, padding: '4px 8px', borderRadius: '4px', border: '0.5px solid var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text-900)', height: '24px' }}
                value={filters.hbd_min ?? ''}
                onChange={(e) => {
                  const val = e.target.value ? parseInt(e.target.value, 10) : null;
                  setFilters({ ...filters, hbd_min: isNaN(val as number) ? null : val }, activeProjectId);
                }}
              />
              <input
                type="number"
                placeholder="Max"
                style={{ flex: 1, padding: '4px 8px', borderRadius: '4px', border: '0.5px solid var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text-900)', height: '24px' }}
                value={filters.hbd_max ?? ''}
                onChange={(e) => {
                  const val = e.target.value ? parseInt(e.target.value, 10) : null;
                  setFilters({ ...filters, hbd_max: isNaN(val as number) ? null : val }, activeProjectId);
                }}
              />
              {Object.keys(filters).length > 0 && (
                <button
                  onClick={() => setFilters({}, activeProjectId)}
                  style={{
                    padding: '4px 8px',
                    borderRadius: '4px',
                    background: 'var(--color-bg)',
                    border: '0.5px solid var(--color-red-200)',
                    color: 'var(--color-red-600)',
                    fontWeight: 500,
                    cursor: 'pointer',
                    fontSize: '11px',
                    height: '24px',
                    whiteSpace: 'nowrap'
                  }}
                >
                  Clear All
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Table or empty state */}
      {total === 0 && !loading ? (
        <div style={{ display: 'flex', flex: 1, alignItems: 'center', justifyContent: 'center', height: '100%' }}>
          <EmptyState
            icon={<Beaker size={20} />}
            title="No compounds yet"
            description="Import a CSV/SDF file or add compounds manually to get started, or load our standard reference."
            primaryAction={{
              label: "Load Demo Imidacloprid",
              onClick: handleLoadDemoImidacloprid,
            }}
            secondaryAction={{
              label: "Import CSV",
              onClick: handleImportCSV,
            }}
          />
        </div>
      ) : (
        <div className="results-table-wrap" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ flex: 1, overflowY: 'auto' }}>
            <table ref={tableRef} className="results-table library-table">
              <thead>
              <tr>
                <th
                  className="sortable"
                  style={{ width: `${widths[0]}%`, position: 'relative' }}
                  onClick={() => handleSort('name')}
                >
                  NAME{sortIndicator('name')}
                  <div className="col-resize-handle" onMouseDown={(e) => handleMouseDown(0, e)} onClick={(e) => e.stopPropagation()} />
                </th>
                <th
                  className="sortable"
                  style={{ width: `${widths[1]}%`, position: 'relative' }}
                  onClick={() => handleSort('smiles')}
                >
                  SMILES{sortIndicator('smiles')}
                  <div className="col-resize-handle" onMouseDown={(e) => handleMouseDown(1, e)} onClick={(e) => e.stopPropagation()} />
                </th>
                <th
                  className="center sortable"
                  style={{ width: `${widths[2]}%`, position: 'relative' }}
                  onClick={() => handleSort('mol_weight')}
                >
                  MW{sortIndicator('mol_weight')}
                  <div className="col-resize-handle" onMouseDown={(e) => handleMouseDown(2, e)} onClick={(e) => e.stopPropagation()} />
                </th>
                <th
                  className="center sortable"
                  style={{ width: `${widths[3]}%`, position: 'relative' }}
                  onClick={() => handleSort('logp')}
                >
                  LogP{sortIndicator('logp')}
                  <div className="col-resize-handle" onMouseDown={(e) => handleMouseDown(3, e)} onClick={(e) => e.stopPropagation()} />
                </th>
                <th
                  className="center sortable"
                  style={{ width: `${widths[4]}%`, position: 'relative' }}
                  onClick={() => handleSort('tpsa')}
                >
                  TPSA{sortIndicator('tpsa')}
                  <div className="col-resize-handle" onMouseDown={(e) => handleMouseDown(4, e)} onClick={(e) => e.stopPropagation()} />
                </th>
                <th
                  className="center sortable"
                  style={{ width: `${widths[5]}%`, position: 'relative' }}
                  onClick={() => handleSort('hbd')}
                >
                  HBD{sortIndicator('hbd')}
                  <div className="col-resize-handle" onMouseDown={(e) => handleMouseDown(5, e)} onClick={(e) => e.stopPropagation()} />
                </th>
                <th
                  className="center"
                  style={{ width: `${widths[6]}%`, position: 'relative' }}
                >
                  ACTIONS
                  <div className="col-resize-handle" onMouseDown={(e) => handleMouseDown(6, e)} onClick={(e) => e.stopPropagation()} />
                </th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} className="center" style={{ padding: '40px', color: 'var(--color-text-400)' }}>
                    Loading...
                  </td>
                </tr>
              ) : (
                compounds.map((compound) => (
                  <tr
                      key={compound.id}
                      className={selectedIds.has(compound.id) ? 'selected' : ''}
                      onClick={(e) => {
                        let newSelected = new Set<string>();
                        if (e.ctrlKey || e.metaKey) {
                          newSelected = new Set(selectedIds);
                          if (newSelected.has(compound.id)) {
                            newSelected.delete(compound.id);
                          } else {
                            newSelected.add(compound.id);
                            setSelectedCompound(compound.id);
                            setLastSelectedId(compound.id);
                          }
                        } else if (e.shiftKey && lastSelectedId) {
                          const lastIdx = compounds.findIndex(c => c.id === lastSelectedId);
                          const curIdx = compounds.findIndex(c => c.id === compound.id);
                          if (lastIdx !== -1 && curIdx !== -1) {
                            const start = Math.min(lastIdx, curIdx);
                            const end = Math.max(lastIdx, curIdx);
                            newSelected = new Set();
                            for (let i = start; i <= end; i++) {
                              newSelected.add(compounds[i].id);
                            }
                            setSelectedCompound(compound.id);
                          } else {
                            newSelected.add(compound.id);
                            setSelectedCompound(compound.id);
                            setLastSelectedId(compound.id);
                          }
                        } else {
                          newSelected.add(compound.id);
                          setSelectedCompound(compound.id);
                          setLastSelectedId(compound.id);
                        }
                        setSelectedIds(newSelected);
                      }}
                      onContextMenu={(e) => {
                        e.preventDefault();
                        let newSelected = new Set(selectedIds);
                        if (!newSelected.has(compound.id)) {
                          newSelected = new Set([compound.id]);
                          setSelectedCompound(compound.id);
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
                      <td className="center">
                        <span className="library-prop-value">
                          {compound.mol_weight != null ? compound.mol_weight.toFixed(1) : '—'}
                        </span>
                      </td>
                      <td className="center">
                        <span className="library-prop-value">
                          {compound.logp != null ? compound.logp.toFixed(2) : '—'}
                        </span>
                      </td>
                      <td className="center">
                        <span className="library-prop-value">
                          {compound.tpsa != null ? compound.tpsa.toFixed(1) : '—'}
                        </span>
                      </td>
                      <td className="center">
                        <span className="library-prop-value">
                          {compound.hbd != null ? compound.hbd : '—'}
                        </span>
                      </td>
                      <td className="center" onClick={(e) => e.stopPropagation()}>
                        <button
                          className="library-btn"
                          style={{
                            padding: '2px 6px',
                            color: 'var(--color-red-700)',
                            borderColor: 'var(--color-red-200)',
                            background: 'transparent',
                            fontSize: '10px',
                            fontWeight: 500,
                            height: '20px'
                          }}
                          onClick={async () => {
                            if (confirm(`Are you sure you want to delete compound "${compound.name}"?`)) {
                              try {
                                await deleteCompounds(activeProjectId, [compound.id]);
                                setSelectedIds(new Set());
                                setLastSelectedId(null);
                                setSelectedCompound(null);
                                setToast({ message: 'Compound deleted', type: 'success' });
                                fetchProjects();
                              } catch (e) {
                                console.error('Failed to delete:', e);
                                setToast({ message: 'Failed to delete compound', type: 'error' });
                              }
                            }
                          }}
                        >
                          🗑 Delete
                        </button>
                      </td>
                    </tr>
                ))
              )}
            </tbody>
          </table>
          </div>

          {/* Pagination footer */}
          <div className="results-footer">
            <span>
              Showing {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} of {total}
              {searchQuery ? ` (filtered)` : ''} · sorted by {sortBy}
            </span>
            {totalPages > 1 && (
              <div className="results-pagination">
                <span
                  onClick={() => handlePageChange(page - 1)}
                  style={{ opacity: page <= 1 ? 0.3 : 1, cursor: page <= 1 ? 'default' : 'pointer' }}
                >
                  ‹
                </span>
                {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
                  let pageNum: number;
                  if (totalPages <= 7) {
                    pageNum = i + 1;
                  } else if (page <= 4) {
                    pageNum = i + 1;
                  } else if (page >= totalPages - 3) {
                    pageNum = totalPages - 6 + i;
                  } else {
                    pageNum = page - 3 + i;
                  }
                  return (
                    <span
                      key={pageNum}
                      onClick={() => handlePageChange(pageNum)}
                      style={{ fontWeight: page === pageNum ? 700 : 400, cursor: 'pointer' }}
                    >
                      {pageNum}
                    </span>
                  );
                })}
                <span
                  onClick={() => handlePageChange(page + 1)}
                  style={{
                    opacity: page >= totalPages ? 0.3 : 1,
                    cursor: page >= totalPages ? 'default' : 'pointer',
                  }}
                >
                  ›
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Dialogs */}
      {showAddCompound && (
        <AddCompoundDialog
          projectId={activeProjectId}
          onComplete={handleAddComplete}
          onClose={() => setShowAddCompound(false)}
        />
      )}

      {/* Context Menu */}
      {contextMenu && (
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
                  setSelectedCompound(null);
                  setToast({ message: `Deleted ${count} compound${count !== 1 ? 's' : ''}`, type: 'success' });
                  fetchProjects();
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
