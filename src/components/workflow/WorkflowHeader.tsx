import { useWorkflowStore } from '../../store/workflowStore';
import { useProjectStore } from '../../store/projectStore';

export function WorkflowHeader() {
  const activeProjectId = useProjectStore((s) => s.activeProjectId);
  const activeWorkflow = useWorkflowStore((s) => s.activeWorkflow);
  const isRunning = useWorkflowStore((s) => s.isRunning);
  const stages = useWorkflowStore((s) => s.stages);
  const pythonReady = useWorkflowStore((s) => s.pythonReady);
  const error = useWorkflowStore((s) => s.error);
  const startWorkflow = useWorkflowStore((s) => s.startWorkflow);

  const stagesComplete = stages.filter((s) => s.status === 'done').length;
  const totalStages = stages.length;

  const handleStart = () => {
    if (activeProjectId) {
      startWorkflow(activeProjectId);
    }
  };

  return (
    <div className="workflow-header">
      <div className="workflow-header-info">
        <h2>
          {activeWorkflow?.name ?? 'Lead Optimization Pre-Screen'}
        </h2>
        <div className="workflow-header-meta">
          {isRunning ? (
            <>
              {stagesComplete} of {totalStages} stages complete
              {' · '}processing...
            </>
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
        {error && (
          <div className="workflow-error">{error}</div>
        )}
      </div>
      <div className="workflow-header-actions">
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
        {isRunning && (
          <button className="workflow-btn-stop" disabled>
            Running...
          </button>
        )}
        {!pythonReady && !isRunning && (
          <span className="workflow-python-warning">⚠ Python not ready</span>
        )}
      </div>
    </div>
  );
}
