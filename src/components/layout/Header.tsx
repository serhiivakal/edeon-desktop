import { useProjectStore } from '../../store/projectStore';
import { useWorkflowStore } from '../../store/workflowStore';
import { useUIStore } from '../../store/uiStore';

export function Header() {
  const activeProjectId = useProjectStore((s) => s.activeProjectId);
  const projects = useProjectStore((s) => s.projects);
  const project = projects.find((p) => p.id === activeProjectId);

  const activeView = useUIStore((s) => s.activeView);
  const activeWorkflow = useWorkflowStore((s) => s.activeWorkflow);
  const isRunning = useWorkflowStore((s) => s.isRunning);
  const stages = useWorkflowStore((s) => s.stages);

  const stagesComplete = stages.filter((s) => s.status === 'done').length;
  const totalStages = stages.length;
  const progressPercent = totalStages > 0 ? Math.round((stagesComplete / totalStages) * 100) : 0;

  return (
    <header className="header">
      {/* Logo */}
      <span className="header-logo">Edeon</span>
      <span className="header-logo-sub">Desktop</span>

      <div className="header-separator" />

      {/* Breadcrumb */}
      <span className="header-breadcrumb">{project?.name ?? 'No project'}</span>
      <span className="header-breadcrumb-sep">›</span>
      <span className="header-breadcrumb-active">
        {activeView === 'workflows'
          ? (activeWorkflow?.name ?? 'Workflows')
          : activeView.charAt(0).toUpperCase() + activeView.slice(1)
        }
      </span>

      {/* Status pill — only in workflow view */}
      {activeView === 'workflows' && (isRunning || activeWorkflow?.status === 'complete') && (
        <>
          <div className="header-status">
            <span className={`header-status-dot ${isRunning ? '' : 'complete'}`} />
            {isRunning ? 'Running' : 'Complete'}
          </div>

          <span className="header-progress-label">{progressPercent}%</span>
          <div className="header-progress-track">
            <div
              className="header-progress-fill"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </>
      )}

      {/* Controls */}
      <button className="header-btn" title="Search">⌕</button>
      <button className="header-btn-primary">Save</button>

      <div className="header-separator" />

      {/* User */}
      <div className="header-user">
        <div className="header-avatar">SV</div>
        <span className="header-username">Sergio</span>
      </div>
    </header>
  );
}
