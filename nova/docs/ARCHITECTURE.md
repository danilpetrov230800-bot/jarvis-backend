# NOVA Architecture

## Overview

```
AI Model
  ↓
NOVA Core (engine.py)
  ↓
Memory | Skills | Agents | Tools | Voice
  ↓
FastAPI Backend (port 47821)
  ↓
Electron + React UI
  ↓
Windows
```

## Components

### Backend (Python)

| Module | Purpose |
|--------|---------|
| `core/engine.py` | Central orchestrator |
| `core/config.py` | Settings and paths |
| `core/state.py` | Runtime state |
| `ai/` | AI provider abstraction |
| `memory/` | SQLite memory store |
| `skills/` | Skill manager and executor |
| `agents/` | Multi-agent system |
| `tools/` | Local tool registry |
| `voice/` | STT/TTS/wake word pipeline |
| `security/` | Permissions and secrets |
| `diagnostics/` | Self-diagnostics |
| `backup/` | Backup/restore |

### Frontend (Electron + React)

- Electron shell auto-starts Python backend
- React SPA with sidebar navigation
- WebSocket + REST API to backend

### Data Storage

- SQLite (`%LOCALAPPDATA%/NOVA/nova.db`)
- Logs (`%LOCALAPPDATA%/NOVA/logs/`)
- Backups (`%LOCALAPPDATA%/NOVA/backups/`)

## AI Providers

```
AIProvider
├── OpenAI
├── Ollama
├── Local (rule-based, offline)
└── Compatible API
```

Fallback chain: configured provider → local provider.

## Voice Pipeline

```
Microphone → VAD → Wake Word → STT → Intent → Core → TTS → Speaker
```

Echo protection via cooldown after TTS.

## Agent System

```
Planner → Executor → Verifier
  max_steps, timeout, retry_limit
```

## Security

- Encrypted secret storage (Fernet)
- Permission system per tool
- Audit log
- No secrets in logs
