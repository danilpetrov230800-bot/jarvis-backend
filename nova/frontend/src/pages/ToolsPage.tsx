import { useEffect, useState } from 'react';
import { Play } from 'lucide-react';
import { api } from '../services/api';

export function ToolsPage() {
  const [tools, setTools] = useState<Array<{ name: string; description: string; dangerous?: boolean }>>([]);
  const [result, setResult] = useState('');

  useEffect(() => {
    api.getTools().then(setTools).catch(() => {});
  }, []);

  const run = async (name: string) => {
    setResult('');
    const params: Record<string, unknown> = {};
    if (name === 'calculator') params.expression = '2+2';
    if (name === 'system_info') {}
    if (name === 'disk_info') {}
    const res = await api.executeTool(name, params);
    setResult(JSON.stringify(res, null, 2));
  };

  return (
    <div>
      <div className="page-header">
        <h1>Tools</h1>
        <p>Локальные инструменты NOVA</p>
      </div>

      <div className="grid-2">
        {tools.map((t) => (
          <div key={t.name} className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <strong>{t.name}</strong>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
                {t.description}
              </div>
            </div>
            <button className="btn btn-secondary" onClick={() => run(t.name)}>
              <Play size={16} />
            </button>
          </div>
        ))}
      </div>

      {result && (
        <div className="card" style={{ marginTop: 24 }}>
          <h3 style={{ marginBottom: 12 }}>Результат</h3>
          <pre style={{ fontSize: 13, whiteSpace: 'pre-wrap', color: 'var(--text-secondary)' }}>{result}</pre>
        </div>
      )}
    </div>
  );
}
