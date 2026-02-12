import { useWorkflowStore } from '../../store/workflowStore';
import { PipelineStage } from './PipelineStage';

export function Pipeline() {
  const stages = useWorkflowStore((s) => s.stages);
  const toggleStage = useWorkflowStore((s) => s.toggleStage);
  const isRunning = useWorkflowStore((s) => s.isRunning);

  return (
    <div>
      <div className="section-label">PIPELINE</div>
      <div className="pipeline">
        {stages.map((stage, i) => {
          const prevStage = i > 0 ? stages[i - 1] : null;
          const connectorDone =
            prevStage?.status === 'done' && stage.status !== 'waiting';
          const isTogglable = stage.id >= 3 && stage.id <= 6;
          const isConnectorDisabled = stage.enabled === false;

          return (
            <div key={stage.id} style={{ display: 'flex', alignItems: 'flex-start' }}>
              {i > 0 && (
                <div
                  className={`pipeline-connector ${connectorDone ? 'done' : 'pending'} ${isConnectorDisabled ? 'disabled' : ''}`}
                />
              )}
              <div
                onClick={() => {
                  if (isTogglable && !isRunning) {
                    toggleStage(stage.id);
                  }
                }}
                style={{
                  cursor: isTogglable && !isRunning ? 'pointer' : 'default',
                  userSelect: 'none',
                }}
              >
                <PipelineStage stage={stage} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
