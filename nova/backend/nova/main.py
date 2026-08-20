"""FastAPI application for NOVA backend."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from nova.agents.manager import get_agent_manager
from nova.ai.manager import get_ai_manager
from nova.backup.manager import get_backup_manager
from nova.core.config import get_settings
from nova.core.engine import get_engine
from nova.core.logging import get_logger, setup_logging
from nova.diagnostics.runner import get_diagnostics
from nova.memory.store import get_memory_store
from nova.research.mode import get_research_mode
from nova.security.permissions import get_permission_manager
from nova.security.secrets import get_secret_store
from nova.skills.manager import get_skill_manager
from nova.tasks.manager import get_task_manager
from nova.tools.registry import get_tool_registry
from nova.voice.pipeline import get_voice_pipeline

setup_logging()
logger = get_logger("nova.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = get_engine()
    await engine.initialize()
    logger.info("NOVA backend started on %s:%s", get_settings().host, get_settings().port)
    yield
    get_voice_pipeline().stop()
    logger.info("NOVA backend stopped")


app = FastAPI(title="NOVA API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    text: str
    confirmed: bool = False


class SettingsUpdate(BaseModel):
    data: dict[str, Any]


class SecretRequest(BaseModel):
    key: str
    value: str | None = None


class MemoryCreate(BaseModel):
    content: str
    type: str = "long-term"
    category: str = "general"
    importance: int = 5


class SkillCreate(BaseModel):
    name: str
    trigger: str
    actions: list[dict]
    description: str = ""
    conditions: list[dict] = Field(default_factory=list)
    enabled: bool = True


class AgentCreate(BaseModel):
    name: str
    role: str
    instructions: str = ""
    model: str = "local"
    tools: list[str] = Field(default_factory=list)
    enabled: bool = True


class TaskCreate(BaseModel):
    title: str
    type: str = "one-time"
    schedule: str = ""
    payload: dict = Field(default_factory=dict)


class ToolExecute(BaseModel):
    name: str
    params: dict = Field(default_factory=dict)
    confirmed: bool = False


class AgentTaskRequest(BaseModel):
    task: str
    agent_id: int | None = None


@app.get("/")
def root():
    return {"status": "NOVA online", "version": get_settings().version}


@app.get("/api/status")
async def status():
    return get_engine().get_status()


@app.post("/api/chat")
async def chat(req: ChatRequest):
    reply = await get_engine().process_message(req.text, req.confirmed)
    return {"reply": reply}


@app.get("/api/settings")
async def get_settings_api():
    return get_engine().get_settings_dict()


@app.put("/api/settings")
async def update_settings(req: SettingsUpdate):
    return await get_engine().update_settings(req.data)


@app.post("/api/secrets")
async def set_secret(req: SecretRequest):
    store = get_secret_store()
    if req.value is None:
        store.delete(req.key)
        return {"deleted": req.key}
    store.set(req.key, req.value)
    return {"stored": req.key}


@app.get("/api/secrets/{key}/exists")
async def secret_exists(key: str):
    return {"exists": get_secret_store().has(key)}


@app.get("/api/memory")
async def list_memory(type: str | None = None):
    return get_memory_store().list_all(type=type)


@app.post("/api/memory")
async def create_memory(req: MemoryCreate):
    return get_memory_store().create(
        content=req.content, type=req.type, category=req.category, importance=req.importance
    )


@app.get("/api/memory/search")
async def search_memory(q: str):
    return get_memory_store().search(q)


@app.put("/api/memory/{memory_id}")
async def update_memory(memory_id: int, data: dict):
    result = get_memory_store().update(memory_id, **data)
    if not result:
        raise HTTPException(404, "Memory not found")
    return result


@app.delete("/api/memory/{memory_id}")
async def delete_memory(memory_id: int):
    if not get_memory_store().delete(memory_id):
        raise HTTPException(404, "Memory not found")
    return {"deleted": memory_id}


@app.get("/api/skills")
async def list_skills():
    return get_skill_manager().list_all()


@app.post("/api/skills")
async def create_skill(req: SkillCreate):
    return get_skill_manager().create(req.model_dump())


@app.put("/api/skills/{skill_id}")
async def update_skill(skill_id: int, data: dict):
    result = get_skill_manager().update(skill_id, data)
    if not result:
        raise HTTPException(404, "Skill not found")
    return result


@app.delete("/api/skills/{skill_id}")
async def delete_skill(skill_id: int):
    if not get_skill_manager().delete(skill_id):
        raise HTTPException(404, "Skill not found")
    return {"deleted": skill_id}


@app.post("/api/skills/{skill_id}/execute")
async def execute_skill(skill_id: int):
    return await get_skill_manager().execute(skill_id)


@app.post("/api/skills/{skill_id}/test")
async def test_skill(skill_id: int):
    return await get_skill_manager().test(skill_id)


@app.get("/api/agents")
async def list_agents():
    return get_agent_manager().list_all()


@app.post("/api/agents")
async def create_agent(req: AgentCreate):
    return get_agent_manager().create(req.model_dump())


@app.put("/api/agents/{agent_id}")
async def update_agent(agent_id: int, data: dict):
    result = get_agent_manager().update(agent_id, data)
    if not result:
        raise HTTPException(404, "Agent not found")
    return result


@app.delete("/api/agents/{agent_id}")
async def delete_agent(agent_id: int):
    if not get_agent_manager().delete(agent_id):
        raise HTTPException(404, "Agent not found")
    return {"deleted": agent_id}


@app.post("/api/agents/run")
async def run_agent_task(req: AgentTaskRequest):
    return await get_agent_manager().run_task(req.task, req.agent_id)


@app.get("/api/tools")
async def list_tools():
    return get_tool_registry().list_tools()


@app.post("/api/tools/execute")
async def execute_tool(req: ToolExecute):
    return await get_tool_registry().execute(req.name, req.params, confirmed=req.confirmed)


@app.get("/api/permissions")
async def list_permissions():
    return get_permission_manager().list_permissions()


@app.put("/api/permissions/{name}")
async def set_permission(name: str, data: dict):
    get_permission_manager().set_enabled(name, data.get("enabled", False))
    return {"name": name, "enabled": data.get("enabled", False)}


@app.get("/api/tasks")
async def list_tasks():
    return get_task_manager().list_all()


@app.post("/api/tasks")
async def create_task(req: TaskCreate):
    return get_task_manager().create(req.model_dump())


@app.put("/api/tasks/{task_id}/status")
async def update_task_status(task_id: int, data: dict):
    result = get_task_manager().update_status(task_id, data.get("status", "pending"))
    if not result:
        raise HTTPException(404, "Task not found")
    return result


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: int):
    if not get_task_manager().delete(task_id):
        raise HTTPException(404, "Task not found")
    return {"deleted": task_id}


@app.get("/api/diagnostics")
async def run_diagnostics():
    return await get_diagnostics().run_all()


@app.post("/api/backup")
async def create_backup(include_secrets: bool = False):
    path = get_backup_manager().create_backup(include_secrets)
    return {"path": path}


@app.get("/api/backups")
async def list_backups():
    return get_backup_manager().list_backups()


@app.post("/api/restore")
async def restore_backup(data: dict):
    return get_backup_manager().restore_backup(data["path"])


@app.get("/api/voice/status")
async def voice_status():
    return get_voice_pipeline().get_status()


@app.post("/api/voice/test/microphone")
async def test_microphone():
    return await get_voice_pipeline().test_microphone()


@app.post("/api/voice/test/tts")
async def test_tts():
    return await get_voice_pipeline().test_tts()


@app.post("/api/voice/start")
async def start_voice():
    get_voice_pipeline().start()
    return {"started": True}


@app.post("/api/voice/stop")
async def stop_voice():
    get_voice_pipeline().stop()
    return {"stopped": True}


@app.post("/api/research/search")
async def research_search(data: dict):
    try:
        return await get_research_mode().search_public_profiles(data.get("query", ""))
    except PermissionError as e:
        raise HTTPException(403, str(e))


@app.get("/api/logs/export")
async def export_logs():
    settings = get_settings()
    log_file = settings.logs_dir / "nova.log"
    if log_file.exists():
        return {"content": log_file.read_text(encoding="utf-8", errors="replace")}
    return {"content": ""}


@app.get("/api/ai/providers")
async def list_ai_providers():
    return get_ai_manager().list_providers()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    engine = get_engine()
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "chat":
                reply = await engine.process_message(data.get("text", ""), data.get("confirmed", False))
                await websocket.send_json({"type": "reply", "text": reply})
            elif data.get("type") == "status":
                await websocket.send_json({"type": "status", "data": engine.get_status()})
    except WebSocketDisconnect:
        pass


def main():
    import uvicorn
    settings = get_settings()
    uvicorn.run("nova.main:app", host=settings.host, port=settings.port, log_level="info")


if __name__ == "__main__":
    main()
