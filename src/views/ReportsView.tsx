import { useEffect, useState, useCallback } from 'react';
import { useProjectStore } from '../store/projectStore';
import { useWorkflowStore } from '../store/workflowStore';
import { invoke } from '@tauri-apps/api/core';
import { save } from '@tauri-apps/plugin-dialog';
import { useResizableColumns } from '../hooks/useResizableColumns';
import type { WorkflowRecord } from '../types';
import { EmptyState } from '../components/shared/EmptyState';
import { CitationExportButton } from '../components/shared/CitationExportButton';
import { useUIStore } from '../store/uiStore';
import { FolderOpen, FileText } from 'lucide-react';

export function ReportsView() {
  const activeProjectId = useProjectStore((s) => s.activeProjectId);
  const { widths, tableRef, handleMouseDown } = useResizableColumns([30, 20, 20, 15, 15]);
  const projects = useProjectStore((s) => s.projects);
  const activeProject = projects.find((p) => p.id === activeProjectId);

  const exportPdf = useWorkflowStore((s) => s.exportPdf);

  const [workflows, setWorkflows] = useState<WorkflowRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string>('');
  const [exportingId, setExportingId] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const fetchWorkflows = useCallback(async () => {
    if (!activeProjectId) return;
    setLoading(true);
    try {
      const list = await invoke<WorkflowRecord[]>('list_workflows', { projectId: activeProjectId });
      setWorkflows(list);
      
      // Auto-select the first completed workflow if available, or just the first workflow
      const completed = list.find((w) => w.status === 'complete');
      if (completed) {
        setSelectedWorkflowId(completed.id);
      } else if (list.length > 0) {
        setSelectedWorkflowId(list[0].id);
      } else {
        setSelectedWorkflowId('');
      }
    } catch (e) {
      console.error('Failed to list workflows:', e);
    } finally {
      setLoading(false);
    }
  }, [activeProjectId]);

  useEffect(() => {
    fetchWorkflows();
  }, [fetchWorkflows]);

  // Auto-dismiss toast
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(t);
  }, [toast]);

  const handleExportPdf = async (
    workflowId: string, 
    workflowName: string, 
    type: 'mpo' | 'environmental' | 'selectivity' = 'mpo'
  ) => {
    if (!workflowId) return;
    setExportingId(workflowId);
    try {
      const defaultFilename = type === 'mpo'
        ? `edeon_report_${workflowName.toLowerCase().replace(/[^a-z0-9]+/g, '_')}.pdf`
        : type === 'environmental'
          ? `edeon_environmental_dossier_${workflowName.toLowerCase().replace(/[^a-z0-9]+/g, '_')}.pdf`
          : `edeon_selectivity_chartbook_${workflowName.toLowerCase().replace(/[^a-z0-9]+/g, '_')}.pdf`;

      const filePath = await save({
        filters: [
          {
            name: 'PDF Documents',
            extensions: ['pdf'],
          },
        ],
        defaultPath: defaultFilename,
      });
      if (filePath) {
        if (type === 'mpo') {
          await exportPdf(workflowId, filePath);
        } else if (type === 'environmental') {
          await invoke('export_environmental_dossier', { workflowId, outputPath: filePath });
        } else if (type === 'selectivity') {
          await invoke('export_selectivity_chartbook', { workflowId, outputPath: filePath });
        }
        setToast({ message: 'PDF report exported successfully!', type: 'success' });
      }
    } catch (e) {
      console.error('Failed to export PDF:', e);
      setToast({ message: `Failed to export PDF: ${String(e)}`, type: 'error' });
    } finally {
      setExportingId(null);
    }
  };

  const completedWorkflows = workflows.filter((w) => w.status === 'complete');
  const activeSelectedWorkflow = workflows.find((w) => w.id === selectedWorkflowId);

  if (!activeProjectId) {
    return (
      <div className="main-content" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
        <EmptyState
          icon={<FolderOpen size={20} />}
          title="No project selected"
          description="Select a project from the sidebar to access its generated reports and dossiers."
        />
      </div>
    );
  }

  return (
    <div className="main-content">
      <div className="reports-container">
        {/* Banner */}
        <div className="reports-header-banner" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h1>Optimized Crop Protection Dossier Generator</h1>
            <p>
              Generate publication-quality reports, dossier sheets, and multi-parameter optimization summaries for <strong>{activeProject?.name}</strong>. Selected properties, bee/toxicity warnings, and selectivity gradients are automatically formatted.
            </p>
          </div>
          {activeSelectedWorkflow && (
            <div style={{ alignSelf: 'center', marginLeft: '16px' }} onClick={(e) => e.stopPropagation()}>
              <CitationExportButton
                target="report"
                metadata={{
                  name: activeSelectedWorkflow.name,
                  date: new Date(activeSelectedWorkflow.started_at).toISOString().split('T')[0]
                }}
              />
            </div>
          )}
        </div>

        {/* Templates Grid */}
        <h2 className="reports-section-title">Available Report Templates</h2>
        <div className="reports-grid">
          {/* Active MPO Summary Template */}
          <div className="report-card available">
            <span className="report-card-badge available">Ready</span>
            <h3>Multi-Parameter Agrochemical Optimization Report</h3>
            <p>
              Provides a structured summary of all synthesized or imported leads. Lists physicochemical properties, Tice rule compliance, ecological selectivity, and composite MPO ranking.
            </p>
            
            {/* Page mockup illustration */}
            <div className="report-card-mockup">
              <div className="mockup-header" />
              <div className="mockup-row" />
              <div className="mockup-row half" />
              <div className="mockup-row quarter" />
              <div className="mockup-pills">
                <span className="mockup-pill green" />
                <span className="mockup-pill amber" />
                <span className="mockup-pill red" />
              </div>
            </div>

            <div className="report-card-actions">
              <div className="report-card-selector">
                <label style={{ marginRight: '6px' }}>Run:</label>
                <select
                  value={selectedWorkflowId}
                  onChange={(e) => setSelectedWorkflowId(e.target.value)}
                  disabled={workflows.length === 0}
                >
                  {workflows.length === 0 ? (
                    <option>No workflows run</option>
                  ) : completedWorkflows.length === 0 ? (
                    <option>No completed runs</option>
                  ) : (
                    completedWorkflows.map((w) => (
                      <option key={w.id} value={w.id}>
                        {w.name} ({w.compounds_total} cmpds)
                      </option>
                    ))
                  )}
                </select>
              </div>

              <button
                className="library-btn-primary"
                style={{ padding: '4px 10px', height: '22px', fontSize: '11px' }}
                disabled={!selectedWorkflowId || exportingId === selectedWorkflowId || !activeSelectedWorkflow || activeSelectedWorkflow.status !== 'complete'}
                onClick={() => handleExportPdf(selectedWorkflowId, activeSelectedWorkflow?.name ?? 'MPO_Report')}
              >
                {exportingId === selectedWorkflowId ? 'Exporting...' : 'Export PDF'}
              </button>
            </div>
          </div>

          {/* Unlocked Pollinator Dossier */}
          <div className="report-card available">
            <span className="report-card-badge available">Ready</span>
            <h3>Environmental & Bee Safety Dossier</h3>
            <p>
              Deep-dive ecological assessment detailing hazard quotients, OECD pollinator guidelines compliance, bio-concentration margins, and soil/sediment persistent risk profiles.
            </p>
            <div className="report-card-mockup">
              <div className="mockup-header" style={{ backgroundColor: 'var(--color-brand-700)' }} />
              <div className="mockup-row" />
              <div className="mockup-row half" />
              <div className="mockup-row quarter" />
            </div>
            <div className="report-card-actions">
              <div className="report-card-selector">
                <label style={{ marginRight: '6px' }}>Run:</label>
                <select
                  value={selectedWorkflowId}
                  onChange={(e) => setSelectedWorkflowId(e.target.value)}
                  disabled={workflows.length === 0}
                >
                  {workflows.length === 0 ? (
                    <option>No workflows run</option>
                  ) : completedWorkflows.length === 0 ? (
                    <option>No completed runs</option>
                  ) : (
                    completedWorkflows.map((w) => (
                      <option key={w.id} value={w.id}>
                        {w.name} ({w.compounds_total} cmpds)
                      </option>
                    ))
                  )}
                </select>
              </div>

              <button
                className="library-btn-primary"
                style={{ padding: '4px 10px', height: '22px', fontSize: '11px' }}
                disabled={!selectedWorkflowId || exportingId === selectedWorkflowId || !activeSelectedWorkflow || activeSelectedWorkflow.status !== 'complete'}
                onClick={() => handleExportPdf(selectedWorkflowId, activeSelectedWorkflow?.name ?? 'Environmental_Dossier', 'environmental')}
              >
                {exportingId === selectedWorkflowId ? 'Exporting...' : 'Export PDF'}
              </button>
            </div>
          </div>

          {/* Unlocked Species Selectivity Dossier */}
          <div className="report-card available">
            <span className="report-card-badge available">Ready</span>
            <h3>Off-Target Species Selectivity Chartbook</h3>
            <p>
              Formatted cross-species toxicity ratios. Generates safety margin comparisons between pest targets and terrestrial/aquatic indicator organisms.
            </p>
            <div className="report-card-mockup">
              <div className="mockup-header" style={{ backgroundColor: 'var(--color-brand-700)' }} />
              <div className="mockup-row" />
              <div className="mockup-row half" />
              <div className="mockup-row quarter" />
            </div>
            <div className="report-card-actions">
              <div className="report-card-selector">
                <label style={{ marginRight: '6px' }}>Run:</label>
                <select
                  value={selectedWorkflowId}
                  onChange={(e) => setSelectedWorkflowId(e.target.value)}
                  disabled={workflows.length === 0}
                >
                  {workflows.length === 0 ? (
                    <option>No workflows run</option>
                  ) : completedWorkflows.length === 0 ? (
                    <option>No completed runs</option>
                  ) : (
                    completedWorkflows.map((w) => (
                      <option key={w.id} value={w.id}>
                        {w.name} ({w.compounds_total} cmpds)
                      </option>
                    ))
                  )}
                </select>
              </div>

              <button
                className="library-btn-primary"
                style={{ padding: '4px 10px', height: '22px', fontSize: '11px' }}
                disabled={!selectedWorkflowId || exportingId === selectedWorkflowId || !activeSelectedWorkflow || activeSelectedWorkflow.status !== 'complete'}
                onClick={() => handleExportPdf(selectedWorkflowId, activeSelectedWorkflow?.name ?? 'Selectivity_Chartbook', 'selectivity')}
              >
                {exportingId === selectedWorkflowId ? 'Exporting...' : 'Export PDF'}
              </button>
            </div>
          </div>
        </div>

        {/* History Table */}
        <h2 className="reports-section-title">Workflow Execution History</h2>
        <div className="reports-history-section">
          {loading && workflows.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '20px', color: 'var(--color-text-600)' }}>
              Loading workflow records...
            </div>
          ) : workflows.length === 0 ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '40px 0', width: '100%' }}>
              <EmptyState
                icon={<FileText size={20} />}
                title="No reports generated yet"
                description="Execute an assessment or design workflow on this project to compile downloadable reports."
                primaryAction={{
                  label: "Go to Workflows",
                  onClick: () => {
                    useUIStore.getState().setActiveView('workflows');
                  }
                }}
              />
            </div>
          ) : (
            <table ref={tableRef} className="results-table" style={{ width: '100%' }}>
              <thead>
                <tr>
                  <th style={{ width: `${widths[0]}%`, position: 'relative' }}>
                    WORKFLOW NAME
                    <div className="col-resize-handle" onMouseDown={(e) => handleMouseDown(0, e)} />
                  </th>
                  <th style={{ width: `${widths[1]}%`, position: 'relative' }} className="center">
                    STATUS
                    <div className="col-resize-handle" onMouseDown={(e) => handleMouseDown(1, e)} />
                  </th>
                  <th style={{ width: `${widths[2]}%`, position: 'relative' }} className="center">
                    COMPOUNDS
                    <div className="col-resize-handle" onMouseDown={(e) => handleMouseDown(2, e)} />
                  </th>
                  <th style={{ width: `${widths[3]}%`, position: 'relative' }} className="center">
                    RUN DATE
                    <div className="col-resize-handle" onMouseDown={(e) => handleMouseDown(3, e)} />
                  </th>
                  <th style={{ width: `${widths[4]}%`, position: 'relative' }} className="center">
                    ACTIONS
                    <div className="col-resize-handle" onMouseDown={(e) => handleMouseDown(4, e)} />
                  </th>
                </tr>
              </thead>
              <tbody>
                {workflows.map((w) => {
                  const runDate = new Date(w.started_at).toLocaleDateString(undefined, {
                    month: 'short',
                    day: 'numeric',
                    year: 'numeric',
                  });

                  return (
                    <tr key={w.id}>
                      <td>
                        <div className="compound-name">{w.name}</div>
                        <div className="compound-subtitle" style={{ fontFamily: 'var(--font-mono)' }}>
                          ID: {w.id.slice(0, 8)}
                        </div>
                      </td>
                      <td className="center">
                        {w.status === 'complete' ? (
                          <span className="risk-badge low">✓ Complete</span>
                        ) : w.status === 'running' ? (
                          <span className="risk-badge medium">⏳ Running ({w.stages_complete}/7)</span>
                        ) : w.status === 'failed' ? (
                          <span className="risk-badge high">✕ Failed</span>
                        ) : (
                          <span className="risk-badge medium">⏹ Stopped</span>
                        )}
                      </td>
                      <td className="center" style={{ fontWeight: 500, color: 'var(--color-text-900)' }}>
                        {w.compounds_processed} / {w.compounds_total}
                      </td>
                      <td className="center" style={{ color: 'var(--color-text-600)' }}>
                        {runDate}
                      </td>
                      <td className="center">
                        <button
                          className={w.status === 'complete' ? 'library-btn-primary' : 'library-btn'}
                          style={{
                            padding: '2px 8px',
                            height: '20px',
                            fontSize: '10px',
                          }}
                          disabled={w.status !== 'complete' || exportingId === w.id}
                          onClick={() => handleExportPdf(w.id, w.name)}
                        >
                          {exportingId === w.id ? 'Exporting...' : w.status === 'complete' ? 'Download PDF' : 'Unavailable'}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Toast notification */}
      {toast && (
        <div className={`toast toast-${toast.type}`}>
          {toast.message}
        </div>
      )}
    </div>
  );
}
