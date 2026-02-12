import { useWorkflowStore } from '../../store/workflowStore';
import { PipelineStage } from './PipelineStage';

export function Pipeline() {
  const stages = useWorkflowStore((s) => s.stages);

  return (
    <div>
      <div className="section-label">PIPELINE</div>
      <div className="pipeline">
        {stages.map((stage, i) => {
          const prevStage = i > 0 ? stages[i - 1] : null;
          const connectorDone =
            prevStage?.status === 'done' && stage.status !== 'waiting';

          return (
            <div key={stage.id} style={{ display: 'flex', alignItems: 'flex-start' }}>
              {i > 0 && (
                <div
                  className={`pipeline-connector ${connectorDone ? 'done' : 'pending'}`}
                />
              )}
              <PipelineStage stage={stage} />
            </div>
          );
        })}
      </div>
    </div>
  );
}
