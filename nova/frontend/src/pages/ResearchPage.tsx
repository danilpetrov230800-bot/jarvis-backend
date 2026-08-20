import { useState } from 'react';
import { Search, Shield } from 'lucide-react';
import { api } from '../services/api';

export function ResearchPage() {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState('');

  const search = async () => {
    setError('');
    setResult(null);
    try {
      const res = await api.researchSearch(query);
      setResult(res);
    } catch (e) {
      setError('Research mode требует отдельного разрешения. Включите в Settings → Research.');
    }
  };

  return (
    <div>
      <div className="page-header">
        <h1>Research</h1>
        <p>Creator Research / OSINT Mode — только открытые источники</p>
      </div>

      <div className="card" style={{ marginBottom: 24, borderColor: 'var(--warning)' }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <Shield size={24} color="var(--warning)" />
          <div>
            <strong>Только для законного исследования</strong>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
              Не обходит приватность, авторизацию, paywall или защитные механизмы.
              Требуется разрешение RESEARCH_MODE.
            </div>
          </div>
        </div>
      </div>

      <div className="form-row" style={{ marginBottom: 24 }}>
        <input
          style={{ flex: 1 }}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Поиск по открытым источникам..."
          onKeyDown={(e) => e.key === 'Enter' && search()}
        />
        <button className="btn btn-primary" onClick={search}>
          <Search size={18} /> Искать
        </button>
      </div>

      {error && (
        <div className="card" style={{ borderColor: 'var(--error)' }}>
          <p style={{ color: 'var(--error)' }}>{error}</p>
        </div>
      )}

      {result && (
        <div className="card">
          <pre style={{ fontSize: 13, whiteSpace: 'pre-wrap' }}>{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
