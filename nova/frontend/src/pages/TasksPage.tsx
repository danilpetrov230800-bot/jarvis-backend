import { useEffect, useState } from 'react';
import { Plus } from 'lucide-react';
import { api } from '../services/api';
import type { Task } from '../types';

export function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [title, setTitle] = useState('');

  const load = () => api.getTasks().then(setTasks).catch(() => {});
  useEffect(() => { load(); }, []);

  const create = async () => {
    if (!title.trim()) return;
    await api.createTask({ title, type: 'one-time' });
    setTitle('');
    load();
  };

  const statusBadge = (s: string) => {
    const map: Record<string, string> = {
      pending: 'badge-warning',
      running: 'badge-info',
      completed: 'badge-success',
      cancelled: 'badge-error',
    };
    return map[s] || 'badge-info';
  };

  return (
    <div>
      <div className="page-header">
        <h1>Tasks</h1>
        <p>Менеджер задач</p>
      </div>

      <div className="form-row" style={{ marginBottom: 24 }}>
        <input
          style={{ flex: 1 }}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Новая задача..."
          onKeyDown={(e) => e.key === 'Enter' && create()}
        />
        <button className="btn btn-primary" onClick={create}>
          <Plus size={18} /> Добавить
        </button>
      </div>

      <div className="card">
        {tasks.length === 0 ? (
          <div className="empty-state"><h3>Нет задач</h3></div>
        ) : (
          tasks.map((t) => (
            <div key={t.id} className="list-item">
              <div>
                <strong>{t.title}</strong>
                <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                  {t.type} · {t.schedule || 'no schedule'}
                </div>
              </div>
              <span className={`badge ${statusBadge(t.status)}`}>{t.status}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
