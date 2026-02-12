import { useEffect, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { useUIStore } from '../../store/uiStore';
import { useWorkflowStore } from '../../store/workflowStore';
import styles from './StatusBar.module.css';

interface StatusData {
  t1_loaded: number;
  t1_total: number;
  t1_all_loaded: boolean;
  opera_available: boolean;
  claude_api_configured: boolean;
  cpu_percent: number;
  memory_mb: number;
  background_tasks_count: number;
  background_tasks: any[];
}

export function StatusBar() {
  const [status, setStatus] = useState<StatusData | null>(null);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const data = await invoke<StatusData>('app_meta_get_status');
        setStatus(data);
      } catch (err) {
        console.warn('Failed to retrieve system status indicators:', err);
      }
    };

    // Fetch immediately on mount, then poll every 5 seconds
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);

    return () => clearInterval(interval);
  }, []);
  const showTasksPanel = useUIStore((s) => s.showTasksPanel);
  const setShowTasksPanel = useUIStore((s) => s.setShowTasksPanel);
  const isWorkflowRunning = useWorkflowStore((s) => s.isRunning);

  // Compute active background task count including workflow execution
  const activeTasksCount = (status?.background_tasks_count || 0) + (isWorkflowRunning ? 1 : 0);

  return (
    <footer className={`${styles.statusBar} status-bar`} style={{ position: 'relative' }}>

      {/* Left side: System status flags */}
      <div className={styles.left}>
        <div className={styles.item}>
          <span
            className={`${styles.dot} ${
              status?.t1_all_loaded ? styles.dotGood : styles.dotModerate
            }`}
          />
          <span>T1 Models: {status ? `${status.t1_loaded}/${status.t1_total}` : 'offline'}</span>
        </div>

        <div className={styles.separator} />

        <div className={styles.item}>
          <span
            className={`${styles.dot} ${
              status?.opera_available ? styles.dotGood : styles.dotUnknown
            }`}
          />
          <span>OPERA: {status?.opera_available ? '✓ ready' : 'offline'}</span>
        </div>

        <div className={styles.separator} />

        <div className={styles.item}>
          <span
            className={`${styles.dot} ${
              status?.claude_api_configured ? styles.dotGood : styles.dotUnknown
            }`}
          />
          <span>Claude RAG: {status?.claude_api_configured ? '✓ connected' : 'not configured'}</span>
        </div>
      </div>

      {/* Right side: Host performance and tasks count */}
      <div className={styles.right}>
        {status && (
          <>
            <div className={styles.item}>
              <span>CPU: {status.cpu_percent.toFixed(0)}%</span>
            </div>

            <div className={styles.separator} />

            <div className={styles.item}>
              <span>RAM: {(status.memory_mb / 1024).toFixed(1)} GB</span>
            </div>

            <div className={styles.separator} />
          </>
        )}

        <button
          className={styles.tasksIndicator}
          onClick={() => setShowTasksPanel(!showTasksPanel)}
        >
          <span>Tasks: {activeTasksCount} running</span>
        </button>

        <div className={styles.separator} />

        <span>Edeon Desktop v0.1.0</span>
      </div>
    </footer>
  );
}
