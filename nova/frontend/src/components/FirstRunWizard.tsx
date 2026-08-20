import { useState } from 'react';
import { api } from '../services/api';

interface Props {
  onComplete: () => void;
}

const STEPS = [
  {
    title: 'Добро пожаловать в NOVA',
    text: 'NOVA — ваш персональный AI-ассистент. Работает локально и с облачными моделями.',
  },
  {
    title: 'AI Provider',
    text: 'Выберите провайдер. Без API key NOVA работает в локальном режиме.',
  },
  {
    title: 'Голос',
    text: 'Скажите «Нова» для активации. Wake word можно настроить позже.',
  },
  {
    title: 'Разрешения',
    text: 'NOVA запросит разрешения для файлов, приложений и других функций.',
  },
  {
    title: 'Готово!',
    text: 'NOVA готова к работе. Начните диалог или скажите «Нова».',
  },
];

export function FirstRunWizard({ onComplete }: Props) {
  const [step, setStep] = useState(0);
  const [provider, setProvider] = useState('local');

  const next = async () => {
    if (step === 1) {
      await api.updateSettings({ ai_provider: provider });
    }
    if (step < STEPS.length - 1) {
      setStep(step + 1);
    } else {
      onComplete();
    }
  };

  const skip = () => onComplete();

  return (
    <div className="wizard-overlay">
      <div className="wizard">
        <div className="wizard-steps">
          {STEPS.map((_, i) => (
            <div key={i} className={`wizard-dot ${i === step ? 'active' : ''}`} />
          ))}
        </div>
        <h2>{STEPS[step].title}</h2>
        <p>{STEPS[step].text}</p>

        {step === 1 && (
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            style={{ marginBottom: 24, width: '100%' }}
          >
            <option value="local">Local (без API)</option>
            <option value="openai">OpenAI</option>
            <option value="ollama">Ollama</option>
          </select>
        )}

        <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
          <button className="btn btn-secondary" onClick={skip}>Пропустить</button>
          <button className="btn btn-primary" onClick={next}>
            {step < STEPS.length - 1 ? 'Далее' : 'Начать'}
          </button>
        </div>
      </div>
    </div>
  );
}
