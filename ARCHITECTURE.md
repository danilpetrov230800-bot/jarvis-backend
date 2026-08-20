# Архитектура NOVA

NOVA упакована как одно Windows GUI-приложение. Внутри него запускаются локальный FastAPI transport и pywebview; пользователь не запускает сервер вручную.

`jarvis/` — UI transport, голос, provider adapters и сохранённые локальные инструменты.

`nova_core/` — независимые доменные сервисы:

- `storage.py`: `%LOCALAPPDATA%\NOVA`, SQLite и резервное копирование.
- `security.py`: Windows DPAPI для API-ключа, permissions и audit trail.
- `services.py`: память, skills, задачи, диагностика, backup/restore.

Провайдеры подключаются через OpenAI-compatible transport. Локальный Ollama не требует API-ключа; при отсутствии модели NOVA остаётся в локальном инструментальном режиме.

Опасные возможности проектируются через явные permissions. Операции удаления, настройки системы, ввода на экран, камеры и микрофона не могут быть неявно выданы агенту.
