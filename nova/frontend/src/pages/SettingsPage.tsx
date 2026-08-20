import { useEffect, useState } from 'react';
import { api } from '../services/api';
import type { Permission } from '../types';

interface Props {
  settings: Record<string, unknown>;
  onUpdate: () => void;
}

export function SettingsPage({ settings, onUpdate }: Props) {
  const [local, setLocal] = useState(settings);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [apiKey, setApiKey] = useState('');
  const [diagResult, setDiagResult] = useState<{ overall: string; checks: Array<{ name: string; status: string; message: string }> } | null>(null);
  const [voiceTest, setVoiceTest] = useState('');

  useEffect(() => { setLocal(settings); }, [settings]);
  useEffect(() => { api.getPermissions().then(setPermissions).catch(() => {}); }, []);

  const save = async (patch: Record<string, unknown>) => {
    const updated = { ...local, ...patch };
    setLocal(updated);
    await api.updateSettings(patch);
    onUpdate();
  };

  const saveApiKey = async () => {
    if (apiKey) {
      await api.setSecret('openai_api_key', apiKey);
      setApiKey('');
    }
  };

  const togglePermission = async (name: string, enabled: boolean) => {
    await api.setPermission(name, enabled);
    setPermissions((prev) => prev.map((p) => (p.name === name ? { ...p, enabled } : p)));
  };

  const runDiagnostics = async () => {
    const res = await api.runDiagnostics();
    setDiagResult(res);
  };

  const testVoice = async (type: 'mic' | 'tts') => {
    const res = type === 'mic' ? await api.testMicrophone() : await api.testTts();
    setVoiceTest(JSON.stringify(res));
  };

  const createBackup = async () => {
    const res = await api.createBackup();
    alert(`Backup создан: ${res.path}`);
  };

  return (
    <div>
      <div className="page-header">
        <h1>Settings</h1>
        <p>Настройки NOVA</p>
      </div>

      <div className="settings-section">
        <h2>General</h2>
        <div className="card">
          <div className="list-item">
            <span>Тема</span>
            <select
              value={(local.theme as string) || 'dark'}
              onChange={(e) => save({ theme: e.target.value })}
            >
              <option value="dark">Dark</option>
              <option value="light">Light</option>
            </select>
          </div>
          <div className="list-item">
            <span>Язык</span>
            <select value={(local.language as string) || 'ru'} onChange={(e) => save({ language: e.target.value })}>
              <option value="ru">Русский</option>
              <option value="en">English</option>
            </select>
          </div>
        </div>
      </div>

      <div className="settings-section">
        <h2>AI</h2>
        <div className="card">
          <div className="list-item">
            <span>Provider</span>
            <select
              value={(local.ai_provider as string) || 'local'}
              onChange={(e) => save({ ai_provider: e.target.value })}
            >
              <option value="local">Local</option>
              <option value="openai">OpenAI</option>
              <option value="ollama">Ollama</option>
              <option value="compatible">Compatible API</option>
            </select>
          </div>
          <div className="list-item">
            <span>Model</span>
            <input
              value={(local.ai_model as string) || ''}
              onChange={(e) => save({ ai_model: e.target.value })}
              style={{ width: 200 }}
            />
          </div>
          <div className="form-group" style={{ padding: '0 16px 16px' }}>
            <label>OpenAI API Key</label>
            <div className="form-row">
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="sk-..."
                style={{ flex: 1 }}
              />
              <button className="btn btn-primary" onClick={saveApiKey}>Сохранить</button>
            </div>
          </div>
        </div>
      </div>

      <div className="settings-section">
        <h2>Voice</h2>
        <div className="card">
          <div className="list-item">
            <span>Wake Word</span>
            <div
              className={`toggle ${local.wake_word_enabled ? 'active' : ''}`}
              onClick={() => save({ wake_word_enabled: !local.wake_word_enabled })}
            />
          </div>
          <div className="list-item">
            <span>Чувствительность</span>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={(local.wake_word_sensitivity as number) || 0.5}
              onChange={(e) => save({ wake_word_sensitivity: parseFloat(e.target.value) })}
              style={{ width: 150 }}
            />
          </div>
          <div className="list-item">
            <span>TTS Rate</span>
            <input
              type="number"
              value={(local.tts_rate as number) || 180}
              onChange={(e) => save({ tts_rate: parseInt(e.target.value) })}
              style={{ width: 80 }}
            />
          </div>
          <div style={{ padding: 16, display: 'flex', gap: 8 }}>
            <button className="btn btn-secondary" onClick={() => testVoice('mic')}>Тест микрофона</button>
            <button className="btn btn-secondary" onClick={() => testVoice('tts')}>Тест голоса</button>
          </div>
          {voiceTest && <pre style={{ padding: 16, fontSize: 12 }}>{voiceTest}</pre>}
        </div>
      </div>

      <div className="settings-section">
        <h2>Permissions</h2>
        <div className="card">
          {permissions.map((p) => (
            <div key={p.name} className="list-item">
              <div>
                <strong>{p.name}</strong>
                {p.dangerous && <span className="badge badge-error" style={{ marginLeft: 8 }}>Dangerous</span>}
              </div>
              <div
                className={`toggle ${p.enabled ? 'active' : ''}`}
                onClick={() => togglePermission(p.name, !p.enabled)}
              />
            </div>
          ))}
        </div>
      </div>

      <div className="settings-section">
        <h2>Research</h2>
        <div className="card">
          <div className="list-item">
            <span>Research Mode</span>
            <div
              className={`toggle ${local.research_mode_enabled ? 'active' : ''}`}
              onClick={() => save({ research_mode_enabled: !local.research_mode_enabled })}
            />
          </div>
        </div>
      </div>

      <div className="settings-section">
        <h2>Storage & Backup</h2>
        <div className="card">
          <div style={{ padding: 16 }}>
            <button className="btn btn-primary" onClick={createBackup}>Создать Backup</button>
          </div>
        </div>
      </div>

      <div className="settings-section">
        <h2>Diagnostics</h2>
        <div className="card">
          <div style={{ padding: 16 }}>
            <button className="btn btn-primary" onClick={runDiagnostics}>Проверить NOVA</button>
          </div>
          {diagResult && (
            <div>
              <div className="list-item">
                <strong>Overall: {diagResult.overall}</strong>
              </div>
              {diagResult.checks.map((c) => (
                <div key={c.name} className="diag-result">
                  <span>{c.name}</span>
                  <span>
                    <span className={`badge badge-${c.status === 'PASS' ? 'success' : c.status === 'WARNING' ? 'warning' : 'error'}`}>
                      {c.status}
                    </span>
                    <span style={{ marginLeft: 8, fontSize: 13, color: 'var(--text-secondary)' }}>{c.message}</span>
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
