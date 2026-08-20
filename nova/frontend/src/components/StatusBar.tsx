import type { NovaStatus } from '../types';
import '../styles/sidebar.css';

interface Props {
  status: NovaStatus | null;
}

export function StatusBar({ status }: Props) {
  const dotClass = status?.offline
    ? 'offline'
    : status?.status === 'processing' || status?.status === 'agent_running'
    ? 'processing'
    : status?.status === 'error'
    ? 'error'
    : '';

  const statusLabel: Record<string, string> = {
    idle: 'Готова',
    listening: 'Слушаю...',
    processing: 'Думаю...',
    speaking: 'Говорю...',
    agent_running: 'Агент работает',
    offline: 'Offline mode',
    error: 'Ошибка',
  };

  return (
    <div className="status-bar">
      <div className="status-left">
        <div className="status-indicator">
          <span className={`status-dot ${dotClass}`} />
          <span>{statusLabel[status?.status || 'idle'] || 'Готова'}</span>
        </div>
        {status?.wake_word_active && (
          <span className="badge badge-info">Wake word</span>
        )}
        {status?.offline && (
          <span className="badge badge-warning">Offline</span>
        )}
        {status?.active_agent && (
          <span className="badge badge-info">{status.active_agent.status}</span>
        )}
      </div>
      <div className="status-right">
        {status?.current_task && <span>{status.current_task}</span>}
      </div>
    </div>
  );
}
