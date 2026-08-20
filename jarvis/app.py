from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from jarvis.brain import respond
from jarvis.config import ROOT, load_settings, merge_settings, public_settings, save_settings
from jarvis.core import (
    delete_record,
    list_records,
    save_agent,
    save_memory,
    save_skill,
    save_task,
    search_memory,
)
from jarvis.diagnostics import run_diagnostics
from jarvis.memory import ConversationMemory
from jarvis.permissions import PermissionDenied, list_permissions, require, set_permission
from jarvis.storage import create_backup, initialize, restore_backup
from jarvis.voice import list_russian_voices, speech_preview, synthesize

STATIC = ROOT / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize()
    yield


app = FastAPI(title="NOVA", version="2.0.0", lifespan=lifespan)


@app.exception_handler(ValueError)
async def value_error_handler(_request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(PermissionDenied)
async def permission_error_handler(_request: Request, exc: PermissionDenied) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(exc), "permission": exc.permission})

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


class PermissionIn(BaseModel):
    enabled: bool


class MemoryIn(BaseModel):
    content: str = Field(min_length=1, max_length=10_000)
    kind: str = "long_term"
    category: str = "general"
    importance: int = Field(default=3, ge=1, le=5)


class BackupIn(BaseModel):
    path: str
    confirmed: bool = False


class FileToolIn(BaseModel):
    operation: str
    path: str = ""
    destination: str = ""
    pattern: str = "*"
    content: str = ""
    paths: list[str] = Field(default_factory=list)
    confirmed: bool = False


class AgentRunIn(BaseModel):
    goal: str = Field(min_length=1, max_length=5000)
    max_steps: int = Field(default=8, ge=1, le=20)
    timeout: float = Field(default=120, ge=1, le=600)
    retry_limit: int = Field(default=1, ge=0, le=3)


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
    updated = merge_settings(current, patch)
    save_settings(updated)
    return public_settings(updated)


@app.get("/api/memory")
def get_memories(q: str = Query(default="", max_length=500)) -> list[dict[str, Any]]:
    return search_memory(q) if q else list_records("memories")


@app.post("/api/memory")
def add_memory(payload: MemoryIn) -> dict[str, Any]:
    return save_memory(payload.content, payload.kind, payload.category, payload.importance)


@app.get("/api/skills")
def get_skills() -> list[dict[str, Any]]:
    return list_records("skills")


@app.get("/api/agents")
def get_agents() -> list[dict[str, Any]]:
    return list_records("agents")


@app.get("/api/tasks")
def get_tasks() -> list[dict[str, Any]]:
    return list_records("tasks")


@app.post("/api/skills")
def add_skill(payload: dict[str, Any]) -> dict[str, Any]:
    return save_skill(payload)


@app.post("/api/agents")
def add_agent(payload: dict[str, Any]) -> dict[str, Any]:
    return save_agent(payload)


@app.post("/api/agents/{agent_id}/run")
async def execute_agent(agent_id: int, payload: AgentRunIn) -> dict[str, Any]:
    from jarvis.agents import run_agent

    agent = next((item for item in list_records("agents") if item["id"] == agent_id), None)
    if not agent:
        raise HTTPException(404, "Агент не найден")
    for permission_name in agent.get("permissions", []):
        require(str(permission_name))
    settings = load_settings()

    async def execute(step: str) -> dict[str, Any]:
        return await respond(settings, memory.history(), step)

    return await run_agent(
        agent,
        payload.goal,
        settings,
        execute,
        max_steps=payload.max_steps,
        timeout=payload.timeout,
        retry_limit=payload.retry_limit,
    )


@app.post("/api/tasks")
def add_task(payload: dict[str, Any]) -> dict[str, Any]:
    return save_task(payload)


@app.delete("/api/{collection}/{record_id}")
def remove_record(collection: str, record_id: int) -> dict[str, bool]:
    if collection not in {"memory", "skills", "agents", "tasks"}:
        raise HTTPException(404, "Раздел не найден")
    table = "memories" if collection == "memory" else collection
    return {"deleted": delete_record(table, record_id)}


@app.get("/api/permissions")
def permissions() -> list[dict[str, object]]:
    return list_permissions()


@app.put("/api/permissions/{name}")
def permission(name: str, payload: PermissionIn) -> dict[str, object]:
    try:
        return set_permission(name, payload.enabled)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/diagnostics")
def diagnostics() -> dict[str, Any]:
    return run_diagnostics()


@app.post("/api/backup")
def backup() -> dict[str, str]:
    return {"path": str(create_backup())}


@app.post("/api/restore")
def restore(payload: BackupIn) -> dict[str, str]:
    require("WRITE_FILES")
    if not payload.confirmed:
        raise HTTPException(400, "Восстановление требует явного подтверждения")
    restore_backup(Path(payload.path))
    return {"status": "restored"}


@app.get("/api/logs")
def logs() -> list[dict[str, Any]]:
    from jarvis.storage import rows

    return rows("audit_log")[:500]


@app.post("/api/tools/files")
def file_tool(payload: FileToolIn) -> Any:
    from jarvis import file_agent

    operations = {
        "find": lambda: file_agent.find_files(payload.path, payload.pattern, payload.content),
        "read": lambda: {"content": file_agent.read_text(payload.path)},
        "write": lambda: file_agent.write_text(payload.path, payload.content, overwrite=payload.confirmed),
        "copy": lambda: file_agent.copy_or_move(payload.path, payload.destination),
        "move": lambda: file_agent.copy_or_move(payload.path, payload.destination, move=True),
        "archive": lambda: file_agent.archive(payload.paths, payload.destination),
        "duplicates": lambda: file_agent.duplicate_groups(payload.path),
        "delete": lambda: file_agent.delete(payload.path, confirmed=payload.confirmed),
    }
    if payload.operation not in operations:
        raise HTTPException(400, "Неизвестная файловая операция")
    return operations[payload.operation]()


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
        require("SCREEN_CONTROL" if action == "screenshot" else "SYSTEM_SETTINGS")
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
