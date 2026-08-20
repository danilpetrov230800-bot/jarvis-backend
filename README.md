# JARVIS для ПК

Персональный ИИ-помощник в духе Джарвиса: голос на русском, грамотная речь, поиск по открытому интернету и локальный интерфейс-HUD.

## Что умеет

- Разговаривать **грамотным русским** (текст и голос, голос Dmitry Neural по умолчанию).
- Слушать микрофон в Chrome/Edge (`ru-RU`), активироваться по «Джарвис».
- Искать в сети **без фильтра SafeSearch** и читать страницы по ссылке.
- Смотреть погоду и текущее время.
- Работать с разными моделями: OpenRouter, OpenAI, Groq или локальная Ollama.

Поиск специально не режет запросы. Это помощник для открытой информации из сети, а не инструмент для преступлений: взлом, мошенничество и вред людям он делать не будет.

## Быстрый старт (Windows)

1. Установите [Python 3.11+](https://www.python.org/downloads/).
2. Скопируйте `.env.example` в `.env` и вставьте ключ.
3. Запустите `start.bat`.

Откроется окно `http://127.0.0.1:8080`.

```bat
copy .env.example .env
start.bat
```

Linux / macOS:

```bash
cp .env.example .env
chmod +x start.sh
./start.sh
```

Или вручную:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

## Ключ модели

Нужен один ключ на выбор:

| Провайдер | Зачем | Переменная |
| --- | --- | --- |
| [OpenRouter](https://openrouter.ai/) | Много моделей, в том числе с мягкими фильтрами (Grok и др.) | `OPENROUTER_API_KEY` |
| [Groq](https://console.groq.com/) | Быстрые Llama | `GROQ_API_KEY` |
| OpenAI | GPT | `OPENAI_API_KEY` |
| [Ollama](https://ollama.com/) | Полностью локально, без облака | `JARVIS_PROVIDER=ollama` |

Ключ также можно вставить в окне **Настройки** интерфейса. Он сохраняется только на этом ПК в `data/settings.json`.

Пример `.env` для OpenRouter:

```
OPENROUTER_API_KEY=sk-or-v1-...
JARVIS_PROVIDER=openrouter
JARVIS_MODEL=x-ai/grok-4-fast
JARVIS_USER_NAME=Данила
JARVIS_TTS_VOICE=ru-RU-DmitryNeural
```

Для локальной Ollama:

```
JARVIS_PROVIDER=ollama
JARVIS_MODEL=qwen2.5:14b
JARVIS_BASE_URL=http://127.0.0.1:11434/v1
```

## Голос

- **Синтез:** Microsoft Edge TTS, русский голос `ru-RU-DmitryNeural` (можно сменить на Светлану в настройках).
- **Распознавание:** Web Speech API браузера, язык `ru-RU`. Нужны Chrome или Edge и разрешение на микрофон.

## API

Совместимо со старым контрактом:

- `GET /` — интерфейс
- `GET /health` — `{ "status": "ok" }`
- `GET /api/status` — состояние ядра
- `POST /chat` и `POST /api/chat` — `{ "text": "..." }` → `{ "reply": "..." }`
- `POST /api/speak` — озвучка
- `POST /api/settings` — ключ и модель

## Разработка

```bash
pip install -r requirements.txt
pytest
```
