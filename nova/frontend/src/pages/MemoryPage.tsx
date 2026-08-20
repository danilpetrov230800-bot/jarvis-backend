import { useEffect, useState } from 'react';
import { Plus, Trash2, Search } from 'lucide-react';
import { api } from '../services/api';
import type { MemoryItem } from '../types';

export function MemoryPage() {
  const [items, setItems] = useState<MemoryItem[]>([]);
  const [query, setQuery] = useState('');
  const [showAdd, setShowAdd] = useState(false);
  const [newContent, setNewContent] = useState('');
  const [newType, setNewType] = useState('long-term');

  const load = () => api.getMemory().then(setItems).catch(() => {});
  useEffect(() => { load(); }, []);

  const search = async () => {
    if (!query.trim()) { load(); return; }
    const results = await api.searchMemory(query);
    setItems(results as MemoryItem[]);
  };

  const add = async () => {
    if (!newContent.trim()) return;
    await api.createMemory({ content: newContent, type: newType });
    setNewContent('');
    setShowAdd(false);
    load();
  };

  const remove = async (id: number) => {
    await api.deleteMemory(id);
    load();
  };

  const typeLabels: Record<string, string> = {
    'short-term': 'Short-term',
    'long-term': 'Long-term',
    preferences: 'Preferences',
    episodic: 'Episodic',
    semantic: 'Semantic',
    skill: 'Skill',
  };

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1>Memory</h1>
          <p>Память NOVA</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowAdd(true)}>
          <Plus size={18} /> Добавить
        </button>
      </div>

      <div className="form-row" style={{ marginBottom: 24 }}>
        <input
          style={{ flex: 1 }}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Поиск в памяти..."
          onKeyDown={(e) => e.key === 'Enter' && search()}
        />
        <button className="btn btn-secondary" onClick={search}>
          <Search size={18} /> Найти
        </button>
      </div>

      <div className="card">
        {items.length === 0 ? (
          <div className="empty-state">
            <h3>Память пуста</h3>
            <p>Скажите «Нова, запомни, что...»</p>
          </div>
        ) : (
          items.map((m) => (
            <div key={m.id} className="list-item">
              <div>
                <span className="badge badge-info" style={{ marginRight: 8 }}>
                  {typeLabels[m.type] || m.type}
                </span>
                <strong>{m.content}</strong>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                  {m.category} · importance: {m.importance}
                </div>
              </div>
              <button className="btn btn-danger" onClick={() => remove(m.id)}>
                <Trash2 size={16} />
              </button>
            </div>
          ))
        )}
      </div>

      {showAdd && (
        <div className="modal-overlay" onClick={() => setShowAdd(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Добавить в память</h2>
            <div className="form-group">
              <label>Тип</label>
              <select value={newType} onChange={(e) => setNewType(e.target.value)}>
                {Object.entries(typeLabels).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label>Содержание</label>
              <textarea rows={4} value={newContent} onChange={(e) => setNewContent(e.target.value)} />
            </div>
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setShowAdd(false)}>Отмена</button>
              <button className="btn btn-primary" onClick={add}>Сохранить</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
