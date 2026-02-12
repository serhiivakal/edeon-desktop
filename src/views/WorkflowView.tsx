import { useEffect } from 'react';
import { WorkflowHeader } from '../components/workflow/WorkflowHeader';
import { Pipeline } from '../components/workflow/Pipeline';
import { ResultsTable } from '../components/workflow/ResultsTable';
import { useWorkflowStore } from '../store/workflowStore';
import { useProjectStore } from '../store/projectStore';

export function WorkflowView() {
  const activeProjectId = useProjectStore((s) => s.activeProjectId);
  const loadLatestWorkflow = useWorkflowStore((s) => s.loadLatestWorkflow);
  const checkPython = useWorkflowStore((s) => s.checkPython);
  const reset = useWorkflowStore((s) => s.reset);

  useEffect(() => {
    checkPython();
    if (activeProjectId) {
      loadLatestWorkflow(activeProjectId);
    }
    return () => reset();
  }, [activeProjectId, loadLatestWorkflow, checkPython, reset]);

  return (
    <div className="main-content">
      <WorkflowHeader />
      <Pipeline />
      <ResultsTable />
    </div>
  );
}
