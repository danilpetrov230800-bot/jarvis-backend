# История изменений (CHANGELOG.md)

## [1.0.0] - 2026-08-20
### Добавлено:
- Полнофункциональное модульное ядро **NOVA Core** под Windows 10/11.
- Унифицированная абстракция **AI Provider** (Local, OpenAI, Ollama, Compatible API).
- Локальные инструменты **Local-First** (калькулятор, заметки, управление громкостью/яркостью, системный монитор, процессы, файловый менеджер).
- Многоуровневая система памяти (Short-term, Long-term, Preferences, Episodic, Semantic).
- Визуальный конструктор и движок навыков **Visual Skill Builder**.
- Мульти-агентный фреймворк (**File Agent**, **System Agent**, **Research Agent**, **Automation Agent**).
- Голосовой пайплайн с распознаванием Wake Word («Нова», «NOVA») и синтезом речи Neural TTS.
- Закрытый режим открытых данных **Creator Research (OSINT) Mode**.
- Модуль **15-точечной самодиагностики** и восстановления после сбоев.
- Создание standalone дистрибутива `release/NOVA-Setup.exe` и `release/NOVA-Portable.zip`.
- Полный набор автоматических тестов `tests/test_master_suite.py` (TEST 01 - TEST 26).
