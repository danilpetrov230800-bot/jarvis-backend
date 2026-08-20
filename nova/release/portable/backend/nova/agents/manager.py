"""Multi-agent system for NOVA."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from nova.ai.manager import get_ai_manager
from nova.ai.provider import AIMessage
from nova.core.config import get_settings
from nova.core.logging import get_audit_log, get_logger
from nova.core.state import AgentProgress, NovaStatus, get_state
from nova.database.db import AgentRecord, get_session
from nova.tools.registry import get_tool_registry

logger = get_logger("nova.agents")
audit = get_audit_log()

DEFAULT_AGENTS = [
    {
        "name": "Research Agent",
        "role": "research",
        "instructions": "Ищи и анализируй информацию из доступных источников.",
        "tools": ["web_search", "file_search"],
    },
    {
        "name": "File Agent",
        "role": "file",
        "instructions": "Управляй файлами: поиск, организация, архивирование.",
        "tools": ["file_search", "file_read", "file_write", "file_delete"],
    },
    {
        "name": "System Agent",
        "role": "system",
        "instructions": "Анализируй состояние системы и объясняй проблемы.",
        "tools": ["system_info", "process_list", "disk_info"],
    },
]


class AgentManager:
    def __init__(self):
        self.settings = get_settings()
        self._seed_defaults()

    def _seed_defaults(self):
        with get_session() as session:
            if session.query(AgentRecord).count() == 0:
                for agent in DEFAULT_AGENTS:
                    session.add(AgentRecord(
                        name=agent["name"],
                        role=agent["role"],
                        instructions=agent["instructions"],
                        tools_json=json.dumps(agent["tools"]),
                        enabled=True,
                    ))
                session.commit()

    def create(self, data: dict) -> dict:
        now = datetime.now(timezone.utc)
        with get_session() as session:
            record = AgentRecord(
                name=data["name"],
                role=data["role"],
                instructions=data.get("instructions", ""),
                model=data.get("model", "local"),
                tools_json=json.dumps(data.get("tools", [])),
                permissions_json=json.dumps(data.get("permissions", [])),
                enabled=data.get("enabled", True),
                created_at=now,
                updated_at=now,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return self._to_dict(record)

    def get(self, agent_id: int) -> dict | None:
        with get_session() as session:
            record = session.get(AgentRecord, agent_id)
            return self._to_dict(record) if record else None

    def list_all(self) -> list[dict]:
        with get_session() as session:
            records = session.query(AgentRecord).all()
            return [self._to_dict(r) for r in records]

    def update(self, agent_id: int, data: dict) -> dict | None:
        with get_session() as session:
            record = session.get(AgentRecord, agent_id)
            if not record:
                return None
            for key in ("name", "role", "instructions", "model", "enabled"):
                if key in data:
                    setattr(record, key, data[key])
            if "tools" in data:
                record.tools_json = json.dumps(data["tools"])
            record.updated_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(record)
            return self._to_dict(record)

    def delete(self, agent_id: int) -> bool:
        with get_session() as session:
            record = session.get(AgentRecord, agent_id)
            if not record:
                return False
            session.delete(record)
            session.commit()
            return True

    def find_by_role(self, role: str) -> dict | None:
        for agent in self.list_all():
            if agent["role"] == role and agent["enabled"]:
                return agent
        return None

    async def run_task(
        self,
        task: str,
        agent_id: int | None = None,
        max_steps: int | None = None,
    ) -> dict:
        settings = self.settings
        max_steps = max_steps or settings.agent_max_steps
        timeout = settings.agent_timeout_sec
        retry_limit = settings.agent_retry_limit

        agent = self.get(agent_id) if agent_id else self.find_by_role("system")
        task_id = str(uuid.uuid4())[:8]
        state = get_state()

        progress = AgentProgress(
            task_id=task_id,
            title=task[:100],
            status="Планирую задачу",
        )
        state.active_agent = progress
        await state.set_status(NovaStatus.AGENT_RUNNING)

        try:
            result = await asyncio.wait_for(
                self._execute_agent_loop(task, agent, progress, max_steps, retry_limit),
                timeout=timeout,
            )
            progress.status = "Завершено"
            progress.completed_at = datetime.now(timezone.utc)
            await state.set_status(NovaStatus.IDLE)
            audit.record("AGENT", "task_completed", {"task_id": task_id, "task": task[:100]})
            return result
        except asyncio.TimeoutError:
            progress.status = "Timeout"
            progress.error = "Agent timeout"
            await state.set_status(NovaStatus.IDLE)
            audit.record("AGENT", "task_timeout", {"task_id": task_id})
            return {"error": "Agent timeout", "task_id": task_id}
        except Exception as e:
            progress.status = "Ошибка"
            progress.error = str(e)
            await state.set_status(NovaStatus.ERROR)
            logger.error("Agent task failed: %s", e)
            return {"error": "Не удалось выполнить задачу", "task_id": task_id}

    async def _execute_agent_loop(
        self,
        task: str,
        agent: dict | None,
        progress: AgentProgress,
        max_steps: int,
        retry_limit: int,
    ) -> dict:
        ai = get_ai_manager()
        registry = get_tool_registry()
        steps_taken = []
        retries = 0

        progress.steps.append({"status": "Планирую задачу", "detail": task})
        progress.current_step = 0

        plan_response = await ai.chat([
            AIMessage(role="user", content=f"Разбей задачу на шаги (макс {max_steps}): {task}")
        ], system=agent["instructions"] if agent else None)

        plan_steps = [s.strip() for s in plan_response.content.split("\n") if s.strip()][:max_steps]

        for i, step in enumerate(plan_steps):
            if i >= max_steps:
                break

            progress.current_step = i + 1
            progress.status = f"Шаг {i + 1}: {step[:50]}"
            progress.steps.append({"status": progress.status, "detail": step})
            steps_taken.append(step)

            tool_result = None
            step_lower = step.lower()

            if any(w in step_lower for w in ("файл", "file", "pdf", "найди")):
                progress.status = "Ищу файлы"
                tool_result = await registry.execute("file_search", {"query": task})
            elif any(w in step_lower for w in ("систем", "cpu", "ram", "компьютер")):
                progress.status = "Проверяю систему"
                tool_result = await registry.execute("system_info", {})
            else:
                progress.status = "Выполняю действие"
                response = await ai.chat([AIMessage(role="user", content=step)])
                tool_result = {"response": response.content}

            progress.steps.append({"status": "Проверяю результат", "detail": str(tool_result)[:200]})

            if tool_result and tool_result.get("error"):
                retries += 1
                if retries >= retry_limit:
                    return {"error": "Retry limit exceeded", "steps": steps_taken}
                continue

        progress.status = "Завершено"
        summary = await ai.chat([
            AIMessage(role="user", content=f"Подведи итог выполнения задачи: {task}. Шаги: {steps_taken}")
        ])

        return {
            "task": task,
            "steps": steps_taken,
            "summary": summary.content,
            "agent": agent["name"] if agent else "NOVA",
        }

    def _to_dict(self, record: AgentRecord) -> dict:
        return {
            "id": record.id,
            "name": record.name,
            "role": record.role,
            "instructions": record.instructions,
            "model": record.model,
            "tools": json.loads(record.tools_json or "[]"),
            "permissions": json.loads(record.permissions_json or "[]"),
            "enabled": record.enabled,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        }


_manager: AgentManager | None = None


def get_agent_manager() -> AgentManager:
    global _manager
    if _manager is None:
        _manager = AgentManager()
    return _manager
