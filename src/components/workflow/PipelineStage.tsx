import type { PipelineStage as PipelineStageType } from '../../types';
import { useWorkflowStore } from '../../store/workflowStore';
import { invoke } from '@tauri-apps/api/core';

interface Props {
  stage: PipelineStageType;
}

export function PipelineStage({ stage }: Props) {
  const isExcluded = stage.enabled === false;

  return (
    <div className={`pipeline-stage ${stage.status} ${isExcluded ? 'excluded' : ''}`}>
      <div className="stage-header">
        <div className={`stage-icon ${stage.status} ${isExcluded ? 'excluded' : ''}`}>
          {isExcluded ? '✕' : (
            <>
              {stage.status === 'done' && '✓'}
              {stage.status === 'running' && '●'}
              {stage.status === 'waiting' && '○'}
            </>
          )}
        </div>
        <span className="stage-number">{stage.id}</span>
        {isExcluded && <span className="stage-excluded-badge">Excluded</span>}
      </div>

      <div className="stage-name">{stage.name}</div>
      <div className="stage-description">{stage.description}</div>

      <div className="stage-result">
        {isExcluded ? (
          <span style={{ color: 'var(--color-text-400)', fontSize: '10px', fontStyle: 'italic' }}>Skipped</span>
        ) : (
          <>
            {stage.status === 'done' && (
              stage.name === '3D Interaction Maps' ? (
                <button
                  className="results-action active"
                  style={{
                    marginTop: '4px',
                    background: 'rgba(37, 99, 235, 0.12)',
                    border: '0.5px solid rgba(37, 99, 235, 0.35)',
                    color: '#2563eb',
                    fontSize: '10px',
                    padding: '3px 8px',
                    borderRadius: '4px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}
                  onClick={(e) => {
                    e.stopPropagation();
                    const dockingJobId = useWorkflowStore.getState().dockingJobId;
                    if (dockingJobId) {
                      useWorkflowStore.getState().setActiveInteractionJobId(dockingJobId);
                    } else {
                      // Fallback: search history by the smiles of the top result
                      const results = useWorkflowStore.getState().results;
                      if (results.length > 0) {
                        const topCompound = results[0];
                        const selectedReceptorPreset = useWorkflowStore.getState().selectedReceptorPreset;
                        const presetMap: Record<string, string> = {
                          als: 'ALS',
                          accase: 'ACCase',
                          epsps: 'EPSPS',
                          gs: 'GS',
                          hppd: 'HPPD',
                          ppo: 'PPO',
                          ps2: 'PSII',
                          sdh: 'SDH',
                        };
                        const targetReceptorName = (presetMap[selectedReceptorPreset.toLowerCase()] || selectedReceptorPreset).toUpperCase();

                        invoke<any[]>('history_list', {
                          receptorId: null,
                          starredOnly: null,
                          searchQuery: topCompound.smiles
                        }).then(jobs => {
                          const match = jobs.find(j => 
                            j.ligand_smiles === topCompound.smiles &&
                            j.receptor_display_name?.toUpperCase() === targetReceptorName
                          );
                          if (match) {
                            useWorkflowStore.getState().setActiveInteractionJobId(match.job_id);
                          } else {
                            alert('No docking result found for this workflow.');
                          }
                        });
                      }
                    }
                  }}
                >
                  👁 View 3D Maps
                </button>
              ) : (
                <>
                  <span className="stage-result-count">{stage.compoundCount}</span>
                  {' '}{stage.compoundLabel}
                </>
              )
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
          </>
        )}
      </div>
    </div>
  );
}
