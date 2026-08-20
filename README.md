# JARVIS для ПК

Персональный ИИ-помощник: русский голос, поиск по интернету, окно как у Джарвиса.

## Как запустить (Windows)

1. Скачайте **JARVIS-windows.zip** из вкладки [Actions](https://github.com/danilpetrov230800-bot/jarvis-backend/actions) (артефакт `JARVIS-windows`) или возьмите папку репозитория.
2. Распакуйте архив.
3. Нажмите дважды **`JARVIS.bat`**.

Первый запуск сам ставит Python, если его нет (1–3 минуты). Потом откроется окно помощника.

Вставьте API-ключ. Бесплатный вариант: [Groq](https://console.groq.com/keys) (ключ вида `gsk_...`).

Ярлык **JARVIS** появится на рабочем столе. Голос — в Chrome или Edge.

Если Windows пишет «защитил компьютер»: Дополнительно → Выполнить в любом случае.  
Если файл из интернета: ПКМ → Свойства → Разблокировать.

## Что умеет

- Грамотная русская речь (текст + голос Dmitry Neural).
- Микрофон, активация по «Джарвис».
- Поиск по открытому интернету без SafeSearch, чтение страниц.
- Погода и время.
- OpenRouter, OpenAI, Groq или локальная Ollama.

Поиск не режет запросы. Помощник не помогает со взломом, мошенничеством и вредом людям.

## Если ставите из исходников

```bat
JARVIS.bat
```

Linux / macOS (нужен свой Python 3.11+):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Ключ также можно прописать в `.env` — см. `.env.example`.

## Сборка ZIP

```bash
python installer/package.py
```

Готовый файл: `dist/JARVIS-windows.zip`. На Windows CI в архив ещё кладётся переносной Python.

## Разработка

```bash
pip install -r requirements-dev.txt
pytest
```
