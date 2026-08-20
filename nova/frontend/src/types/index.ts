declare global {
  interface Window {
    nova?: {
      getBackendUrl: () => Promise<string>;
      openExternal: (url: string) => Promise<void>;
    };
  }
}

export interface NovaStatus {
  status: string;
  offline: boolean;
  current_task: string | null;
  voice_active: boolean;
  wake_word_active: boolean;
  version?: string;
  active_agent?: {
    task_id: string;
    title: string;
    status: string;
    steps: Array<{ status: string; detail?: string }>;
    current_step: number;
  } | null;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export interface MemoryItem {
  id: number;
  type: string;
  category: string;
  content: string;
  importance: number;
  created_at: string;
}

export interface Skill {
  id: number;
  name: string;
  description: string;
  trigger: string;
  actions: Array<Record<string, unknown>>;
  enabled: boolean;
}

export interface Agent {
  id: number;
  name: string;
  role: string;
  instructions: string;
  model: string;
  tools: string[];
  enabled: boolean;
}

export interface Permission {
  name: string;
  enabled: boolean;
  dangerous: boolean;
}

export interface Task {
  id: number;
  title: string;
  type: string;
  status: string;
  schedule: string;
}

export interface DiagnosticCheck {
  name: string;
  status: 'PASS' | 'WARNING' | 'FAIL';
  message: string;
}

export {};
