import type { PipelineStage as PipelineStageType } from '../../types';

interface Props {
  stage: PipelineStageType;
}

export function PipelineStage({ stage }: Props) {
  return (
    <div className={`pipeline-stage ${stage.status}`}>
      <div className="stage-header">
        <div className={`stage-icon ${stage.status}`}>
          {stage.status === 'done' && '✓'}
          {stage.status === 'running' && '●'}
          {stage.status === 'waiting' && '○'}
        </div>
        <span className="stage-number">{stage.id}</span>
      </div>

      <div className="stage-name">{stage.name}</div>
      <div className="stage-description">{stage.description}</div>

      <div className="stage-result">
        {stage.status === 'done' && (
          <>
            <span className="stage-result-count">{stage.compoundCount}</span>
            {' '}{stage.compoundLabel}
          </>
        )}
        {stage.status === 'running' && (
          <>
            <div className="stage-progress-track">
              <div
                className="stage-progress-fill"
                style={{ width: `${stage.progressPercent}%` }}
              />
            </div>
            <div className="stage-progress-label">{stage.progressLabel}</div>
          </>
        )}
        {stage.status === 'waiting' && 'Waiting'}
      </div>
    </div>
  );
}
