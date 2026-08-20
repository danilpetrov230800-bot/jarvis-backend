import { useState } from 'react';
import { Download } from 'lucide-react';
import { api } from '../services/api';

export function LogsPage() {
  const [logs, setLogs] = useState('');
  const [loaded, setLoaded] = useState(false);

  const load = async () => {
    const res = await api.exportLogs();
    setLogs(res.content || 'Логи пусты');
    setLoaded(true);
  };

  const download = () => {
    const blob = new Blob([logs], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `nova_logs_${new Date().toISOString().slice(0, 10)}.log`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1>Logs</h1>
          <p>Журнал событий NOVA</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-secondary" onClick={load}>Загрузить</button>
          {loaded && (
            <button className="btn btn-primary" onClick={download}>
              <Download size={18} /> Экспорт логов
            </button>
          )}
        </div>
      </div>

      <div className="card">
        {!loaded ? (
          <div className="empty-state"><p>Нажмите «Загрузить» для просмотра логов</p></div>
        ) : (
          <pre style={{ fontSize: 12, whiteSpace: 'pre-wrap', maxHeight: '70vh', overflow: 'auto', color: 'var(--text-secondary)' }}>
            {logs}
          </pre>
        )}
      </div>
    </div>
  );
}
