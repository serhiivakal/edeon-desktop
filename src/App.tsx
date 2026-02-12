import './styles/global.css';
import './styles/layout.css';
import './styles/components.css';

import { Header } from './components/layout/Header';
import { Sidebar } from './components/layout/Sidebar';
import { Inspector } from './components/layout/Inspector';
import { StatusBar } from './components/layout/StatusBar';

import { WorkflowView } from './views/WorkflowView';
import { LibraryView } from './views/LibraryView';
import { KnowledgeView } from './views/KnowledgeView';
import { ModelsView } from './views/ModelsView';
import { ReportsView } from './views/ReportsView';
import { SettingsView } from './views/SettingsView';
import { DockingWorkbenchView } from './views/DockingWorkbenchView';
import { FateView } from './views/FateView';
import { GenerationWorkbenchView } from './views/GenerationWorkbenchView';
import { VerificationReportView } from './views/VerificationReportView';
import { JournalView } from './views/JournalView';


import { useUIStore } from './store/uiStore';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';


// Shell overlays & provider
import { ThemeProvider } from './shell/ThemeProvider';
import { OnboardingTour } from './shell/OnboardingTour';
import { CommandPalette } from './shell/CommandPalette';
import { AboutModal } from './shell/AboutModal';
import { BackgroundTasksPanel } from './shell/BackgroundTasksPanel';
import { KeyboardShortcutsOverlay } from './shell/KeyboardShortcutsOverlay';

function MainContent() {
  const activeView = useUIStore((s) => s.activeView);

  switch (activeView) {
    case 'workflows':
      return <WorkflowView />;
    case 'library':
      return <LibraryView />;
    case 'knowledge':
      return <KnowledgeView />;
    case 'models':
      return <ModelsView />;
    case 'reports':
      return <ReportsView />;
    case 'settings':
      return <SettingsView />;
    case 'viewer3d':
      return <DockingWorkbenchView />;
    case 'fate':
      return <FateView />;
    case 'generation':
      return <GenerationWorkbenchView />;
    case 'verification_report':
      return <VerificationReportView />;
    case 'journal':
      return <JournalView />;
    default:
      return <WorkflowView />;
  }
}

export default function App() {
  // Mount the global keyboard shortcuts hook
  useKeyboardShortcuts();

  const activeView = useUIStore((s) => s.activeView);

  return (
    <ThemeProvider>
      <div className={`app-shell${activeView === 'settings' || activeView === 'viewer3d' || activeView === 'verification_report' ? ' no-inspector' : ''}`}>
        <Header />
        <Sidebar />
        <MainContent />
        {activeView !== 'settings' && activeView !== 'viewer3d' && activeView !== 'verification_report' && <Inspector />}
        <StatusBar />

        {/* Global Overlays */}
        <OnboardingTour />
        <CommandPalette />
        <AboutModal />
        <BackgroundTasksPanel />
        <KeyboardShortcutsOverlay />
      </div>
    </ThemeProvider>
  );
}


