# Architecture

NOVA is a Windows desktop assistant.

Launch: `NOVA-Setup.exe` or `NOVA.vbs` → embedded `pythonw` → FastAPI thread → `pywebview` window (browser fallback).

```
Microphone → wake word → STT → brain/planner → tools/agents → TTS → speaker
Text chat  → brain → memory/skills/tools/agents → UI
```

## Modules

- `jarvis.brain` — intent routing (local first, optional LLM)
- `jarvis.store` — SQLite (`memories`, `skills`, `tasks`, `agents`, `audit`)
- `jarvis.memory_long` / `skills` / `tasks` / `agents_catalog`
- `jarvis.agent` — planner with max_steps, timeout, retry
- `jarvis.files_agent` — sandboxed user folders
- `jarvis.apps` — Start Menu `.lnk` indexer
- `jarvis.permissions` — per-tool switches
- `jarvis.diagnostics` / `backup` / `logs` / `offline` / `recovery`
- `jarvis.llm` — OpenAI / Groq / OpenRouter / Ollama / compatible API
- `jarvis.voice` — Edge TTS + SAPI fallback, cache, preview
- `static/` — HUD UI, sidebar, wizard

## Data

On Windows, profile is `%LOCALAPPDATA%\NOVA` unless an older install already has `data/` next to the app. Updates and uninstall of Setup.exe do not wipe that profile.
