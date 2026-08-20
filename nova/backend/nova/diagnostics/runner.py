"""NOVA diagnostics system."""

from __future__ import annotations

import os
import platform
from pathlib import Path

import psutil

from nova.ai.manager import get_ai_manager
from nova.core.config import get_settings
from nova.core.logging import get_logger
from nova.database.db import init_db, get_session
from nova.memory.store import get_memory_store
from nova.security.permissions import get_permission_manager
from nova.skills.manager import get_skill_manager
from nova.agents.manager import get_agent_manager
from nova.tools.registry import get_tool_registry
from nova.voice.pipeline import get_voice_pipeline

logger = get_logger("nova.diagnostics")


class DiagnosticsRunner:
    async def run_all(self) -> dict:
        checks = []
        checks.append(await self._check_database())
        checks.append(await self._check_memory())
        checks.append(await self._check_tools())
        checks.append(await self._check_permissions())
        checks.append(await self._check_ai())
        checks.append(await self._check_voice())
        checks.append(await self._check_network())
        checks.append(await self._check_disk())
        checks.append(await self._check_runtime())
        checks.append(await self._check_skills())
        checks.append(await self._check_agents())

        passed = sum(1 for c in checks if c["status"] == "PASS")
        warnings = sum(1 for c in checks if c["status"] == "WARNING")
        failed = sum(1 for c in checks if c["status"] == "FAIL")

        overall = "PASS"
        if failed > 0:
            overall = "FAIL"
        elif warnings > 0:
            overall = "WARNING"

        return {
            "overall": overall,
            "summary": {"pass": passed, "warning": warnings, "fail": failed},
            "checks": checks,
        }

    async def _check_database(self) -> dict:
        try:
            init_db()
            with get_session() as session:
                session.execute(__import__("sqlalchemy").text("SELECT 1"))
            return {"name": "Database", "status": "PASS", "message": "SQLite работает"}
        except Exception as e:
            return {"name": "Database", "status": "FAIL", "message": str(e)}

    async def _check_memory(self) -> dict:
        try:
            store = get_memory_store()
            count = len(store.list_all(limit=1))
            return {"name": "Memory", "status": "PASS", "message": f"Memory store OK"}
        except Exception as e:
            return {"name": "Memory", "status": "FAIL", "message": str(e)}

    async def _check_tools(self) -> dict:
        registry = get_tool_registry()
        tools = registry.list_tools()
        return {"name": "Tools", "status": "PASS", "message": f"{len(tools)} tools registered"}

    async def _check_permissions(self) -> dict:
        pm = get_permission_manager()
        perms = pm.list_permissions()
        return {"name": "Permissions", "status": "PASS", "message": f"{len(perms)} permissions configured"}

    async def _check_ai(self) -> dict:
        ai = get_ai_manager()
        results = await ai.health_check()
        local = next((r for r in results if r["provider"] == "local"), None)
        if local and local["available"]:
            return {"name": "AI Provider", "status": "PASS", "message": "Local provider available"}
        return {"name": "AI Provider", "status": "WARNING", "message": "Only cloud providers may be unavailable"}

    async def _check_voice(self) -> dict:
        voice = get_voice_pipeline()
        status = voice.get_status()
        if status["microphone_available"]:
            return {"name": "Voice", "status": "PASS", "message": "Voice subsystem ready"}
        return {"name": "Voice", "status": "WARNING", "message": "Microphone unavailable — text mode active"}

    async def _check_network(self) -> dict:
        ai = get_ai_manager()
        online = await ai.check_network()
        if online:
            return {"name": "Network", "status": "PASS", "message": "Internet available"}
        return {"name": "Network", "status": "WARNING", "message": "Offline mode"}

    async def _check_disk(self) -> dict:
        settings = get_settings()
        free = psutil.disk_usage(str(settings.data_dir)).free / (1024**3)
        if free < 0.5:
            return {"name": "Disk", "status": "FAIL", "message": f"Low disk space: {free:.1f} GB"}
        return {"name": "Disk", "status": "PASS", "message": f"{free:.1f} GB free"}

    async def _check_runtime(self) -> dict:
        return {
            "name": "Runtime",
            "status": "PASS",
            "message": f"Python {platform.python_version()} on {platform.system()}",
        }

    async def _check_skills(self) -> dict:
        skills = get_skill_manager().list_all()
        return {"name": "Skills", "status": "PASS", "message": f"{len(skills)} skills"}

    async def _check_agents(self) -> dict:
        agents = get_agent_manager().list_all()
        return {"name": "Agents", "status": "PASS", "message": f"{len(agents)} agents"}


_runner: DiagnosticsRunner | None = None


def get_diagnostics() -> DiagnosticsRunner:
    global _runner
    if _runner is None:
        _runner = DiagnosticsRunner()
    return _runner
