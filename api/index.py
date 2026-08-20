"""Nova — персональный ИИ-ассистент (backend).

FastAPI-приложение, которое отдаёт веб-интерфейс Nova и проксирует
запросы к OpenAI. Если ключ OPENAI_API_KEY не задан, включается
локальный демо-режим, чтобы интерфейс оставался полностью рабочим.
"""

from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path
from typing import Iterator, List, Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

MODEL = os.getenv("NOVA_MODEL", "gpt-5")
MAX_HISTORY = 24

NOVA_SYSTEM_PROMPT = (
    "Ты — Nova, персональный ИИ-ассистент своего пользователя, в духе "
    "J.A.R.V.I.S. из «Железного человека». Твой стиль: уверенный, тёплый, "
    "с лёгким чувством юмора, но всегда по делу.\n"
    "Принципы:\n"
    "— Отвечай прямо и честно, без лишних оговорок и морализаторства.\n"
    "— Обсуждай любые темы, помогай с кодом, идеями, планами, расчётами и бытом.\n"
    "— По умолчанию отвечай на русском, кратко и структурно; код давай в блоках.\n"
    "— Если чего-то не знаешь — скажи прямо и предложи, как выяснить.\n"
    "— Обращайся к пользователю на «ты», дружелюбно."
)


app = FastAPI(title="Nova", description="Персональный ИИ-ассистент")


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    stream: bool = True
    temperature: float = 0.7


def _openai_client():
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    try:
        from openai import OpenAI

        return OpenAI(api_key=key)
    except Exception:
        return None


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


# --------------------------------------------------------------------------
# Демо-режим (без ключа): связный локальный ответ, чтобы интерфейс работал.
# --------------------------------------------------------------------------
_DEMO_INTROS = [
    "На связи, Nova слушает.",
    "Принято. Разбираемся.",
    "Готова помочь.",
]


def _demo_reply(user_text: str) -> str:
    text = (user_text or "").strip()
    low = text.lower()
    intro = random.choice(_DEMO_INTROS)

    if any(w in low for w in ("привет", "здоров", "хай", "hello", "hi", "ку")):
        body = (
            "Привет! Я **Nova** — твой персональный ассистент. "
            "Могу помочь с кодом, идеями, планированием и ответами на вопросы."
        )
    elif "?" in text or any(
        w in low for w in ("как", "почему", "что", "зачем", "когда", "где", "кто")
    ):
        body = (
            f"Ты спросил: «{text}».\n\n"
            "Сейчас я работаю в **демо-режиме** — реальная языковая модель "
            "не подключена. Как только в окружении появится ключ "
            "`OPENAI_API_KEY`, я начну давать полноценные развёрнутые ответы "
            "по любой теме."
        )
    else:
        body = (
            f"Записала: «{text}».\n\n"
            "Это демо-ответ. Подключи `OPENAI_API_KEY` — и Nova заработает "
            "на полную мощность с настоящим ИИ."
        )

    return f"{intro} {body}"


def _demo_stream(user_text: str) -> Iterator[str]:
    reply = _demo_reply(user_text)
    for token in reply.split(" "):
        yield token + " "
        time.sleep(0.02)


# --------------------------------------------------------------------------
# Реальный ответ через OpenAI Responses API.
# --------------------------------------------------------------------------
def _openai_stream(client, messages: List[ChatMessage], temperature: float) -> Iterator[str]:
    convo = [{"role": m.role, "content": m.content} for m in messages[-MAX_HISTORY:]]
    try:
        stream = client.responses.create(
            model=MODEL,
            instructions=NOVA_SYSTEM_PROMPT,
            input=convo,
            temperature=temperature,
            stream=True,
        )
        for event in stream:
            etype = getattr(event, "type", "")
            if etype == "response.output_text.delta":
                delta = getattr(event, "delta", "") or ""
                if delta:
                    yield delta
            elif etype == "response.error":
                raise RuntimeError(getattr(event, "error", "stream error"))
        return
    except TypeError:
        # SDK не поддерживает stream=True в таком виде — падаем в non-stream.
        pass

    response = client.responses.create(
        model=MODEL,
        instructions=NOVA_SYSTEM_PROMPT,
        input=convo,
        temperature=temperature,
    )
    yield getattr(response, "output_text", "") or ""


@app.get("/api/health")
def health():
    return {
        "status": "online",
        "name": "Nova",
        "model": MODEL,
        "ai_connected": bool(os.getenv("OPENAI_API_KEY")),
    }


@app.post("/api/chat")
def chat(req: ChatRequest):
    if not req.messages:
        return JSONResponse({"error": "messages is empty"}, status_code=400)

    last_user = next(
        (m.content for m in reversed(req.messages) if m.role == "user"), ""
    )
    client = _openai_client()

    def event_source() -> Iterator[str]:
        yield _sse({"type": "start", "ai_connected": client is not None})
        try:
            if client is None:
                chunks = _demo_stream(last_user)
            else:
                chunks = _openai_stream(client, req.messages, req.temperature)
            for chunk in chunks:
                yield _sse({"type": "delta", "content": chunk})
        except Exception as exc:  # noqa: BLE001
            yield _sse(
                {
                    "type": "error",
                    "content": f"Ошибка при обращении к модели: {exc}",
                }
            )
        yield _sse({"type": "done"})

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/")
def index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"status": "Nova online", "hint": "static UI not found"}


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
