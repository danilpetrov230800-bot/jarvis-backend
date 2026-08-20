import { useEffect, useState } from 'react';
import { Plus, Play, Trash2, TestTube } from 'lucide-react';
import { api } from '../services/api';
import type { Skill } from '../types';

export function SkillsPage() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [showBuilder, setShowBuilder] = useState(false);
  const [form, setForm] = useState({
    name: '',
    trigger: '',
    description: '',
    actions: [{ type: 'message', text: '' }] as Array<Record<string, unknown>>,
  });

  const load = () => api.getSkills().then(setSkills).catch(() => {});
  useEffect(() => { load(); }, []);

  const create = async () => {
    if (!form.name || !form.trigger) return;
    await api.createSkill(form);
    setShowBuilder(false);
    setForm({ name: '', trigger: '', description: '', actions: [{ type: 'message', text: '' }] });
    load();
  };

  const execute = async (id: number) => {
    const res = await api.executeSkill(id);
    alert(JSON.stringify(res, null, 2));
  };

  const remove = async (id: number) => {
    await api.deleteSkill(id);
    load();
  };

  const addAction = () => {
    setForm({
      ...form,
      actions: [...form.actions, { type: 'tool', tool: 'system_info', params: {} }],
    });
  };

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1>Skills</h1>
          <p>Автоматизация и обучаемые команды</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowBuilder(true)}>
          <Plus size={18} /> Skill Builder
        </button>
      </div>

      <div className="card">
        {skills.length === 0 ? (
          <div className="empty-state">
            <h3>Нет Skills</h3>
            <p>Скажите «Нова, запомни...» или создайте Skill вручную</p>
          </div>
        ) : (
          skills.map((s) => (
            <div key={s.id} className="list-item">
              <div>
                <strong>{s.name}</strong>
                <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                  Trigger: «{s.trigger}» · {s.actions.length} actions
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn btn-secondary" onClick={() => execute(s.id)} title="Test">
                  <Play size={16} />
                </button>
                <button className="btn btn-danger" onClick={() => remove(s.id)}>
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {showBuilder && (
        <div className="modal-overlay" onClick={() => setShowBuilder(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 640 }}>
            <h2>Skill Builder</h2>
            <div className="skill-builder">
              <div className="form-group">
                <label>Название</label>
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              </div>
              <div className="form-group">
                <label>Trigger (фраза активации)</label>
                <input value={form.trigger} onChange={(e) => setForm({ ...form, trigger: e.target.value })} placeholder="режим работы" />
              </div>
              <div className="form-group">
                <label>Описание</label>
                <textarea rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
              </div>
              <div>
                <label style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Actions</label>
                {form.actions.map((action, i) => (
                  <div key={i} className="action-item">
                    <span className="drag-handle">⠿</span>
                    <select
                      value={action.type as string}
                      onChange={(e) => {
                        const actions = [...form.actions];
                        actions[i] = { type: e.target.value };
                        setForm({ ...form, actions });
                      }}
                    >
                      <option value="message">Message</option>
                      <option value="tool">Tool</option>
                      <option value="delay">Delay</option>
                    </select>
                    {action.type === 'message' && (
                      <input
                        style={{ flex: 1 }}
                        placeholder="Текст сообщения"
                        value={(action.text as string) || ''}
                        onChange={(e) => {
                          const actions = [...form.actions];
                          actions[i] = { ...action, text: e.target.value };
                          setForm({ ...form, actions });
                        }}
                      />
                    )}
                    {action.type === 'tool' && (
                      <select
                        value={(action.tool as string) || 'system_info'}
                        onChange={(e) => {
                          const actions = [...form.actions];
                          actions[i] = { type: 'tool', tool: e.target.value, params: {} };
                          setForm({ ...form, actions });
                        }}
                      >
                        <option value="system_info">System Info</option>
                        <option value="launch_app">Launch App</option>
                        <option value="file_search">File Search</option>
                        <option value="calculator">Calculator</option>
                      </select>
                    )}
                    {action.type === 'delay' && (
                      <input
                        type="number"
                        placeholder="Seconds"
                        value={(action.seconds as number) || 1}
                        onChange={(e) => {
                          const actions = [...form.actions];
                          actions[i] = { type: 'delay', seconds: parseInt(e.target.value) };
                          setForm({ ...form, actions });
                        }}
                      />
                    )}
                  </div>
                ))}
                <button className="btn btn-secondary" onClick={addAction} style={{ marginTop: 8 }}>
                  + Добавить действие
                </button>
              </div>
            </div>
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setShowBuilder(false)}>Отмена</button>
              <button className="btn btn-primary" onClick={create}>Сохранить Skill</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
