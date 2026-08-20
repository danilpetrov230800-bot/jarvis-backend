import { useEffect, useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { StatusBar } from './components/StatusBar';
import { FirstRunWizard } from './components/FirstRunWizard';
import { HomePage } from './pages/HomePage';
import { ChatPage } from './pages/ChatPage';
import { AgentsPage } from './pages/AgentsPage';
import { SkillsPage } from './pages/SkillsPage';
import { MemoryPage } from './pages/MemoryPage';
import { ToolsPage } from './pages/ToolsPage';
import { TasksPage } from './pages/TasksPage';
import { ResearchPage } from './pages/ResearchPage';
import { SettingsPage } from './pages/SettingsPage';
import { LogsPage } from './pages/LogsPage';
import { initApi, api } from './services/api';
import type { NovaStatus } from './types';
import './styles/app.css';

export type Page =
  | 'home'
  | 'chat'
  | 'agents'
  | 'skills'
  | 'memory'
  | 'tools'
  | 'tasks'
  | 'research'
  | 'settings'
  | 'logs';

export default function App() {
  const [ready, setReady] = useState(false);
  const [page, setPage] = useState<Page>('home');
  const [status, setStatus] = useState<NovaStatus | null>(null);
  const [settings, setSettings] = useState<Record<string, unknown>>({});
  const [showWizard, setShowWizard] = useState(false);

  useEffect(() => {
    initApi().then(async () => {
      try {
        const [s, cfg] = await Promise.all([api.getStatus(), api.getSettings()]);
        setStatus(s);
        setSettings(cfg);
        if (!cfg.first_run_complete) setShowWizard(true);
      } catch {
        setTimeout(() => initApi().then(() => setReady(true)), 2000);
      }
      setReady(true);
    });

    const interval = setInterval(async () => {
      try {
        const s = await api.getStatus();
        setStatus(s);
      } catch { /* backend reconnecting */ }
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  const refreshSettings = async () => {
    const cfg = await api.getSettings();
    setSettings(cfg);
  };

  if (!ready) {
    return (
      <div className="loading-screen">
        <div className="nova-logo">NOVA</div>
        <p>Запуск...</p>
      </div>
    );
  }

  const renderPage = () => {
    switch (page) {
      case 'home': return <HomePage status={status} onNavigate={setPage} />;
      case 'chat': return <ChatPage />;
      case 'agents': return <AgentsPage />;
      case 'skills': return <SkillsPage />;
      case 'memory': return <MemoryPage />;
      case 'tools': return <ToolsPage />;
      case 'tasks': return <TasksPage />;
      case 'research': return <ResearchPage />;
      case 'settings': return <SettingsPage settings={settings} onUpdate={refreshSettings} />;
      case 'logs': return <LogsPage />;
      default: return <HomePage status={status} onNavigate={setPage} />;
    }
  };

  return (
    <div className="app" data-theme={settings.theme === 'light' ? 'light' : 'dark'}>
      <Sidebar current={page} onNavigate={setPage} />
      <main className="main-content">
        <StatusBar status={status} />
        <div className="page-container">{renderPage()}</div>
      </main>
      {showWizard && (
        <FirstRunWizard
          onComplete={async () => {
            await api.updateSettings({ first_run_complete: true });
            setShowWizard(false);
            refreshSettings();
          }}
        />
      )}
    </div>
  );
}
