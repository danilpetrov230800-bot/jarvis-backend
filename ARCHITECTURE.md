# Architecture

NOVA is a local desktop application. PyWebView hosts the HTML interface while a
loopback-only FastAPI service provides typed application APIs.

- `jarvis/app.py`: API boundary and error-safe responses.
- `jarvis/brain.py`, `jarvis/llm.py`: intent and AI-provider routing.
- `jarvis/storage.py`: SQLite migrations, audit, backup, and restore.
- `jarvis/core.py`: memory, Skills, Agents, Tasks, bounded execution.
- `jarvis/permissions.py`: deny-by-default capability checks.
- `jarvis/file_agent.py`: confined local file operations.
- `jarvis/voice.py`: network TTS with Windows SAPI fallback.
- `static/`: native WebView UI and wake-word speech pipeline.

Persistent state lives under the user's local application-data directory,
separate from immutable installed files. Updates can replace the application
without replacing the profile. SQLite schema changes use `PRAGMA user_version`.
