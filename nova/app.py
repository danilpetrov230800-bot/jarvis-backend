"""
NOVA HTTP & WebSocket Desktop Server API
FastAPI endpoints serving GUI and desktop RPC
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from nova.agents import AgentDefinition, agent_manager
from nova.config import AppSettings, STATIC_DIR
from nova.core import nova_core
from nova.database import db
from nova.diagnostics import diagnostics_manager
from nova.memory import memory_manager
from nova.research import research_engine
from nova.security import security_manager
from nova.skills import skills_engine
from nova.tasks import task_manager
from nova.tools import (
    capture_screenshot,
    create_archive,
    delete_file_safe,
    evaluate_math,
    find_files,
    get_system_metrics,
    list_notes,
    list_processes,
    open_application,
    read_file_safe,
    search_file_content,
    unpack_archive,
    write_file_safe,
)
from nova.voice import voice_manager

app = FastAPI(title="NOVA Desktop Assistant", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# --- Models ---
class ChatInput(BaseModel):
    message: str
    source: str = "text"
    confirmed: bool = False


class MemoryCreateInput(BaseModel):
    category: str = "long_term"
    title: str
    content: str
    importance: int = 1
    metadata: dict[str, Any] = {}


class SkillCreateInput(BaseModel):
    name: str
    description: str = ""
    trigger_type: str = "phrase"
    trigger_value: str
    actions: list[dict[str, Any]]
    conditions: list[str] = []
    permissions: list[str] = []


class AgentCreateInput(BaseModel):
    id: str | None = None
    name: str
    role: str
    system_prompt: str
    model: str = "default"
    tools: list[str] = []
    permissions: list[str] = []
    enabled: bool = True


class AgentRunInput(BaseModel):
    agent_id: str
    task_prompt: str


class ResearchInput(BaseModel):
    query: str
    target_type: str = "general"


class FileReadInput(BaseModel):
    path: str


class FileWriteInput(BaseModel):
    path: str
    content: str
    confirmed: bool = False


class FileDeleteInput(BaseModel):
    path: str
    confirmed: bool = False


class TTSInput(BaseModel):
    text: str
    voice: str | None = None
    rate: str = "+10%"


# --- Routes ---

@app.get("/")
async def root():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"name": "NOVA Desktop Assistant", "status": "running"}


@app.get("/api/status")
async def get_status():
    return {
        "status": "online",
        "app_name": "NOVA",
        "version": "1.0.0",
        "settings": nova_core.settings.model_dump(),
        "system": get_system_metrics()
    }


@app.post("/api/chat")
async def chat_endpoint(payload: ChatInput):
    result = await nova_core.process_user_input(
        text=payload.message,
        source=payload.source,
        confirmed=payload.confirmed
    )
    return result


# --- Voice Endpoints ---
@app.post("/api/voice/tts")
async def tts_endpoint(payload: TTSInput):
    voice = payload.voice or nova_core.settings.voice.voice
    data, mime = await voice_manager.synthesize_speech(payload.text, voice=voice, rate=payload.rate)
    if not data:
        raise HTTPException(status_code=500, detail="TTS synthesis failed")
    return Response(content=data, media_type=mime)


@app.get("/api/voice/voices")
async def list_voices_endpoint():
    return voice_manager.get_available_voices()


# --- Memory Endpoints ---
@app.get("/api/memory")
async def list_memory(category: str | None = None, query: str | None = None):
    return memory_manager.list_all(category=category, query=query) # type: ignore


@app.post("/api/memory")
async def create_memory(payload: MemoryCreateInput):
    item = memory_manager.add(
        category=payload.category, # type: ignore
        title=payload.title,
        content=payload.content,
        importance=payload.importance,
        metadata=payload.metadata
    )
    return item


@app.delete("/api/memory/{item_id}")
async def delete_memory(item_id: str):
    success = memory_manager.delete(item_id)
    return {"success": success}


@app.get("/api/memory/export")
async def export_memory():
    return memory_manager.export_json()


@app.post("/api/memory/import")
async def import_memory(payload: dict[str, Any]):
    count = memory_manager.import_json(payload)
    return {"imported_count": count}


# --- Skills Endpoints ---
@app.get("/api/skills")
async def list_skills():
    return skills_engine.list_skills()


@app.post("/api/skills")
async def create_skill(payload: SkillCreateInput):
    skill = skills_engine.create_skill(
        name=payload.name,
        description=payload.description,
        trigger_type=payload.trigger_type,
        trigger_value=payload.trigger_value,
        actions=payload.actions,
        conditions=payload.conditions,
        permissions=payload.permissions
    )
    return skill


@app.post("/api/skills/{skill_id}/run")
async def run_skill(skill_id: str):
    skill = skills_engine.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    res = await skills_engine.execute_skill(skill)
    return res


@app.delete("/api/skills/{skill_id}")
async def delete_skill(skill_id: str):
    return {"success": skills_engine.delete_skill(skill_id)}


# --- Multi-Agent Endpoints ---
@app.get("/api/agents")
async def list_agents():
    return agent_manager.list_agents()


@app.post("/api/agents")
async def create_agent(payload: AgentCreateInput):
    agent = AgentDefinition(
        id=payload.id or f"agent_{int(time.time())}",
        name=payload.name,
        role=payload.role,
        system_prompt=payload.system_prompt,
        model=payload.model,
        tools=payload.tools,
        permissions=payload.permissions,
        enabled=payload.enabled
    )
    agent_manager.save_agent(agent)
    return agent


@app.post("/api/agents/run")
async def run_agent(payload: AgentRunInput):
    res = await agent_manager.run_agent_task(
        agent_id=payload.agent_id,
        task_prompt=payload.task_prompt,
        ai_settings=nova_core.settings.ai
    )
    return res


# --- Local Tools API ---
@app.get("/api/tools/files/search")
async def tool_search_files(query: str = "", extension: str | None = None):
    return find_files(query=query, extension=extension)


@app.post("/api/tools/files/read")
async def tool_read_file(payload: FileReadInput):
    return read_file_safe(payload.path)


@app.post("/api/tools/files/write")
async def tool_write_file(payload: FileWriteInput):
    return write_file_safe(payload.path, payload.content, confirmed=payload.confirmed)


@app.post("/api/tools/files/delete")
async def tool_delete_file(payload: FileDeleteInput):
    return delete_file_safe(payload.path, confirmed=payload.confirmed)


@app.get("/api/tools/system/metrics")
async def tool_system_metrics():
    return get_system_metrics()


@app.get("/api/tools/system/processes")
async def tool_system_processes(limit: int = 15, sort_by: str = "memory"):
    return list_processes(limit=limit, sort_by=sort_by)


@app.post("/api/tools/system/screenshot")
async def tool_screenshot():
    return capture_screenshot()


# --- Research Mode Endpoints ---
@app.post("/api/research/query")
async def research_query(payload: ResearchInput):
    return await research_engine.run_investigation(payload.query, payload.target_type)


@app.get("/api/research/history")
async def research_history():
    return research_engine.list_past_investigations()


# --- Tasks Endpoints ---
@app.get("/api/tasks")
async def list_tasks(status: str | None = None):
    return task_manager.list_tasks(status=status)


@app.post("/api/tasks")
async def create_task(payload: dict[str, Any]):
    return task_manager.create_task(
        title=payload.get("title", "New Task"),
        task_type=payload.get("task_type", "one_time"),
        scheduled_at=payload.get("scheduled_at"),
        schedule_cron=payload.get("schedule_cron", ""),
        payload=payload.get("payload", {})
    )


# --- Diagnostics & Backup Endpoints ---
@app.get("/api/diagnostics/run")
async def run_diagnostics():
    return await diagnostics_manager.run_full_diagnostics(nova_core.settings)


@app.post("/api/backup/create")
async def create_backup():
    bck = db.create_backup(label="manual")
    return {"success": True, "backup_file": str(bck)}


@app.get("/api/settings")
async def get_settings():
    return nova_core.settings


@app.post("/api/settings")
async def update_settings(new_settings: AppSettings):
    nova_core.save_settings(new_settings)
    return {"success": True, "settings": nova_core.settings}


@app.get("/api/logs")
async def get_audit_logs(limit: int = 100):
    with db.get_connection() as conn:
        cur = conn.execute("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT ?", (limit,))
        return [dict(r) for r in cur.fetchall()]
