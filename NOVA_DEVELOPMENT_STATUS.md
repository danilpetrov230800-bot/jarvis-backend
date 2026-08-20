# NOVA Development Status

## Baseline audit

- `main` contained only a 38-line FastAPI/OpenAI JARVIS endpoint.
- No archive or tag named `NOVA-PC-v0.9.15-RUSSIAN-VOICE-FIX2` exists in this repository.
- The explicitly rejected versions `v0.9.37`–`v0.9.39` are also absent.
- Two remote implementations were compared. The more complete
  `cursor/jarvis-pc-assistant-a7a1` branch was preserved because it includes native
  pywebview UI, Russian voice, local commands, PC controls, portable packaging, and 63 tests.
- The separate packaging branch supplied a reusable icon and PyInstaller/Inno Setup approach.

## Current architecture

`UI (WebView2/HTML) → FastAPI Core → provider / memory / skills / agents / tasks /
permissions / tools → SQLite and per-user files → Windows`

- Native launcher: `run.py`, `jarvis/window.py`
- HTTP/UI boundary: `jarvis/app.py`, `static/`
- Intent and provider routing: `jarvis/brain.py`, `jarvis/llm.py`
- Durable SQLite core: `jarvis/storage.py`, `jarvis/core.py`
- Permission enforcement: `jarvis/permissions.py`
- Local file operations: `jarvis/file_agent.py`
- Voice/TTS: `jarvis/voice.py` plus WebView speech recognition
- Diagnostics and backup: `jarvis/diagnostics.py`, `jarvis/storage.py`
- Windows build: PyInstaller one-folder application + Inno Setup installer

## Preserved functions

Russian text chat, optional OpenAI-compatible providers, Ollama-compatible endpoint,
offline deterministic commands, Web search and public information services, TTS,
wake phrase handling, notes, timer, calculator, clipboard, screenshots, volume/media/
brightness controls, app and site launching, native window/widget mode.

## Implemented in this development branch

- Writable per-user storage under `%LOCALAPPDATA%\NOVA`.
- Versioned SQLite database in WAL mode.
- Long-term memory CRUD/search, skills, specialized agent definitions, and task registry.
- Permission defaults, explicit dangerous-permission confirmation, and security audit log.
- Bounded execution utility with timeout and retry limits.
- File search/read/write/copy/move/archive/duplicate/delete modules with profile-root
  confinement and explicit delete confirmation.
- DPAPI-protected API-key storage on Windows and key deletion.
- Profile backup/validated restore with traversal protection and automatic safety backup.
- Diagnostics for database, provider, voice, storage, assets, disk, permissions, and network.
- Functional UI sections for chat, memory, skills, agents, tasks, tools, research,
  permissions, diagnostics, logs, and settings.
- Wake-word command window and TTS echo suppression.
- Production installer workflow with packaged-app smoke test, silent clean install,
  installed diagnostics, uninstall test, portable ZIP, checksums, and release notes.

## Dependencies

Python 3.12 is bundled by PyInstaller. Runtime libraries are declared in
`requirements.txt`. End users do not install Python, Node.js, Git, or libraries.
WebView2 is a standard Windows 10/11 runtime; pywebview falls back to the system browser
if native window initialization fails.

## Known platform boundary

Linux can run all portable unit/API/security tests, but Windows-only microphone,
SAPI, WebView2, installer, shortcut, and uninstall checks execute on the
`windows-latest` production workflow. Release artifacts are accepted only if that job
passes its installed-build checks.

## Test record

- Imported baseline: `63 passed`.
- Production implementation verification: recorded in `TESTING.md` and CI.

## Release output

The Windows workflow creates:

- `release/NOVA-Setup.exe`
- `release/NOVA-Portable.zip`
- `release/SHA256.txt`
- `release/RELEASE_NOTES.md`
