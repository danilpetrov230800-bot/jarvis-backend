from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from jarvis import agents_catalog, backup, diagnostics, files_agent, logs, memory_long, permissions, research, skills, tasks
from jarvis.apps import launch_named, list_apps
from jarvis.config import load_settings
from jarvis.desktop import system_info
from jarvis.store import recent_audit

router = APIRouter()


class MemoryIn(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    kind: str = "note"


class SkillIn(BaseModel):
    name: str = ""
    trigger: str = Field(min_length=1, max_length=200)
    action_text: str = ""
    actions: list[dict[str, str]] | None = None


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=400)
    seconds: int = 0


class FileSearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=200)


class FileCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    content: str = ""


class FileDeleteIn(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    confirm: bool = False


class AppOpenIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ResearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=500)


class AgentIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    role: str = ""
    instructions: str = ""
    tools: list[str] | None = None
    model: str = ""


class MemoryImportIn(BaseModel):
    items: list[dict[str, str]]


class RestoreIn(BaseModel):
    path: str = Field(min_length=1, max_length=500)


class BackupIn(BaseModel):
    include_secrets: bool = False


@router.get("/api/diagnostics")
def api_diagnostics() -> dict[str, Any]:
    checks = diagnostics.run_diagnostics()
    worst = "PASS"
    if any(item["status"] == "FAIL" for item in checks):
        worst = "FAIL"
    elif any(item["status"] == "WARNING" for item in checks):
        worst = "WARNING"
    return {"result": worst, "checks": checks}


@router.get("/api/logs")
def api_logs() -> dict[str, str]:
    return {"text": logs.tail_log()}


@router.get("/api/logs/export")
def api_logs_export() -> PlainTextResponse:
    return PlainTextResponse(
        logs.tail_log(2000),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=nova-log.txt"},
    )


@router.get("/api/audit")
def api_audit() -> dict[str, Any]:
    return {"items": recent_audit()}


@router.get("/api/memory-long")
def api_memory_list(q: str = "") -> dict[str, Any]:
    return {"items": memory_long.list_memories(query=q)}


@router.post("/api/memory-long")
def api_memory_add(payload: MemoryIn) -> dict[str, Any]:
    return memory_long.add_memory(payload.content, kind=payload.kind)


@router.delete("/api/memory-long/{ident}")
def api_memory_delete(ident: int) -> dict[str, bool]:
    ok = memory_long.delete_memory(ident)
    if not ok:
        raise HTTPException(status_code=404, detail="not found")
    return {"ok": True}


@router.get("/api/skills")
def api_skills() -> dict[str, Any]:
    return {"items": skills.list_skills()}


@router.post("/api/skills")
def api_skill_create(payload: SkillIn) -> dict[str, Any]:
    return skills.create_skill(payload.name or payload.trigger, payload.trigger, payload.actions, payload.action_text)


@router.post("/api/skills/{ident}/run")
def api_skill_run(ident: int) -> dict[str, Any]:
    result = skills.run_skill(ident=ident)
    return {"reply": result.reply, "tools": result.tools}


@router.post("/api/skills/{ident}/toggle")
def api_skill_toggle(ident: int) -> dict[str, Any]:
    return skills.toggle_skill(ident)


@router.delete("/api/skills/{ident}")
def api_skill_delete(ident: int) -> dict[str, bool]:
    if not skills.delete_skill(ident):
        raise HTTPException(status_code=404, detail="not found")
    return {"ok": True}


@router.get("/api/tasks")
def api_tasks() -> dict[str, Any]:
    return {"items": tasks.list_tasks()}


@router.post("/api/tasks")
def api_task_add(payload: TaskIn) -> dict[str, Any]:
    return tasks.add_task(payload.title, seconds=payload.seconds)


@router.post("/api/tasks/{ident}/cancel")
def api_task_cancel(ident: int) -> dict[str, bool]:
    if not tasks.cancel_task(ident):
        raise HTTPException(status_code=404, detail="not found")
    return {"ok": True}


@router.post("/api/files/search")
def api_files_search(payload: FileSearchIn) -> dict[str, Any]:
    try:
        items = files_agent.find_files(payload.query)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"items": items}


@router.post("/api/files/create")
def api_files_create(payload: FileCreateIn) -> dict[str, Any]:
    try:
        path = files_agent.create_file(payload.name, payload.content)
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"path": str(path)}


@router.post("/api/files/delete")
def api_files_delete(payload: FileDeleteIn) -> dict[str, Any]:
    try:
        reply = files_agent.delete_file(payload.path, confirm=payload.confirm)
    except (PermissionError, FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"reply": reply}


@router.get("/api/apps")
def api_apps() -> dict[str, Any]:
    return {"items": list_apps()}


@router.post("/api/apps/open")
def api_apps_open(payload: AppOpenIn) -> dict[str, str]:
    return {"reply": launch_named(payload.name)}


@router.get("/api/permissions")
def api_perms() -> dict[str, bool]:
    return permissions.load()


@router.post("/api/permissions")
def api_perms_save(payload: dict[str, bool]) -> dict[str, bool]:
    return permissions.save(payload)


@router.post("/api/backup")
def api_backup(payload: BackupIn | None = None) -> dict[str, str]:
    include = payload.include_secrets if payload else False
    path = backup.create_backup(include_secrets=include)
    return {"path": str(path)}


@router.post("/api/restore")
def api_restore(payload: RestoreIn) -> dict[str, str]:
    from pathlib import Path

    try:
        path = backup.restore_backup(Path(payload.path))
    except (PermissionError, FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"path": str(path)}


@router.post("/api/research")
async def api_research(payload: ResearchIn) -> dict[str, Any]:
    settings = load_settings()
    try:
        return await research.research(payload.query, region=settings.search_region)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/api/system")
def api_system() -> dict[str, str]:
    return {"reply": system_info()}


@router.get("/api/agents")
def api_agents() -> dict[str, Any]:
    return {"items": agents_catalog.list_agents()}


@router.post("/api/agents")
def api_agent_create(payload: AgentIn) -> dict[str, Any]:
    return agents_catalog.create_agent(
        payload.name,
        role=payload.role,
        instructions=payload.instructions,
        tools=payload.tools,
        model=payload.model,
    )


@router.post("/api/agents/{ident}/toggle")
def api_agent_toggle(ident: int) -> dict[str, Any]:
    try:
        return agents_catalog.toggle_agent(ident)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="not found") from exc


@router.delete("/api/agents/{ident}")
def api_agent_delete(ident: int) -> dict[str, bool]:
    if not agents_catalog.delete_agent(ident):
        raise HTTPException(status_code=404, detail="not found")
    return {"ok": True}


@router.post("/api/agents/{ident}/run")
async def api_agent_run(ident: int, payload: ResearchIn) -> dict[str, Any]:
    from jarvis.agent import run_agent

    try:
        agent = agents_catalog.get_agent(ident)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="not found") from exc
    if not agent["enabled"]:
        raise HTTPException(status_code=400, detail="агент выключен")
    return await run_agent(payload.query, region=load_settings().search_region, agent=agent)


@router.get("/api/backups")
def api_backups() -> dict[str, Any]:
    return {"items": backup.list_backups()}


@router.post("/api/files/zip")
def api_files_zip(payload: FileSearchIn) -> dict[str, str]:
    try:
        path = files_agent.make_zip(payload.query)
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"path": str(path)}


@router.get("/api/memory-long/export")
def api_memory_export() -> dict[str, Any]:
    return {"items": memory_long.list_memories(limit=500)}


@router.post("/api/memory-long/import")
def api_memory_import(payload: MemoryImportIn) -> dict[str, int]:
    count = 0
    for item in payload.items[:400]:
        content = (item.get("content") or "").strip()
        if not content:
            continue
        memory_long.add_memory(content, kind=item.get("kind") or "note")
        count += 1
    return {"imported": count}


@router.get("/api/updates")
def api_updates() -> dict[str, str]:
    return {
        "current": "1.5.0",
        "channel": "github-actions",
        "note": "Скачайте новый NOVA-Setup.exe. Память в профиле Windows не удаляется при обновлении.",
    }


@router.post("/api/settings/clear-key")
def api_clear_key() -> dict[str, Any]:
    from jarvis.config import clear_api_key, load_settings, public_settings

    return public_settings(clear_api_key(load_settings()))
