# NOVA — статус разработки

## Аудит (2026-08-20)

Исходная ветка `main` содержала только небольшой FastAPI endpoint JARVIS (`api/index.py`) и не являлась desktop-приложением. В удалённой ветке `cursor/jarvis-pc-assistant-a7a1` обнаружена работоспособная база NOVA; она интегрирована в рабочую ветку как сохраняемая основа.

Архив или тег `NOVA-PC-v0.9.15-RUSSIAN-VOICE-FIX2` в репозитории не найден. Версии `v0.9.37`, `v0.9.38` и `v0.9.39` не найдены и не использовались.

## Сохранённые компоненты

- FastAPI backend и pywebview-окно (`jarvis/app.py`, `jarvis/window.py`).
- Текстовый чат, OpenAI-compatible providers, Ollama.
- Базовые локальные команды: калькулятор, заметки, таймер, буфер обмена, скриншот, открытие приложений и сайтов, системная информация.
- Edge TTS, браузерное распознавание речи, русскоязычный UI.
- Веб-поиск, погода, новости, курс валют и справочные сервисы.
- Unit-тесты для текущих возможностей.

## Выявленные риски и недостатки

- Отсутствует Windows installer `NOVA-Setup.exe`; существующая упаковка является ZIP и во время первого запуска скачивает Python и зависимости.
- Пользовательские данные расположены рядом с исходным кодом/установкой, что небезопасно при обновлении и ограничениях прав.
- API-ключ сохраняется как открытый JSON, а не в Windows Credential Manager.
- Нет SQLite-миграций, расширенной памяти, Skills, Agents, задач, резервного копирования, диагностики и permission system.
- Лаунчер выводит технический текст и допускает браузерный fallback; production-запуск не должен требовать консоли.
- Список приложений в значительной части жёстко задан, нет полноценного индекса Start Menu/registry.
- Голос зависит от браузерного SpeechRecognition, нет локального wake-word/VAD pipeline.

## Целевая архитектура

`nova_core` добавляется поверх сохранённого транспорта:

1. `storage`: SQLite, миграции, резервные копии и путь `%LOCALAPPDATA%\NOVA`.
2. `security`: разрешения, подтверждения, аудит и безопасное хранилище секретов.
3. `memory`, `skills`, `agents`, `tasks`, `diagnostics`: изолированные сервисы с API.
4. `jarvis`: совместимый UI и HTTP слой, перенаправленный на сервисы Core.
5. `installer`: PyInstaller + Inno Setup, без dev server и без зависимости от установленного Python.

## Выполнение

- [x] Провести аудит и сохранить пригодную базу.
- [x] Переместить данные в пользовательский профиль и добавить SQLite/migrations.
- [x] Реализовать базовые permissions, memory, skills, tasks, backup и diagnostics.
- [ ] Реализовать Agent orchestration и расширенный визуальный редактор Skills.
- [ ] Расширить UI только работающими функциями.
- [x] Добавить production PyInstaller/Inno Setup packaging configuration.
- [x] Прогнать unit, integration, security и package tests.
- [ ] Проверить Windows installer на Windows runner.

## Последний результат тестов

`python3 -m pytest -q`: **68 passed**.

`python3 -m compileall -q jarvis nova_core installer`: успешно.

`python3 installer/package.py -o /tmp/NOVA-windows.zip` и `unzip -t`: успешно. Пакет содержит Core (`nova_core/storage.py`, `nova_core/security.py`).

Windows `.exe` не собирался в Linux Cloud Agent: PyInstaller не может кросс-компилировать Windows GUI executable. Для этого добавлен воспроизводимый Windows GitHub Actions workflow, который устанавливает Inno Setup, собирает PyInstaller приложение и публикует `release/NOVA-Setup.exe`.
