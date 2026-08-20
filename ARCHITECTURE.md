# Архитектура NOVA

```
AI Provider → NOVA Core → Memory → Skills → Tools → Agents → Computer → Voice → UI → Windows
```

## Core

`nova.kernel.NovaKernel` собирает модули через явные зависимости:

- настройки и секреты
- SQLite + миграции
- разрешения и подтверждения
- память, навыки, агенты, задачи
- инструменты
- голос
- диагностика и резервные копии

## AI

Абстракция `AIProvider`:

- `local` — правила и инструменты без ключа
- `openai` / `compatible` — OpenAI-совместимый HTTP API
- `ollama` — локальная модель на порту 11434

Ключи хранятся в DPAPI на Windows, не в исходниках и не в логах.

## UI

Локальный FastAPI на 127.0.0.1 и окно pywebview (Edge WebView2). Backend поднимается самим процессом NOVA.

## Данные

`%LOCALAPPDATA%\NOVA` — база, настройки, логи, резервные копии, кэш TTS.
