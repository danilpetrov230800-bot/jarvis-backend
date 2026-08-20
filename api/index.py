"""Nova — персональный ИИ-ассистент (backend).

FastAPI-приложение: веб-интерфейс, потоковый чат с инструментами,
локальный ИИ (Ollama) без ключей, управление ПК и PWA.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterator, List, Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import assistant, llm
from . import system_control as sysctl
from . import tools

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Nova", description="Персональный ИИ-ассистент")


# --------------------------------------------------------------------------
# Модели запросов
# --------------------------------------------------------------------------
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    stream: bool = True


class ValueIn(BaseModel):
    value: int


class MuteIn(BaseModel):
    state: bool = True


class ActionIn(BaseModel):
    action: str


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _fast_tokens(text: str) -> Iterator[str]:
    import time

    for token in text.split(" "):
        yield token + " "
        time.sleep(0.008)


# --------------------------------------------------------------------------
# Чат
# --------------------------------------------------------------------------
@app.post("/api/chat")
def chat(req: ChatRequest):
    if not req.messages:
        return JSONResponse({"error": "messages is empty"}, status_code=400)

    messages = [m.model_dump() for m in req.messages]
    last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    routed = assistant.detect_and_run(last_user)
    info = llm.provider_info()
    # Ответы инструментов уже точны и готовы — отдаём их мгновенно, без медленной
    # модели. Рефразирование моделью можно включить через NOVA_TOOL_REPHRASE=1.
    rephrase = os.getenv("NOVA_TOOL_REPHRASE") == "1"

    def gen() -> Iterator[str]:
        yield _sse({"type": "start", "provider": info["provider"], "model": info["model"]})
        for ev in routed["events"]:
            yield _sse({
                "type": "tool",
                "tool": ev.get("tool", "tool"),
                "title": ev.get("title", ""),
                "ok": ev.get("ok", True),
                "summary": ev.get("summary", ""),
                "data": ev.get("data", {}),
                "source": ev.get("source", ""),
            })
        try:
            if routed["used"] and not rephrase:
                for token in _fast_tokens(routed["direct"]):
                    yield _sse({"type": "delta", "content": token})
            else:
                for delta in llm.stream_reply(messages, routed["context"], routed["direct"]):
                    yield _sse({"type": "delta", "content": delta})
        except Exception as exc:  # noqa: BLE001
            yield _sse({"type": "error", "content": f"Ошибка модели: {exc}"})
        yield _sse({"type": "done"})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --------------------------------------------------------------------------
# Инструменты (прямой доступ)
# --------------------------------------------------------------------------
@app.get("/api/tools/weather")
def api_weather(city: str = "Москва"):
    return tools.weather(city)


@app.get("/api/tools/search")
def api_search(q: str):
    return tools.web_search(q)


@app.get("/api/tools/wiki")
def api_wiki(q: str):
    return tools.wikipedia(q)


@app.get("/api/tools/currency")
def api_currency(amount: float = 1, base: str = "USD", target: str = "RUB"):
    return tools.currency(amount, base, target)


@app.get("/api/tools/time")
def api_time(city: Optional[str] = None):
    return tools.time_in(city)


@app.get("/api/tools/route")
def api_route(origin: str, destination: str):
    return tools.route(origin, destination)


@app.get("/api/tools/news")
def api_news(topic: str = ""):
    return tools.news(topic)


# --------------------------------------------------------------------------
# Управление ПК
# --------------------------------------------------------------------------
@app.get("/api/system/status")
def api_status():
    return sysctl.status()


@app.get("/api/system/volume")
def api_get_volume():
    return sysctl.get_volume()


@app.post("/api/system/volume")
def api_set_volume(body: ValueIn):
    return sysctl.set_volume(body.value)


@app.post("/api/system/mute")
def api_mute(body: MuteIn):
    return sysctl.mute(body.state)


@app.post("/api/system/brightness")
def api_brightness(body: ValueIn):
    return sysctl.set_brightness(body.value)


@app.post("/api/system/media")
def api_media(body: ActionIn):
    return sysctl.media(body.action)


@app.post("/api/system/power")
def api_power(body: ActionIn):
    return sysctl.power(body.action)


# --------------------------------------------------------------------------
# Статус / здоровье
# --------------------------------------------------------------------------
@app.get("/api/health")
def health():
    info = llm.provider_info()
    return {
        "status": "online",
        "name": "Nova",
        "provider": info["provider"],
        "model": info["model"],
        "provider_label": info["label"],
        "os": sysctl.OS,
        "tools": ["weather", "search", "wiki", "currency", "time", "route", "news", "calculate"],
    }


# --------------------------------------------------------------------------
# PWA + статика
# --------------------------------------------------------------------------
@app.get("/")
def index():
    f = STATIC_DIR / "index.html"
    return FileResponse(f) if f.exists() else JSONResponse({"status": "Nova online"})


@app.get("/manifest.webmanifest")
def manifest():
    f = STATIC_DIR / "manifest.webmanifest"
    return FileResponse(f, media_type="application/manifest+json")


@app.get("/sw.js")
def service_worker():
    f = STATIC_DIR / "sw.js"
    return FileResponse(f, media_type="text/javascript")


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
