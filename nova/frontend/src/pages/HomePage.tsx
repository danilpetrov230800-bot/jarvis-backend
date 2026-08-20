import { useState } from 'react';
import { Mic, MessageSquare, Sparkles, Settings } from 'lucide-react';
import type { NovaStatus } from '../types';
import type { Page } from '../App';

interface Props {
  status: NovaStatus | null;
  onNavigate: (page: Page) => void;
}

export function HomePage({ status, onNavigate }: Props) {
  return (
    <div>
      <div className="home-hero">
        <h1>NOVA</h1>
        <p>
          Neural Operational & Virtual Assistant — ваш персональный AI-ассистент.
          Скажите «Нова» или начните печатать.
        </p>
        <div className="quick-actions">
          <button className="btn btn-primary" onClick={() => onNavigate('chat')}>
            <MessageSquare size={18} /> Начать диалог
          </button>
          <button className="btn btn-secondary" onClick={() => onNavigate('skills')}>
            <Sparkles size={18} /> Skills
          </button>
          <button className="btn btn-secondary" onClick={() => onNavigate('settings')}>
            <Settings size={18} /> Настройки
          </button>
        </div>
      </div>

      <div className="grid-3">
        <div className="card stat-card">
          <div className="value">{status?.status === 'idle' ? '✓' : '…'}</div>
          <div className="label">Статус</div>
        </div>
        <div className="card stat-card">
          <div className="value">{status?.wake_word_active ? '🎤' : '—'}</div>
          <div className="label">Wake Word</div>
        </div>
        <div className="card stat-card">
          <div className="value">{status?.offline ? 'Offline' : 'Online'}</div>
          <div className="label">Сеть</div>
        </div>
      </div>

      {status?.active_agent && (
        <div className="card agent-progress" style={{ marginTop: 24 }}>
          <h3>Agent: {status.active_agent.title}</h3>
          {status.active_agent.steps.map((step, i) => (
            <div
              key={i}
              className={`agent-step ${i === status.active_agent!.current_step ? 'active' : i < status.active_agent!.current_step ? 'done' : ''}`}
            >
              {step.status}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
