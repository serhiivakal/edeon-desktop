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

import { useUIStore } from './store/uiStore';

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
    default:
      return <WorkflowView />;
  }
}

export default function App() {
  return (
    <div className="app-shell">
      <Header />
      <Sidebar />
      <MainContent />
      <Inspector />
      <StatusBar />
    </div>
  );
}
