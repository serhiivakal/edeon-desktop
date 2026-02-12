import { useState, useEffect } from 'react';
import { useWorkflowStore, type WorkflowType } from '../../store/workflowStore';
import { useProjectStore } from '../../store/projectStore';
import { useUIStore } from '../../store/uiStore';
import { save } from '@tauri-apps/plugin-dialog';
import { invoke } from '@tauri-apps/api/core';

export function WorkflowHeader() {
  const activeProjectId = useProjectStore((s) => s.activeProjectId);
  const activeWorkflow = useWorkflowStore((s) => s.activeWorkflow);
  const isRunning = useWorkflowStore((s) => s.isRunning);
  const stages = useWorkflowStore((s) => s.stages);
  const pythonReady = useWorkflowStore((s) => s.pythonReady);
  const error = useWorkflowStore((s) => s.error);
  const startWorkflow = useWorkflowStore((s) => s.startWorkflow);
  const cancelWorkflow = useWorkflowStore((s) => s.cancelWorkflow);
  const exportPdf = useWorkflowStore((s) => s.exportPdf);
  const selectedWorkflowType = useWorkflowStore((s) => s.selectedWorkflowType);
  const setWorkflowType = useWorkflowStore((s) => s.setWorkflowType);
  const reset = useWorkflowStore((s) => s.reset);
  const clearWorkflow = useWorkflowStore((s) => s.clearWorkflow);

  const selectedWorkflowId = useWorkflowStore((s) => s.selectedWorkflowId);
  const availableWorkflows = useWorkflowStore((s) => s.availableWorkflows);
  const runNamedWorkflow = useWorkflowStore((s) => s.runNamedWorkflow);

  const selectedCompoundId = useUIStore((s) => s.selectedCompoundId);
  const setSelectedCompound = useUIStore((s) => s.setSelectedCompound);
  const [allCompounds, setAllCompounds] = useState<any[]>([]);

  useEffect(() => {
    if (selectedWorkflowType === 'bioisostere_opt' && activeProjectId) {
      invoke<any>('list_compounds', { projectId: activeProjectId, page_size: 500 })
        .then((res) => {
          setAllCompounds(res.compounds || []);
        })
        .catch(console.error);
    }
  }, [selectedWorkflowType, activeProjectId]);

  const stagesComplete = stages.filter((s) => s.status === 'done').length;
  const totalStages = stages.length;

  const handleStart = () => {
    if (activeProjectId) {
      if (selectedWorkflowId && selectedWorkflowId !== 'legacy') {
        runNamedWorkflow(activeProjectId);
        return;
      }
      if (selectedWorkflowType === 'bioisostere_opt' && !selectedCompoundId) {
        useWorkflowStore.setState({ error: 'Please select a starting lead compound from the dropdown first.' });
        return;
      }
      if (selectedWorkflowType === 'library_prep' || selectedWorkflowType === 'active_learning') {
        const uploadedFile = useWorkflowStore.getState().uploadedFile;
        const structureColumn = useWorkflowStore.getState().structureColumn;
        if (!uploadedFile) {
          useWorkflowStore.setState({ error: 'Please upload a library file (.smi, .smiles, .sdf, or .csv) first.' });
          return;
        }
        if (uploadedFile.extension === 'csv' && !structureColumn) {
          useWorkflowStore.setState({ error: 'Please select the target structure column for the uploaded CSV file.' });
          return;
        }
      }
      startWorkflow(activeProjectId);
    }
  };

  const handleCancel = async () => {
    if (activeWorkflow) {
      await cancelWorkflow(activeWorkflow.id);
    }
  };

  const handleExportPdf = async () => {
    if (!activeWorkflow) return;
    try {
      const filePath = await save({
        filters: [
          {
            name: 'PDF Documents',
            extensions: ['pdf'],
          },
        ],
        defaultPath: `edeon_report_${activeWorkflow.id.slice(0, 8)}.pdf`,
      });
      if (filePath) {
        await exportPdf(activeWorkflow.id, filePath);
      }
    } catch (e) {
      console.error('Failed to export PDF:', e);
    }
  };

  const handleBackToGallery = () => {
    if (isRunning) {
      useWorkflowStore.setState({ selectedWorkflowId: null });
    } else {
      reset();
    }
  };

  return (
    <div className="workflow-header">
      <div className="workflow-header-info">
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '4px' }}>
          {selectedWorkflowId && (
            <button
              onClick={handleBackToGallery}
              style={{
                padding: '4px 10px',
                borderRadius: '6px',
                border: '0.5px solid var(--color-border)',
                background: 'var(--color-surface)',
                color: 'var(--color-brand-900)',
                fontSize: '11px',
                fontWeight: 600,
                cursor: 'pointer',
                boxShadow: 'var(--shadow-sm)',
                transition: 'all 0.2s',
              }}
            >
              ← Back to Gallery
            </button>
          )}
          <h2 style={{ margin: 0 }}>
            {activeWorkflow?.name ?? (
              selectedWorkflowId && selectedWorkflowId !== 'legacy' ? (availableWorkflows.find(w => w.id === selectedWorkflowId)?.name) :
              selectedWorkflowType === 'lead_opt' ? 'Lead Optimization Pre-Screen' :
              selectedWorkflowType === 'bioisostere_opt' ? 'Bioisosteric Lead Optimization' :
              selectedWorkflowType === 'active_learning' ? 'Virtual Screening & Active Learning' :
              selectedWorkflowType === 'library_prep' ? 'Screening Library Preparation' :
              'Resistance Mitigation & Selectivity'
            )}
          </h2>
          {!selectedWorkflowId && !isRunning && !activeWorkflow && (
            <select
              value={selectedWorkflowType}
              onChange={(e) => setWorkflowType(e.target.value as WorkflowType)}
              style={{
                padding: '4px 10px',
                borderRadius: '6px',
                border: '0.5px solid var(--color-border)',
                background: 'var(--color-surface)',
                color: 'var(--color-text-800)',
                fontSize: '11px',
                fontWeight: 600,
                outline: 'none',
                cursor: 'pointer',
                boxShadow: 'var(--shadow-sm)',
                transition: 'border-color 0.2s',
              }}
            >
              <option value="lead_opt">Lead Optimization Pre-Screen (7-Stage)</option>
              <option value="bioisostere_opt">Bioisosteric Lead Optimization & Docking</option>
              <option value="active_learning">Virtual Screening & Active Learning Gate</option>
              <option value="resistance_mitigation">Target-Site Resistance Mitigation</option>
              <option value="library_prep">Screening Library Preparation</option>
            </select>
          )}
        </div>
        <div className="workflow-header-meta">
          {isRunning ? (
            (() => {
              const runningStage = stages.find((s) => s.status === 'running');
              const runningStagePercent = runningStage?.progressPercent || 0;
              const continuousProgressPercent = totalStages > 0
                ? Math.round(((stagesComplete + (runningStagePercent / 100)) / totalStages) * 100)
                : 0;

              return (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginTop: '4px' }}>
                  <span style={{ fontWeight: 600, color: 'var(--color-text-800)' }}>
                    {stagesComplete} of {totalStages} stages complete
                  </span>
                  <span style={{ color: 'var(--color-text-400)' }}>·</span>
                  <span style={{ color: 'var(--color-text-600)', fontSize: '11px' }}>
                    {runningStage?.progressLabel || 'processing...'}
                  </span>
                  <div className="header-progress-track" style={{ width: '180px', marginLeft: '4px', background: 'var(--color-border)' }}>
                    <div
                      className="header-progress-fill"
                      style={{
                        width: `${continuousProgressPercent}%`,
                        background: 'var(--color-brand-600)'
                      }}
                    />
                  </div>
                  <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-brand-700)' }}>
                    {continuousProgressPercent}%
                  </span>
                </div>
              );
            })()
          ) : activeWorkflow?.status === 'complete' ? (
            <>
              {totalStages} of {totalStages} stages complete
              {' · '}{activeWorkflow.compounds_total} compounds processed
            </>
          ) : activeWorkflow?.status === 'failed' ? (
            <span style={{ color: 'var(--color-red-700)' }}>Workflow failed</span>
          ) : (
            'Ready to start'
          )}
        </div>
        {selectedWorkflowType === 'bioisostere_opt' && !isRunning && !activeWorkflow && (
          <div style={{ marginTop: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '11px', color: 'var(--color-text-500)', fontWeight: 600 }}>
              🎯 Starting Lead:
            </span>
            <select
              value={selectedCompoundId || ''}
              onChange={(e) => setSelectedCompound(e.target.value || null)}
              style={{
                padding: '4px 10px',
                borderRadius: '6px',
                border: '0.5px solid var(--color-border)',
                background: 'var(--color-surface)',
                color: 'var(--color-text-800)',
                fontSize: '11px',
                fontWeight: 500,
                outline: 'none',
                cursor: 'pointer',
                maxWidth: '260px',
                boxShadow: 'var(--shadow-sm)',
              }}
            >
              <option value="">-- Select a starting compound --</option>
              {allCompounds.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
        )}
        {error && (
          <div className="workflow-error">{error}</div>
        )}
      </div>
      <div className="workflow-header-actions">
        {!isRunning && activeWorkflow && (
          <button
            className="workflow-btn-stop"
            onClick={clearWorkflow}
            title="Reset workflow to default configuration"
          >
            Clear Workflow
          </button>
        )}
        {!isRunning && (
          <button
            className="workflow-btn-configure"
            onClick={handleStart}
            disabled={!activeProjectId || !pythonReady}
            title={!pythonReady ? 'Python engine not available' : undefined}
          >
            {activeWorkflow ? 'Re-run' : 'Start Workflow'}
          </button>
        )}
        {!isRunning && activeWorkflow?.status === 'complete' && (
          <button
            className="workflow-btn-configure"
            onClick={handleExportPdf}
            style={{ borderColor: 'var(--color-brand-600)', color: 'var(--color-brand-700)', fontWeight: 500 }}
          >
            Export PDF Report
          </button>
        )}
        {isRunning && (
          <button
            className="workflow-btn-stop"
            onClick={handleCancel}
            title="Cancel current running workflow"
          >
            Cancel Workflow
          </button>
        )}
        {!pythonReady && !isRunning && (
          <span className="workflow-python-warning">⚠ Python not ready</span>
        )}
      </div>
    </div>
  );
}
