from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from jarvis.config import load_settings, merge_settings, public_settings, save_settings
from jarvis.llm import LLMError, chat_once
from jarvis.memory import ConversationMemory
from jarvis.voice import list_russian_voices, synthesize

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"

app = FastAPI(title="JARVIS", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

memory = ConversationMemory()


class ChatIn(BaseModel):
    text: str = Field(min_length=1, max_length=8000)


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=8000)


class SettingsIn(BaseModel):
    provider: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    user_name: str | None = None
    assistant_name: str | None = None
    tts_voice: str | None = None
    tts_rate: str | None = None
    search_region: str | None = None


class SpeakIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    voice: str | None = None


@app.get("/api/status")
def api_status() -> dict[str, Any]:
    settings = load_settings()
    return {
        "status": "JARVIS online",
        "assistant": settings.assistant_name,
        "user": settings.user_name,
        "ready": bool(settings.api_key) or settings.provider == "ollama",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/settings")
def get_settings() -> dict[str, Any]:
    return public_settings(load_settings())


@app.post("/api/settings")
def update_settings(payload: SettingsIn) -> dict[str, Any]:
    current = load_settings()
    patch = payload.model_dump(exclude_none=True)
    if patch.get("api_key") == "":
        patch.pop("api_key")
    updated = merge_settings(current, patch)
    save_settings(updated)
    return public_settings(updated)


@app.get("/api/voices")
async def voices() -> dict[str, Any]:
    return {"voices": await list_russian_voices()}


@app.post("/api/chat")
async def api_chat(payload: ChatIn) -> dict[str, Any]:
    return await _chat(payload.text)


@app.post("/chat")
async def legacy_chat(payload: MessageIn) -> dict[str, Any]:
    result = await _chat(payload.text)
    return {"reply": result["reply"], **{k: v for k, v in result.items() if k != "reply"}}


@app.post("/api/reset")
def reset_memory() -> dict[str, str]:
    memory.clear()
    return {"status": "cleared"}


@app.post("/api/speak")
async def speak(payload: SpeakIn) -> Response:
    settings = load_settings()
    voice = payload.voice or settings.tts_voice
    audio = await synthesize(payload.text, voice=voice, rate=settings.tts_rate)
    if not audio:
        raise HTTPException(status_code=502, detail="Не удалось синтезировать речь")
    return Response(content=audio, media_type="audio/mpeg")


async def _chat(text: str) -> dict[str, Any]:
    settings = load_settings()
    try:
        result = await chat_once(settings, memory.history(), text.strip())
    except LLMError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    memory.add("user", text.strip())
    memory.add("assistant", result["reply"])
    return result


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


if STATIC.exists():
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
