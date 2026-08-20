# NOVA Development Status

Date: 2026-08-20
Version: 1.0.0
Branch: `cursor/nova-production-desktop-6c7e`

## PHASE 1 — Audit

Workspace `main` contained only a stub FastAPI JARVIS (`api/index.py`, `server. py`). No installer, no GUI, no memory, no skills.

Existing branches:

| Branch | What it had | Keep? |
| --- | --- | --- |
| `cursor/jarvis-pc-assistant-a7a1` | Working desktop UI, local brain, voice TTS, PC control, ZIP package | Yes, as logic base |
| `cursor/setup-cloud-agent-environment-74f2` | Inno Setup + PyInstaller workflow | Yes, installer approach |
| `cursor/nova-local-assistant-2fa7` | Smaller local assistant | Concepts only |

Preferred conceptual base: NOVA-PC-v0.9.15-RUSSIAN-VOICE-FIX2 — archive not in this repo. Closest working code is jarvis-pc-assistant (voice + local tools). Versions 0.9.37–0.9.39 were not used.

## Architecture now

Modular Python package `nova/` + local FastAPI + pywebview + SQLite.

AI Provider → Core → Memory → Skills → Tools → Agents → Computer → Voice → UI → Windows

User data: `%LOCALAPPDATA%\NOVA` (survives updates).

## Implemented

- Core, settings, DPAPI secrets, permissions, confirmations, audit log
- Local / OpenAI-compatible / Ollama providers
- Memory CRUD, skills builder, multi-agent catalog + planner/executor/timeout/retry
- File, system, apps, clipboard, notes, web, computer-control tools
- Voice TTS (edge-tts + SAPI), wake word, echo guard, STT via Web Speech
- Creator-only public research mode (permission gated, no auth bypass)
- Tasks, notifications, backup/restore, diagnostics, first-run wizard
- Dark/light UI, scaling, all sidebar sections wired to APIs
- Tests: functional, security, stress
- Windows production installer via GitHub Actions: `NOVA-Setup.exe`

## Dependencies

See `requirements.txt`. Bundled into the installer by PyInstaller. End user does not install Python.

## Test results

Local (Linux, 2026-08-20):

- `python -m pytest -q` → **36 passed**
- Live server smoke: `/health` ok, chat «привет» ok, calculator 12*12 = 144, diagnostics **PASS** (18 checks), UI 200
- Windows `NOVA-Setup.exe` is built by GitHub Actions `windows-release` (PyInstaller onedir + Inno Setup), then silently installed, launched, and uninstalled on `windows-latest`

## Remaining environment limits

This Cloud Agent is Linux. The production installer binary is produced on GitHub-hosted Windows runners. After CI succeeds, download `NOVA-Setup.exe` from the workflow artifact `NOVA-Windows`.
