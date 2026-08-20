from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from jarvis.brain import respond
from jarvis.config import load_settings, merge_settings, public_settings, save_settings
from jarvis.memory import ConversationMemory
from jarvis.voice import list_russian_voices, speech_preview, synthesize

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"

app = FastAPI(title="NOVA", version="1.3.0")
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


class PcIn(BaseModel):
    action: str
    value: int | None = None


@app.get("/api/status")
def api_status() -> dict[str, Any]:
    settings = load_settings()
    return {
        "status": "NOVA online",
        "assistant": settings.assistant_name,
        "user": settings.user_name,
        "ready": True,
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
    audio, mime = await synthesize(payload.text, voice=voice, rate=settings.tts_rate or "+12%")
    if not audio:
        raise HTTPException(status_code=502, detail="Не удалось синтезировать речь")
    return Response(content=audio, media_type=mime, headers={"Cache-Control": "private, max-age=86400"})


@app.get("/api/pc")
def pc_state() -> dict[str, Any]:
    return {
        "actions": [
            "volume_up",
            "volume_down",
            "mute",
            "brightness",
            "brighter",
            "darker",
            "play",
            "next",
            "prev",
            "mixer",
            "display",
            "lock",
            "screenshot",
        ],
    }


@app.post("/api/pc")
def pc_action(payload: PcIn) -> dict[str, Any]:
    from jarvis import pc_control

    action = payload.action
    try:
        if action == "volume_up":
            reply = pc_control.volume_up()
        elif action == "volume_down":
            reply = pc_control.volume_down()
        elif action == "mute":
            reply = pc_control.volume_mute()
        elif action == "brightness":
            reply = pc_control.set_brightness(payload.value or 70)
        elif action == "brighter":
            reply = pc_control.brightness_up()
        elif action == "darker":
            reply = pc_control.brightness_down()
        elif action == "play":
            reply = pc_control.media_play_pause()
        elif action == "next":
            reply = pc_control.media_next()
        elif action == "prev":
            reply = pc_control.media_prev()
        elif action == "mixer":
            reply = pc_control.open_sound_settings()
        elif action == "display":
            reply = pc_control.open_display_settings()
        elif action == "lock":
            from jarvis.desktop import lock_workstation

            reply = lock_workstation()
        elif action == "screenshot":
            from jarvis.desktop import take_screenshot

            reply = f"Скриншот сохранён: {take_screenshot()}"
        else:
            raise HTTPException(status_code=400, detail="unknown action")
    except RuntimeError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    return {"reply": reply, "action": action}


async def _chat(text: str) -> dict[str, Any]:
    settings = load_settings()
    result = await respond(settings, memory.history(), text.strip())
    result["speech"] = speech_preview(result["reply"])
    memory.add("user", text.strip())
    memory.add("assistant", result["reply"])
    return result


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


if STATIC.exists():
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
