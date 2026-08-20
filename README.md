# NOVA для ПК

Персональный ИИ-помощник: грамотный русский, голос, поиск по интернету.

## Как запустить (Windows)

1. Скачайте **NOVA-windows.zip** из [Actions](https://github.com/danilpetrov230800-bot/jarvis-backend/actions) (артефакт `NOVA-windows`) или возьмите папку репозитория.
2. Распакуйте архив.
3. Нажмите дважды **`NOVA.bat`**.

Первый запуск сам ставит Python, если его нет. Потом откроется окно NOVA.

Вставьте API-ключ. Бесплатно: [Groq](https://console.groq.com/keys) (`gsk_...`).

Ярлык **NOVA** появится на рабочем столе. Голос — в Chrome или Edge.

Если Windows ругается: Дополнительно → Выполнить в любом случае.  
Файл из интернета: ПКМ → Свойства → Разблокировать.

## Что умеет

- Грамотная русская речь и голос.
- Микрофон, активация по «Нова».
- Поиск по открытому интернету без SafeSearch.
- Погода и время.
- OpenRouter, OpenAI, Groq или Ollama.

## Из исходников

```bat
NOVA.bat
```

Linux / macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

## Сборка ZIP

```bash
python installer/package.py
```

Файл: `dist/NOVA-windows.zip`.

## Разработка

```bash
pip install -r requirements-dev.txt
pytest
```
