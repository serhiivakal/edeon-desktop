import { useEffect, useState, useRef } from 'react';
import { useUIStore } from '../../store/uiStore';
import { useProjectStore } from '../../store/projectStore';
import { mockRecentWorkflows } from '../../data/mockData';
import type { ViewId } from '../../types';

const views: { id: ViewId; label: string; badge?: number }[] = [
  { id: 'viewer3d', label: '3D Viewer' },
  { id: 'library', label: 'Library' },
  { id: 'workflows', label: 'Workflows', badge: 1 },
  { id: 'generation', label: 'De Novo Design' },
  { id: 'fate', label: 'Env Fate' },
  { id: 'knowledge', label: 'Knowledge' },
  { id: 'models', label: 'Models' },
  { id: 'journal', label: 'Decision Journal' },
  { id: 'reports', label: 'Reports' },
];

export function Sidebar() {
  const activeView = useUIStore((s) => s.activeView);
  const setActiveView = useUIStore((s) => s.setActiveView);

  const projects = useProjectStore((s) => s.projects);
  const activeProjectId = useProjectStore((s) => s.activeProjectId);
  const fetchProjects = useProjectStore((s) => s.fetchProjects);
  const createProject = useProjectStore((s) => s.createProject);
  const renameProject = useProjectStore((s) => s.renameProject);
  const deleteProject = useProjectStore((s) => s.deleteProject);
  const setActiveProject = useProjectStore((s) => s.setActiveProject);
  const loadActiveProjectId = useProjectStore((s) => s.loadActiveProjectId);

  const [isCreating, setIsCreating] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [contextMenu, setContextMenu] = useState<{
    id: string;
    x: number;
    y: number;
  } | null>(null);

  const newInputRef = useRef<HTMLInputElement>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);

  // Load projects and active project on mount
  useEffect(() => {
    fetchProjects();
    loadActiveProjectId();
  }, [fetchProjects, loadActiveProjectId]);

  // Auto-activate first project if none is active
  useEffect(() => {
    if (!activeProjectId && projects.length > 0) {
      setActiveProject(projects[0].id);
    }
  }, [activeProjectId, projects, setActiveProject]);

  // Focus new project input
  useEffect(() => {
    if (isCreating && newInputRef.current) {
      newInputRef.current.focus();
    }
  }, [isCreating]);

  // Focus rename input
  useEffect(() => {
    if (renamingId && renameInputRef.current) {
      renameInputRef.current.focus();
      renameInputRef.current.select();
    }
  }, [renamingId]);

  // Close context menu on click outside
  useEffect(() => {
    if (!contextMenu) return;
    const handler = () => setContextMenu(null);
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, [contextMenu]);

  const handleCreateProject = async () => {
    const name = newProjectName.trim();
    if (!name) {
      setIsCreating(false);
      return;
    }
    try {
      await createProject(name);
      setNewProjectName('');
      setIsCreating(false);
    } catch (e) {
      console.error('Failed to create project:', e);
    }
  };

  const handleRename = async () => {
    if (!renamingId) return;
    const name = renameValue.trim();
    if (!name) {
      setRenamingId(null);
      return;
    }
    try {
      await renameProject(renamingId, name);
      setRenamingId(null);
    } catch (e) {
      console.error('Failed to rename project:', e);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteProject(id);
    } catch (e) {
      console.error('Failed to delete project:', e);
    }
  };

  const handleContextMenu = (e: React.MouseEvent, id: string) => {
    e.preventDefault();
    setContextMenu({ id, x: e.clientX, y: e.clientY });
  };

  return (
    <aside className="sidebar">
      {/* Projects */}
      <div className="sidebar-section">
        <div className="sidebar-section-label">PROJECTS</div>
        {projects.map((project) => (
          <div
            key={project.id}
            className={`sidebar-item${project.id === activeProjectId ? ' active' : ''}`}
            onClick={() => setActiveProject(project.id)}
            onContextMenu={(e) => handleContextMenu(e, project.id)}
          >
            {renamingId === project.id ? (
              <input
                ref={renameInputRef}
                className="sidebar-inline-input"
                value={renameValue}
                onChange={(e) => setRenameValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleRename();
                  if (e.key === 'Escape') setRenamingId(null);
                }}
                onBlur={handleRename}
                onClick={(e) => e.stopPropagation()}
              />
            ) : (
              <>
                <span>
                  {project.id === activeProjectId ? '▶' : '▸'} {project.name}
                </span>
                <span className="sidebar-item-count">{project.compound_count}</span>
              </>
            )}
          </div>
        ))}

        {isCreating ? (
          <div className="sidebar-item">
            <input
              ref={newInputRef}
              className="sidebar-inline-input"
              placeholder="Project name..."
              value={newProjectName}
              onChange={(e) => setNewProjectName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleCreateProject();
                if (e.key === 'Escape') {
                  setIsCreating(false);
                  setNewProjectName('');
                }
              }}
              onBlur={handleCreateProject}
            />
          </div>
        ) : (
          <button
            className="sidebar-new-project"
            onClick={() => setIsCreating(true)}
          >
            + New project
          </button>
        )}
      </div>

      {/* Views */}
      <div className="sidebar-section">
        <div className="sidebar-section-label">VIEWS</div>
        {views.map((view) => {
          let elementId = `${view.id}-nav`;
          if (view.id === 'viewer3d') elementId = 'docking-workbench-nav';
          if (view.id === 'generation') elementId = 'generation-workbench-nav';
          if (view.id === 'knowledge') elementId = 'knowledge-hub-nav';

          return (
            <div
              key={view.id}
              id={elementId}
              className={`sidebar-item${activeView === view.id ? ' active' : ''}`}
              onClick={() => setActiveView(view.id)}
            >
              <span>{view.label}</span>
              {view.badge && (
                <span className="sidebar-badge">{view.badge}</span>
              )}
            </div>
          );
        })}
      </div>

      {/* Recent Workflows — still mock data until Phase 3 */}
      <div className="sidebar-section">
        <div className="sidebar-section-label">RECENT WORKFLOWS</div>
        {mockRecentWorkflows.map((wf) => (
          <div key={wf.name} className="sidebar-recent-item">
            <div className="sidebar-recent-name">{wf.name}</div>
            <div className="sidebar-recent-meta">{wf.meta}</div>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="sidebar-footer">
        <div
          className={`sidebar-footer-item${activeView === 'settings' ? ' active' : ''}`}
          onClick={() => setActiveView('settings')}
        >
          ⚙ Settings
        </div>
        <div className="sidebar-footer-item">Help</div>
      </div>

      {/* Context Menu */}
      {contextMenu && (
        <div
          className="context-menu"
          style={{ top: contextMenu.y, left: contextMenu.x }}
        >
          <div
            className="context-menu-item"
            onClick={(e) => {
              e.stopPropagation();
              const project = projects.find((p) => p.id === contextMenu.id);
              if (project) {
                setRenameValue(project.name);
                setRenamingId(contextMenu.id);
              }
              setContextMenu(null);
            }}
          >
            Rename
          </div>
          <div
            className="context-menu-item danger"
            onClick={(e) => {
              e.stopPropagation();
              handleDelete(contextMenu.id);
              setContextMenu(null);
            }}
          >
            Delete
          </div>
        </div>
      )}
    </aside>
  );
}
