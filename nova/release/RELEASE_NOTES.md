# NOVA v1.0.0 Release Notes

**Release Date:** 2026-08-20

## NOVA — Neural Operational & Virtual Assistant

Первый полноценный релиз desktop AI-ассистента для Windows.

## Установка

### Windows Installer
Скачайте `NOVA-Setup.exe` и запустите установщик.
> **Note:** NOVA-Setup.exe собирается на Windows через `scripts/build-windows.ps1`.
> В Linux CI доступен `NOVA-Portable.zip`.

### Portable
Распакуйте `NOVA-Portable.zip` и запустите через Electron.

## Что нового

### Core
- Модульное ядро NOVA с оркестрацией всех подсистем
- Offline mode с автоматическим определением сети
- Crash recovery на уровне компонентов

### AI
- 4 провайдера: OpenAI, Ollama, Local, Compatible API
- Fallback на локальный режим без API key
- Безопасное хранение API keys

### Voice
- Speech-to-Text и Text-to-Speech
- Wake word: «Нова» / «NOVA»
- Echo protection
- Graceful fallback на текстовый режим

### Features
- Memory (6 типов) с поиском и экспортом
- Skills с визуальным Skill Builder
- Multi-agent system (Research, File, System + custom)
- 20+ локальных инструментов
- Permission system с подтверждением опасных действий
- Creator Research / OSINT mode
- Task manager
- Backup/restore
- Diagnostics (11 checks)
- First-run wizard

### UI
- Современный Electron + React интерфейс
- 10 экранов: Home, Chat, Agents, Skills, Memory, Tools, Tasks, Research, Settings, Logs
- Dark/Light theme
- Agent progress visualization

## Tests

- 20/20 self-test checks passed
- 8/8 unit tests passed

## Known Limitations

- Voice wake word использует STT (не Porcupine) — работает на Windows с микрофоном
- OCR требует Tesseract OCR на системе
- Windows installer требует сборки на Windows

## SHA256

See `SHA256.txt`
