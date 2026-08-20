let baseUrl = 'http://127.0.0.1:47821';

export async function initApi(): Promise<void> {
  if (window.nova?.getBackendUrl) {
    baseUrl = await window.nova.getBackendUrl();
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${baseUrl}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

export const api = {
  getStatus: () => request<import('../types').NovaStatus>('/api/status'),
  chat: (text: string, confirmed = false) =>
    request<{ reply: string }>('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ text, confirmed }),
    }),
  getSettings: () => request<Record<string, unknown>>('/api/settings'),
  updateSettings: (data: Record<string, unknown>) =>
    request('/api/settings', { method: 'PUT', body: JSON.stringify({ data }) }),
  setSecret: (key: string, value: string | null) =>
    request('/api/secrets', { method: 'POST', body: JSON.stringify({ key, value }) }),
  getMemory: () => request<import('../types').MemoryItem[]>('/api/memory'),
  createMemory: (data: { content: string; type?: string; category?: string }) =>
    request('/api/memory', { method: 'POST', body: JSON.stringify(data) }),
  deleteMemory: (id: number) => request(`/api/memory/${id}`, { method: 'DELETE' }),
  searchMemory: (q: string) => request(`/api/memory/search?q=${encodeURIComponent(q)}`),
  getSkills: () => request<import('../types').Skill[]>('/api/skills'),
  createSkill: (data: Partial<import('../types').Skill>) =>
    request('/api/skills', { method: 'POST', body: JSON.stringify(data) }),
  updateSkill: (id: number, data: Partial<import('../types').Skill>) =>
    request(`/api/skills/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteSkill: (id: number) => request(`/api/skills/${id}`, { method: 'DELETE' }),
  executeSkill: (id: number) => request(`/api/skills/${id}/execute`, { method: 'POST' }),
  getAgents: () => request<import('../types').Agent[]>('/api/agents'),
  createAgent: (data: Partial<import('../types').Agent>) =>
    request('/api/agents', { method: 'POST', body: JSON.stringify(data) }),
  runAgentTask: (task: string, agentId?: number) =>
    request('/api/agents/run', {
      method: 'POST',
      body: JSON.stringify({ task, agent_id: agentId }),
    }),
  getTools: () => request<Array<{ name: string; description: string }>>('/api/tools'),
  executeTool: (name: string, params: Record<string, unknown>, confirmed = false) =>
    request('/api/tools/execute', {
      method: 'POST',
      body: JSON.stringify({ name, params, confirmed }),
    }),
  getPermissions: () => request<import('../types').Permission[]>('/api/permissions'),
  setPermission: (name: string, enabled: boolean) =>
    request(`/api/permissions/${name}`, {
      method: 'PUT',
      body: JSON.stringify({ enabled }),
    }),
  getTasks: () => request<import('../types').Task[]>('/api/tasks'),
  createTask: (data: { title: string; type?: string }) =>
    request('/api/tasks', { method: 'POST', body: JSON.stringify(data) }),
  runDiagnostics: () =>
    request<{ overall: string; checks: import('../types').DiagnosticCheck[] }>('/api/diagnostics'),
  createBackup: () => request<{ path: string }>('/api/backup', { method: 'POST' }),
  exportLogs: () => request<{ content: string }>('/api/logs/export'),
  testMicrophone: () => request('/api/voice/test/microphone', { method: 'POST' }),
  testTts: () => request('/api/voice/test/tts', { method: 'POST' }),
  researchSearch: (query: string) =>
    request('/api/research/search', { method: 'POST', body: JSON.stringify({ query }) }),
};
