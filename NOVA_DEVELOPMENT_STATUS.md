# NOVA development status

Version in code: **1.5.0**  
Product: Neural Operational & Virtual Assistant (Windows desktop)

## Architecture

Python FastAPI (`jarvis/`) + HUD UI (`static/`) + `pywebview` + portable CPython 3.12 in `runtime/`.

`NOVA.vbs` / `NOVA-Setup.exe` → `pythonw run.py` → uvicorn thread → native window.

Profile: `%LOCALAPPDATA%\NOVA` on Windows (legacy `.\data` is reused if it already has settings).

## Implemented

Core, chat, local tools, PC control, memory, skills, agents, file agent, Start Menu launcher, permissions, diagnostics, backup/restore, research (opt-in public web), wizard, hidden launcher, Inno Setup script, CI artifacts, logs export, offline badge, TTS/STT with echo lock, wake word in recognizer.

## Honest limits (not faked in UI)

- Local LLM weights are not bundled. Ollama works if already installed.
- Porcupine wake-word SDK is not bundled. Wake word uses Speech Recognition + echo lock.
- Drag-and-drop skill canvas: form editor runs the same skills.
- WinRT OCR / GPU temp: screenshot always; OCR only if Tesseract is present.
- Clean Windows VM uninstall is verified by CI producing Setup.exe; this Linux builder cannot run the exe.

## Tests

`pytest` **89 passed** twice on 2026-08-20.

Windows installer is produced by GitHub Actions job `windows-zip` (`NOVA-Setup.exe`, `NOVA-windows.zip`, `SHA256.txt`).
