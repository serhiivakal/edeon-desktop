import { useEffect, useState, useCallback } from 'react';
import { useProjectStore } from '../store/projectStore';
import { useCompoundStore } from '../store/compoundStore';
import { useUIStore } from '../store/uiStore';
import { ImportDialog } from '../components/library/ImportDialog';
import { AddCompoundDialog } from '../components/library/AddCompoundDialog';

export function LibraryView() {
  const activeProjectId = useProjectStore((s) => s.activeProjectId);
  const projects = useProjectStore((s) => s.projects);
  const fetchProjects = useProjectStore((s) => s.fetchProjects);
  const activeProject = projects.find((p) => p.id === activeProjectId);

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
  const setSelectedCompound = useUIStore((s) => s.setSelectedCompound);

  const [showImport, setShowImport] = useState(false);
  const [showAddCompound, setShowAddCompound] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // Fetch compounds when project changes
  useEffect(() => {
    if (activeProjectId) {
      reset();
      fetchCompounds(activeProjectId);
    }
  }, [activeProjectId, reset, fetchCompounds]);

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

  const handleImportComplete = (count: number) => {
    setShowImport(false);
    setToast({ message: `Imported ${count} compound${count !== 1 ? 's' : ''}`, type: 'success' });
    fetchProjects(); // Refresh project compound counts
  };

  const handleAddComplete = () => {
    setShowAddCompound(false);
    setToast({ message: 'Compound added', type: 'success' });
    fetchProjects();
  };

  const sortIndicator = (column: string) => {
    if (sortBy !== column) return '';
    return sortDir === 'asc' ? ' ▴' : ' ▾';
  };

  if (!activeProjectId) {
    return (
      <div className="main-content">
        <div className="library-empty-state">
          <div className="library-empty-icon">📂</div>
          <h2>No project selected</h2>
          <p>Create or select a project from the sidebar to get started.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="main-content">
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
          <button className="library-btn" onClick={() => setShowAddCompound(true)}>
            + Add
          </button>
          <button className="library-btn-primary" onClick={() => setShowImport(true)}>
            ↑ Import CSV
          </button>
        </div>
      </div>

      {/* Table or empty state */}
      {total === 0 && !loading ? (
        <div className="library-empty-state">
          <div className="library-empty-icon">🧪</div>
          <h2>No compounds yet</h2>
          <p>Import a CSV file or add compounds manually to get started.</p>
          <div className="library-empty-actions">
            <button className="library-btn-primary" onClick={() => setShowImport(true)}>
              ↑ Import CSV
            </button>
            <button className="library-btn" onClick={() => setShowAddCompound(true)}>
              + Add compound
            </button>
          </div>
        </div>
      ) : (
        <div className="results-table-wrap" style={{ flex: 1 }}>
          <table className="results-table library-table">
            <thead>
              <tr>
                <th
                  className="sortable"
                  style={{ width: '22%' }}
                  onClick={() => handleSort('name')}
                >
                  NAME{sortIndicator('name')}
                </th>
                <th
                  className="sortable"
                  style={{ width: '34%' }}
                  onClick={() => handleSort('smiles')}
                >
                  SMILES{sortIndicator('smiles')}
                </th>
                <th
                  className="center sortable"
                  style={{ width: '11%' }}
                  onClick={() => handleSort('mol_weight')}
                >
                  MW{sortIndicator('mol_weight')}
                </th>
                <th
                  className="center sortable"
                  style={{ width: '11%' }}
                  onClick={() => handleSort('logp')}
                >
                  LogP{sortIndicator('logp')}
                </th>
                <th
                  className="center sortable"
                  style={{ width: '11%' }}
                  onClick={() => handleSort('tpsa')}
                >
                  TPSA{sortIndicator('tpsa')}
                </th>
                <th
                  className="center sortable"
                  style={{ width: '11%' }}
                  onClick={() => handleSort('hbd')}
                >
                  HBD{sortIndicator('hbd')}
                </th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6} className="center" style={{ padding: '40px', color: 'var(--color-text-400)' }}>
                    Loading...
                  </td>
                </tr>
              ) : (
                compounds.map((compound) => (
                  <tr
                    key={compound.id}
                    className={selectedIds.has(compound.id) ? 'selected' : ''}
                    onClick={() => {
                      setSelectedCompound(compound.id);
                      setSelectedIds(new Set([compound.id]));
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
                  </tr>
                ))
              )}
            </tbody>
          </table>

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
      {showImport && (
        <ImportDialog
          projectId={activeProjectId}
          onComplete={handleImportComplete}
          onClose={() => setShowImport(false)}
        />
      )}
      {showAddCompound && (
        <AddCompoundDialog
          projectId={activeProjectId}
          onComplete={handleAddComplete}
          onClose={() => setShowAddCompound(false)}
        />
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
