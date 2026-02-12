import { useState, useRef, useEffect } from 'react';
import { useUIStore } from '../../store/uiStore';
import { useProjectStore } from '../../store/projectStore';
import { useWorkflowStore } from '../../store/workflowStore';
import { useTourStore } from '../../store/tourStore';
import { useHotkeys } from 'react-hotkeys-hook';
import { Search, Bell, HelpCircle, Sun, Moon } from 'lucide-react';
import styles from './Header.module.css';

export function Header() {
  const activeProjectId = useProjectStore((s) => s.activeProjectId);
  const projects = useProjectStore((s) => s.projects);
  const setActiveProject = useProjectStore((s) => s.setActiveProject);
  const project = projects.find((p) => p.id === activeProjectId);

  const theme = useUIStore((s) => s.theme);
  const toggleTheme = useUIStore((s) => s.toggleTheme);
  const isRunning = useWorkflowStore((s) => s.isRunning);

  const setShowAboutModal = useUIStore((s) => s.setShowAboutModal);
  const setShowTasksPanel = useUIStore((s) => s.setShowTasksPanel);
  const showTasksPanel = useUIStore((s) => s.showTasksPanel);
  const startTour = useTourStore((s) => s.startTour);

  const [projectOpen, setProjectOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [userOpen, setUserOpen] = useState(false);

  const searchInputRef = useRef<HTMLInputElement>(null);

  // Trigger search focus on Cmd+/ or Ctrl+/
  useHotkeys('mod+/', (e) => {
    e.preventDefault();
    if (searchInputRef.current) {
      searchInputRef.current.focus();
    }
  });

  // Close menus on click outside
  useEffect(() => {
    const handler = () => {
      setProjectOpen(false);
      setHelpOpen(false);
      setUserOpen(false);
    };
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, []);

  return (
    <header className={`${styles.header} header`}>
      {/* Left side: Logo & Project Switcher */}
      <div className={styles.left}>
        <div className={styles.logoContainer} onClick={() => setShowAboutModal(true)}>
          <span className={styles.logoText}>Edeon</span>
          <span className={styles.logoSubtext}>Desktop</span>
        </div>

        <div className={styles.dropdownContainer} onClick={(e) => e.stopPropagation()}>
          <button
            className={styles.dropdownTrigger}
            onClick={() => setProjectOpen(!projectOpen)}
          >
            <span>📁 {project?.name ?? 'Select Project'}</span>
            <span>▾</span>
          </button>
          
          {projectOpen && (
            <div className={styles.dropdownMenu}>
              {projects.map((p) => (
                <button
                  key={p.id}
                  className={`${styles.dropdownItem} ${
                    p.id === activeProjectId ? styles.dropdownItemActive : ''
                  }`}
                  onClick={() => {
                    setActiveProject(p.id);
                    setProjectOpen(false);
                  }}
                >
                  {p.name}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Center: Global search input (focus triggers Command Palette command list or helps navigate) */}
      <div className={styles.center} onClick={(e) => e.stopPropagation()}>
        <Search size={14} className={styles.searchIcon} />
        <input
          ref={searchInputRef}
          type="text"
          placeholder="Press Cmd+/ to search settings, models, workflows..."
          className={styles.searchInput}
          onFocus={(e) => {
            // Unfocus input and trigger global Cmd+K command palette popup
            e.target.blur();
            const event = new KeyboardEvent('keydown', {
              key: 'k',
              metaKey: true,
              ctrlKey: true,
              bubbles: true,
            });
            document.dispatchEvent(event);
          }}
        />
      </div>

      {/* Right side: Operations panel, help, theme toggles, and user avatar */}
      <div className={styles.right} onClick={(e) => e.stopPropagation()}>
        {/* Background tasks notifier bell */}
        <button
          className={styles.headerBtn}
          title="Background active tasks"
          onClick={() => setShowTasksPanel(!showTasksPanel)}
        >
          <Bell size={16} />
          {isRunning && <span className={styles.badge} />}
        </button>

        {/* Help Menu Dropdown */}
        <div className={styles.dropdownContainer}>
          <button
            className={styles.headerBtn}
            title="Help & Guides"
            onClick={() => setHelpOpen(!helpOpen)}
          >
            <HelpCircle size={16} />
          </button>
          
          {helpOpen && (
            <div className={styles.dropdownMenu} style={{ left: 'auto', right: 0 }}>
              <button
                className={styles.dropdownItem}
                onClick={() => {
                  startTour();
                  setHelpOpen(false);
                }}
              >
                Show guided tour
              </button>
              <button
                className={styles.dropdownItem}
                onClick={() => {
                  setShowAboutModal(true);
                  setHelpOpen(false);
                }}
              >
                About Edeon
              </button>
              <button
                className={styles.dropdownItem}
                onClick={() => {
                  window.open('https://edeon-agchem.org/docs', '_blank');
                  setHelpOpen(false);
                }}
              >
                Documentation
              </button>
            </div>
          )}
        </div>

        {/* Theme Toggle Button */}
        <button
          className={styles.themeToggle}
          onClick={toggleTheme}
          title="Toggle Light/Dark Theme"
        >
          {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
        </button>

        {/* User profile dropdown */}
        <div className={styles.dropdownContainer}>
          <div
            className={styles.userContainer}
            onClick={() => setUserOpen(!userOpen)}
            style={{ cursor: 'pointer' }}
          >
            <div className={styles.avatar}>SV</div>
            <span className={styles.username}>Sergio</span>
          </div>

          {userOpen && (
            <div className={styles.dropdownMenu} style={{ left: 'auto', right: 0 }}>
              <div className={styles.dropdownItem} style={{ borderBottom: '1px solid var(--color-border-subtle)', borderRadius: 0, cursor: 'default' }}>
                Sergio Vakal
              </div>
              <button
                className={styles.dropdownItem}
                onClick={() => {
                  window.open('https://edeon-agchem.org/profile', '_blank');
                  setUserOpen(false);
                }}
              >
                User Profile
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
