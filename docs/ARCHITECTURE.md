# Архитектура NOVA (ARCHITECTURE.md)

## 1. Обзор слоев системы

```
AI Models (Local Rule Engine / OpenAI / Ollama / Compatible)
       │
       ▼
  NOVA Core (Центральный координатор & Intent Routing)
  ┌────┼──────────────┬───────────────┬──────────────┐
  ▼    ▼              ▼               ▼              ▼
Memory Skills       Tools          Multi-Agents    Voice Pipeline
(SQLite)(Builder)  (Local-First)  (Autonomous)   (Wake Word/STT/TTS)
  │    │              │               │              │
  └────┴──────────────┼───────────────┴──────────────┘
                      ▼
               Security Manager
          (Permissions & Secret Redaction)
                      │
                      ▼
              Windows 10/11 OS & UI
```

## 2. Модули ядра
- `nova/core.py`: Центральное ядро, обработка интентов и маршрутизация задач.
- `nova/database.py`: База данных SQLite с версионированием схемы, WAL-режимом и автоматическими бэкапами.
- `nova/security.py`: Менеджер разрешений, аудит-лог и фильтрация API-ключей/паролей.
- `nova/memory.py`: Многоуровневая память (short_term, long_term, preferences, episodic, semantic, skill).
- `nova/skills.py`: Движок навыков и сценариев автоматизации.
- `nova/agents.py`: Мульти-агентный фреймворк с планировщиком (Planner), исполнителем (Executor), верификатором (Verifier) и защитой от циклов.
- `nova/tools.py`: Локальные инструменты ПК (файловый менеджер, монитор CPU/RAM, калькулятор, заметки, управление медиа/звуком).
- `nova/voice.py`: Подсистема речи с поддержкой Wake Word («Нова»), STT и естественного синтеза Neural TTS.
- `nova/diagnostics.py`: Модуль 15-точечной самодиагностики системы.
- `nova/research.py`: Creator-Only режим агрегации публичных данных (OSINT).
- `nova/tasks.py`: Фоновый планировщик задач и таймеров.
