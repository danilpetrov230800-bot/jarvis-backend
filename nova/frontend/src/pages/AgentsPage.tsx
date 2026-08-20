import { useEffect, useState } from 'react';
import { Plus, Play, Trash2 } from 'lucide-react';
import { api } from '../services/api';
import type { Agent } from '../types';

export function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [taskInput, setTaskInput] = useState('');
  const [result, setResult] = useState('');
  const [running, setRunning] = useState(false);
  const [form, setForm] = useState({ name: '', role: '', instructions: '', model: 'local' });

  const load = () => api.getAgents().then(setAgents).catch(() => {});
  useEffect(() => { load(); }, []);

  const create = async () => {
    if (!form.name || !form.role) return;
    await api.createAgent(form);
    setShowCreate(false);
    setForm({ name: '', role: '', instructions: '', model: 'local' });
    load();
  };

  const runTask = async () => {
    if (!taskInput.trim()) return;
    setRunning(true);
    setResult('');
    try {
      const res = await api.runAgentTask(taskInput) as { summary?: string; error?: string };
      setResult(res.summary || res.error || 'Задача выполнена');
    } catch {
      setResult('Не удалось выполнить задачу');
    } finally {
      setRunning(false);
    }
  };

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1>Agents</h1>
          <p>Специализированные AI-агенты</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
          <Plus size={18} /> Создать агента
        </button>
      </div>

      <div className="card" style={{ marginBottom: 24 }}>
        <h3 style={{ marginBottom: 12 }}>Agent Mode</h3>
        <div className="form-row">
          <input
            style={{ flex: 1 }}
            value={taskInput}
            onChange={(e) => setTaskInput(e.target.value)}
            placeholder="Поставьте задачу агенту..."
          />
          <button className="btn btn-primary" onClick={runTask} disabled={running}>
            <Play size={18} /> {running ? 'Выполняю...' : 'Запустить'}
          </button>
        </div>
        {result && (
          <div style={{ marginTop: 16, padding: 16, background: 'var(--bg-tertiary)', borderRadius: 8 }}>
            {result}
          </div>
        )}
      </div>

      <div className="card">
        {agents.length === 0 ? (
          <div className="empty-state"><h3>Нет агентов</h3></div>
        ) : (
          agents.map((a) => (
            <div key={a.id} className="list-item">
              <div>
                <strong>{a.name}</strong>
                <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                  {a.role} · {a.model} · {a.enabled ? 'Active' : 'Disabled'}
                </div>
              </div>
              <span className={`badge ${a.enabled ? 'badge-success' : 'badge-warning'}`}>
                {a.enabled ? 'ON' : 'OFF'}
              </span>
            </div>
          ))
        )}
      </div>

      {showCreate && (
        <div className="modal-overlay" onClick={() => setShowCreate(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Новый агент</h2>
            <div className="form-group">
              <label>Имя</label>
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Роль</label>
              <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                <option value="">Выберите...</option>
                <option value="research">Research</option>
                <option value="file">File</option>
                <option value="system">System</option>
                <option value="coding">Coding</option>
                <option value="creative">Creative</option>
                <option value="automation">Automation</option>
              </select>
            </div>
            <div className="form-group">
              <label>Инструкции</label>
              <textarea rows={3} value={form.instructions} onChange={(e) => setForm({ ...form, instructions: e.target.value })} />
            </div>
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setShowCreate(false)}>Отмена</button>
              <button className="btn btn-primary" onClick={create}>Создать</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
