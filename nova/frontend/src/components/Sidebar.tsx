import {
  Home, MessageSquare, Bot, Sparkles, Brain, Wrench,
  ListTodo, Search, Settings, FileText,
} from 'lucide-react';
import type { Page } from '../App';

const NAV_ITEMS: { id: Page; label: string; icon: typeof Home }[] = [
  { id: 'home', label: 'Home', icon: Home },
  { id: 'chat', label: 'Chat', icon: MessageSquare },
  { id: 'agents', label: 'Agents', icon: Bot },
  { id: 'skills', label: 'Skills', icon: Sparkles },
  { id: 'memory', label: 'Memory', icon: Brain },
  { id: 'tools', label: 'Tools', icon: Wrench },
  { id: 'tasks', label: 'Tasks', icon: ListTodo },
  { id: 'research', label: 'Research', icon: Search },
  { id: 'settings', label: 'Settings', icon: Settings },
  { id: 'logs', label: 'Logs', icon: FileText },
];

interface Props {
  current: Page;
  onNavigate: (page: Page) => void;
}

export function Sidebar({ current, onNavigate }: Props) {
  return (
    <nav className="sidebar">
      <div className="sidebar-logo">NOVA</div>
      <ul className="sidebar-nav">
        {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
          <li key={id}>
            <button
              className={`sidebar-item ${current === id ? 'active' : ''}`}
              onClick={() => onNavigate(id)}
            >
              <Icon size={18} />
              <span>{label}</span>
            </button>
          </li>
        ))}
      </ul>
      <div className="sidebar-footer">
        <span className="version">v1.0.0</span>
      </div>
    </nav>
  );
}
