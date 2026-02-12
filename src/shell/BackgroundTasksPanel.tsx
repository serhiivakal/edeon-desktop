import React from 'react';
import { useUIStore } from '../store/uiStore';
import { useWorkflowStore } from '../store/workflowStore';
import styles from './BackgroundTasksPanel.module.css';

export const BackgroundTasksPanel: React.FC = () => {
  const showTasksPanel = useUIStore((state) => state.showTasksPanel);
  const setShowTasksPanel = useUIStore((state) => state.setShowTasksPanel);
  const isRunning = useWorkflowStore((state) => state.isRunning);
  const selectedWorkflowType = useWorkflowStore((state) => state.selectedWorkflowType);
  const activeWorkflow = useWorkflowStore((state) => state.activeWorkflow);
  const stages = useWorkflowStore((state) => state.stages);
  const cancelWorkflow = useWorkflowStore((state) => state.cancelWorkflow);

  if (!showTasksPanel) return null;

  // Calculate current workflow progress percent
  const totalStages = stages.length;
  const runningOrCompletedStages = stages.filter(
    (s) => s.status === 'done' || s.status === 'running'
  ).length;
  const progressPercent =
    totalStages > 0
      ? Math.round((runningOrCompletedStages / totalStages) * 100)
      : 0;

  // Find active stage name
  const activeStage = stages.find((s) => s.status === 'running')?.name || 'Running stage...';

  const handleCancel = async () => {
    if (activeWorkflow?.id) {
      await cancelWorkflow(activeWorkflow.id);
    }
  };

  const hasTasks = isRunning;

  return (
    <div className={styles.panelContainer}>
      <div className={styles.header}>
        <h3 className={styles.title}>Background Tasks</h3>
        <button
          className={styles.closeButton}
          onClick={() => setShowTasksPanel(false)}
        >
          ✕
        </button>
      </div>

      <div className={styles.content}>
        {hasTasks ? (
          <div className={styles.taskItem}>
            <div className={styles.taskHeader}>
              <span className={styles.taskName}>
                {selectedWorkflowType === 'lead_opt'
                  ? 'Lead Optimization'
                  : selectedWorkflowType === 'bioisostere_opt'
                  ? 'Bioisostere Gen & Docking'
                  : 'Library Prep'}
              </span>
              <span className={styles.taskStatus}>Active</span>
            </div>
            
            <div className={styles.progressBarContainer}>
              <div
                className={styles.progressBarFill}
                style={{ width: `${progressPercent}%` }}
              />
            </div>

            <div className={styles.taskMeta}>
              <span>Stage: {activeStage}</span>
              <span>{progressPercent}%</span>
            </div>

            <button className={styles.cancelBtn} onClick={handleCancel}>
              Cancel Task
            </button>
          </div>
        ) : (
          <div className={styles.emptyText}>No background tasks are running.</div>
        )}
      </div>
    </div>
  );
};
