import { useEffect } from 'react';
import { useWorkflowStore } from '../../store/workflowStore';

export function StatusBar() {
  const pythonReady = useWorkflowStore((s) => s.pythonReady);
  const isRunning = useWorkflowStore((s) => s.isRunning);
  const stages = useWorkflowStore((s) => s.stages);
  const checkPython = useWorkflowStore((s) => s.checkPython);

  useEffect(() => {
    checkPython();
  }, [checkPython]);

  const runningStage = stages.find((s) => s.status === 'running');

  return (
    <footer className="statusbar">
      <div className="statusbar-item">
        <span className={`statusbar-dot ${isRunning ? '' : 'idle'}`} />
        {isRunning && runningStage
          ? `${runningStage.name} · processing...`
          : 'Idle'
        }
      </div>
      <span>
        Python: {pythonReady ? '✓ ready' : '✗ not available'}
      </span>
      <span>Queue: {isRunning ? '1 active' : '0 active'}</span>
      <span style={{ marginLeft: 'auto' }}>
        Edeon Desktop v0.1.0
      </span>
    </footer>
  );
}
