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
from nova_core.services import NovaServices
from nova_core.storage import APP_DIR

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"

app = FastAPI(title="NOVA", version="1.4.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

memory = ConversationMemory()
core = NovaServices()


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


class MemoryIn(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    category: str = "long_term"
    importance: int = Field(default=0, ge=0, le=5)


class SkillIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    trigger: str = Field(min_length=1, max_length=500)
    actions: list[dict[str, Any]] = Field(min_length=1, max_length=32)
    description: str = Field(default="", max_length=1000)


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    kind: str = "one_time"
    due_at: str | None = None
    repeat_rule: str | None = None


class PermissionIn(BaseModel):
    allowed: bool


@app.get("/api/status")
def api_status() -> dict[str, Any]:
    settings = load_settings()
    return {
        "status": "NOVA online",
        "assistant": settings.assistant_name,
        "user": settings.user_name,
        "ready": True,
        "offline_mode": not bool(settings.api_key) and settings.provider != "ollama",
        "storage": str(APP_DIR),
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


@app.get("/api/memories")
def get_memories(query: str = "") -> dict[str, Any]:
    return {"items": core.memories(query)}


@app.post("/api/memories")
def add_memory(payload: MemoryIn) -> dict[str, Any]:
    try:
        return core.add_memory(payload.content, payload.category, payload.importance)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/memories/{memory_id}")
def delete_memory(memory_id: str) -> dict[str, str]:
    core.delete_memory(memory_id)
    return {"status": "deleted"}


@app.get("/api/skills")
def get_skills() -> dict[str, Any]:
    return {"items": core.skills()}


@app.post("/api/skills")
def add_skill(payload: SkillIn) -> dict[str, Any]:
    try:
        return core.create_skill(payload.name, payload.trigger, payload.actions, payload.description)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/tasks")
def get_tasks() -> dict[str, Any]:
    return {"items": core.list_tasks()}


@app.post("/api/tasks")
def add_task(payload: TaskIn) -> dict[str, Any]:
    try:
        return core.create_task(payload.title, payload.kind, payload.due_at, payload.repeat_rule)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/permissions")
def get_permissions() -> dict[str, Any]:
    return core.permissions_status()


@app.put("/api/permissions/{permission}")
def set_permission(permission: str, payload: PermissionIn) -> dict[str, Any]:
    from nova_core.security import Permission

    try:
        item = Permission(permission)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Неизвестное разрешение.") from exc
    core.permissions.set(item, payload.allowed)
    return core.permissions_status()


@app.get("/api/diagnostics")
def get_diagnostics() -> dict[str, Any]:
    return {"checks": core.diagnostics()}


@app.post("/api/backup")
def create_backup() -> dict[str, str]:
    return {"path": str(core.backup())}


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
