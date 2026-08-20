from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from nova import __version__
from nova.errors import ConfirmationRequired, NovaError, PermissionDenied
from nova.kernel import NovaKernel
from nova.paths import static_dir
from nova.voice.pipeline import list_voices, synthesize

kernel = NovaKernel()
STATIC = static_dir()

app = FastAPI(title="NOVA", version=__version__, docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(PermissionDenied)
async def denied_handler(_, exc: PermissionDenied):
    from fastapi.responses import JSONResponse

    return JSONResponse({"ok": False, "reply": exc.user_message, "detail": exc.user_message}, status_code=403)


@app.exception_handler(ConfirmationRequired)
async def confirm_handler(_, exc: ConfirmationRequired):
    from fastapi.responses import JSONResponse

    return JSONResponse(
        {
            "ok": False,
            "needs_confirmation": True,
            "confirmation_token": exc.token,
            "confirmation_summary": exc.summary,
            "reply": exc.summary,
        }
    )


@app.exception_handler(NovaError)
async def nova_handler(_, exc: NovaError):
    from fastapi.responses import JSONResponse

    return JSONResponse({"ok": False, "reply": exc.user_message}, status_code=400)


class ChatIn(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    source: str = "text"


class SettingsIn(BaseModel):
    model_config = {"extra": "allow"}


class SpeakIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    voice: str | None = None


class ToolIn(BaseModel):
    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class ConfirmIn(BaseModel):
    token: str


class SkillIn(BaseModel):
    model_config = {"extra": "allow"}


class AgentIn(BaseModel):
    model_config = {"extra": "allow"}


class MemoryIn(BaseModel):
    content: str
    kind: str = "long_term"
    category: str = "general"
    title: str = ""
    importance: int = 3
    tags: str = ""


class TaskIn(BaseModel):
    title: str
    kind: str = "one-time"
    payload: dict[str, Any] = Field(default_factory=dict)
    schedule: str = ""
    delay_seconds: int | None = None


class ResearchIn(BaseModel):
    identifier: str = ""
    query: str = ""


class BackupIn(BaseModel):
    include_secrets: bool = False
    path: str = ""


class PermissionIn(BaseModel):
    key: str
    allowed: bool


def _user_error(exc: Exception) -> HTTPException:
    kernel.log.error("api error", error=str(exc))
    return HTTPException(status_code=400, detail="Не удалось выполнить действие.")


@app.get("/health")
@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/api/status")
def status() -> dict[str, Any]:
    return kernel.snapshot()


@app.get("/api/settings")
def get_settings() -> dict[str, Any]:
    return kernel.settings.public()


@app.post("/api/settings")
def update_settings(payload: SettingsIn) -> dict[str, Any]:
    patch = {k: v for k, v in payload.model_dump().items() if v is not None}
    kernel.settings.update(patch)
    return kernel.settings.public()


@app.post("/api/settings/delete-key")
def delete_key() -> dict[str, Any]:
    kernel.secrets.delete("NOVA_API_KEY")
    return kernel.settings.public()


@app.post("/api/chat")
async def chat(payload: ChatIn) -> dict[str, Any]:
    return await kernel.handle_chat(payload.text, source=payload.source)


@app.post("/chat")
async def legacy_chat(payload: ChatIn) -> dict[str, Any]:
    result = await kernel.handle_chat(payload.text, source=payload.source)
    return {"reply": result.get("reply"), **result}


@app.post("/api/reset")
def reset_chat() -> dict[str, str]:
    kernel.memory.conversation_clear()
    return {"status": "cleared"}


@app.get("/api/conversation")
def conversation() -> dict[str, Any]:
    return {"messages": kernel.memory.conversation(80)}


@app.get("/api/voices")
async def voices() -> dict[str, Any]:
    return {"voices": await list_voices()}


@app.post("/api/speak")
async def speak(payload: SpeakIn) -> Response:
    settings = kernel.settings.current
    audio, mime = await synthesize(payload.text, voice=payload.voice or settings.tts_voice, rate=settings.tts_rate)
    if not audio:
        raise HTTPException(status_code=502, detail="Не удалось синтезировать речь")
    kernel.echo.mark_spoken(payload.text, duration_ms=max(800, len(payload.text) * 40))
    return Response(content=audio, media_type=mime, headers={"Cache-Control": "private, max-age=86400"})


@app.post("/api/wake")
async def wake(payload: ChatIn) -> dict[str, Any]:
    from nova.voice.pipeline import is_wake_word

    heard = payload.text
    if kernel.echo.blocked(heard):
        return {"wake": False, "reason": "echo_guard"}
    wake = is_wake_word(heard, kernel.settings.current.wake_words, kernel.settings.current.wake_sensitivity)
    return {"wake": wake}


@app.get("/api/tools")
def tools() -> dict[str, Any]:
    return {"tools": kernel.tools.list_public()}


@app.post("/api/tools/run")
async def run_tool(payload: ToolIn) -> dict[str, Any]:
    return await kernel.tools.run(payload.name, payload.args)


@app.post("/api/confirm")
async def confirm(payload: ConfirmIn) -> dict[str, Any]:
    info = kernel.permissions.confirm(payload.token)
    action = info["action"]
    data = info["payload"]
    data["confirmed"] = True
    if action in kernel.tools.names():
        return await kernel.tools.run(action, data)
    if action == "delete_file":
        return await kernel.tools.run("delete_file", data)
    return {"ok": True, "reply": "Подтверждено.", "action": action}


@app.get("/api/permissions")
def permissions() -> dict[str, Any]:
    return {"permissions": kernel.permissions.all()}


@app.post("/api/permissions")
def set_permission(payload: PermissionIn) -> dict[str, Any]:
    kernel.permissions.set(payload.key, payload.allowed)
    return {"permissions": kernel.permissions.all()}


@app.get("/api/memory")
def memory_list(kind: str | None = None, q: str | None = None) -> dict[str, Any]:
    return {"items": kernel.memory.list(kind=kind, query=q)}


@app.post("/api/memory")
def memory_add(payload: MemoryIn) -> dict[str, Any]:
    return kernel.memory.add(
        payload.content,
        kind=payload.kind,
        category=payload.category,
        title=payload.title,
        importance=payload.importance,
        tags=payload.tags,
    )


@app.post("/api/memory/clear")
def memory_clear(kind: str | None = None) -> dict[str, Any]:
    return {"deleted": kernel.memory.clear(kind)}


@app.post("/api/memory/{memory_id}")
def memory_update(memory_id: int, payload: MemoryIn) -> dict[str, Any]:
    return kernel.memory.update(
        memory_id,
        content=payload.content,
        kind=payload.kind,
        category=payload.category,
        title=payload.title,
        importance=payload.importance,
        tags=payload.tags,
    )


@app.delete("/api/memory/{memory_id}")
def memory_delete(memory_id: int) -> dict[str, str]:
    kernel.memory.delete(memory_id)
    return {"status": "deleted"}


@app.get("/api/memory/export")
def memory_export() -> dict[str, Any]:
    return {"items": kernel.memory.export()}


@app.post("/api/memory/import")
def memory_import(payload: dict[str, Any]) -> dict[str, Any]:
    return {"imported": kernel.memory.import_rows(payload.get("items") or [])}


@app.get("/api/skills")
def skills() -> dict[str, Any]:
    return {"skills": kernel.skills.list()}


@app.post("/api/skills")
def skill_create(payload: SkillIn) -> dict[str, Any]:
    return kernel.skills.create(payload.model_dump())


@app.post("/api/skills/{skill_id}")
def skill_update(skill_id: int, payload: SkillIn) -> dict[str, Any]:
    return kernel.skills.update(skill_id, payload.model_dump())


@app.delete("/api/skills/{skill_id}")
def skill_delete(skill_id: int) -> dict[str, str]:
    kernel.skills.delete(skill_id)
    return {"status": "deleted"}


@app.post("/api/skills/{skill_id}/test")
async def skill_test(skill_id: int) -> dict[str, Any]:
    skill = kernel.skills.get(skill_id)
    return await kernel.handle_chat(skill["trigger"] or skill["name"], source="skill-test")


@app.get("/api/agents")
def agents() -> dict[str, Any]:
    return {"agents": kernel.agents.list()}


@app.post("/api/agents")
def agent_create(payload: AgentIn) -> dict[str, Any]:
    return kernel.agents.create(payload.model_dump())


@app.post("/api/agents/run")
async def agent_run(payload: ChatIn) -> dict[str, Any]:
    run = await kernel.agent_runtime.run(payload.text)
    return {
        "status": run.status,
        "result": run.result,
        "error": run.error,
        "steps": kernel.agent_runtime.visualize(run),
    }


@app.post("/api/agents/{agent_id}")
def agent_update(agent_id: int, payload: AgentIn) -> dict[str, Any]:
    return kernel.agents.update(agent_id, payload.model_dump())


@app.delete("/api/agents/{agent_id}")
def agent_delete(agent_id: int) -> dict[str, str]:
    kernel.agents.delete(agent_id)
    return {"status": "deleted"}


@app.get("/api/tasks")
def tasks() -> dict[str, Any]:
    return {"tasks": kernel.tasks.list()}


@app.post("/api/tasks")
def task_create(payload: TaskIn) -> dict[str, Any]:
    return kernel.tasks.create(payload.title, payload.kind, payload.payload, payload.schedule, payload.delay_seconds)


@app.post("/api/tasks/{task_id}/cancel")
def task_cancel(task_id: int) -> dict[str, Any]:
    return kernel.tasks.set_status(task_id, "cancelled")


@app.post("/api/tasks/{task_id}/pause")
def task_pause(task_id: int) -> dict[str, Any]:
    return kernel.tasks.set_status(task_id, "paused")


@app.get("/api/notifications")
def notifications() -> dict[str, Any]:
    return {"items": kernel.notify.list()}


@app.post("/api/research")
async def research(payload: ResearchIn) -> dict[str, Any]:
    if not kernel.settings.current.research_enabled:
        raise HTTPException(status_code=403, detail="Режим исследования выключен в настройках.")
    kernel.permissions.require("RESEARCH")
    if payload.identifier:
        result = await kernel.research.search_profiles(payload.identifier)
    else:
        result = await kernel.research.analyze(payload.query or "open source")
    return result.as_dict()


@app.get("/api/logs")
def logs() -> dict[str, Any]:
    return {"lines": kernel.log.tail(400)}


@app.post("/api/logs/export")
def logs_export() -> dict[str, Any]:
    path = kernel.log.export()
    return {"path": str(path)}


@app.post("/api/diagnostics")
async def diagnostics() -> dict[str, Any]:
    return await kernel.diagnostics.run()


@app.get("/api/backup")
def backups() -> dict[str, Any]:
    return {"items": kernel.backup.list()}


@app.post("/api/backup")
def backup_create(payload: BackupIn) -> dict[str, Any]:
    path = kernel.backup.create(include_secrets=payload.include_secrets)
    return {"path": str(path)}


@app.post("/api/restore")
def backup_restore(payload: BackupIn) -> dict[str, str]:
    from pathlib import Path

    if not payload.path:
        raise HTTPException(status_code=400, detail="Укажите файл резервной копии.")
    kernel.backup.restore(Path(payload.path), include_secrets=payload.include_secrets)
    return {"status": "restored"}


@app.get("/api/updates")
def updates() -> dict[str, str]:
    return kernel.updates.current()


@app.post("/api/first-run/complete")
def first_run_done() -> dict[str, Any]:
    kernel.settings.update({"first_run_complete": True})
    return kernel.settings.public()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


if STATIC.exists():
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
