import { useEffect } from 'react';
import { WorkflowHeader } from '../components/workflow/WorkflowHeader';
import { Pipeline } from '../components/workflow/Pipeline';
import { ResultsTable } from '../components/workflow/ResultsTable';
import { WorkflowRunConfig } from '../components/workflow/WorkflowRunConfig';
import { useWorkflowStore } from '../store/workflowStore';
import { useProjectStore } from '../store/projectStore';
import { useCompoundStore } from '../store/compoundStore';
import { InteractionViewerModal } from '../components/workflow/InteractionViewerModal';
import { WorkflowGalleryView } from './WorkflowGalleryView';
import { DecisionArtifact } from '../components/workflow/DecisionArtifact';

import { useUIStore } from '../store/uiStore';

export function WorkflowView() {
  const activeProjectId = useProjectStore((s) => s.activeProjectId);
  const loadLatestWorkflow = useWorkflowStore((s) => s.loadLatestWorkflow);
  const checkPython = useWorkflowStore((s) => s.checkPython);
  const fetchCompounds = useCompoundStore((s) => s.fetchCompounds);

  const selectedWorkflowId = useWorkflowStore((s) => s.selectedWorkflowId);
  const workflowResult = useWorkflowStore((s) => s.workflowResult);

  const activeInteractionJobId = useWorkflowStore((s) => s.activeInteractionJobId);
  const setActiveInteractionJobId = useWorkflowStore((s) => s.setActiveInteractionJobId);
  const dockingResult = useWorkflowStore((s) => s.dockingResult);
  const dockingReceptorHash = useWorkflowStore((s) => s.dockingReceptorHash);

  const isMaximized = useUIStore((s) => s.isResultsTableMaximized);

  useEffect(() => {
    checkPython();
    if (activeProjectId) {
      loadLatestWorkflow(activeProjectId, selectedWorkflowId);
      fetchCompounds(activeProjectId);
    }
  }, [activeProjectId, selectedWorkflowId, loadLatestWorkflow, checkPython, fetchCompounds]);

  if (!selectedWorkflowId) {
    return (
      <div className="main-content" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', boxSizing: 'border-box' }}>
        <WorkflowGalleryView />
      </div>
    );
  }

  return (
    <div className="main-content" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', boxSizing: 'border-box', padding: '16px' }}>
      <WorkflowHeader />
      {!isMaximized && (
        <div style={{ display: 'flex', gap: '16px', marginBottom: '16px', alignItems: 'flex-start', flex: 1, minHeight: 0, overflow: 'hidden' }}>
          <div style={{ flex: 1, minWidth: 0, height: '100%', overflowY: 'auto' }}>
            {workflowResult ? (
              <DecisionArtifact workflowResult={workflowResult} />
            ) : (
              <Pipeline />
            )}
          </div>
          {!workflowResult && <WorkflowRunConfig />}
        </div>
      )}
      <ResultsTable />

      {activeInteractionJobId && (
        <InteractionViewerModal
          jobId={activeInteractionJobId}
          onClose={() => setActiveInteractionJobId(null)}
          dockingResult={dockingResult}
          receptorHash={dockingReceptorHash || undefined}
        />
      )}
    </div>
  );
}
