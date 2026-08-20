from __future__ import annotations

import asyncio
import re
from typing import Any, Awaitable, Callable

from jarvis.config import Settings
from jarvis.storage import audit

StepExecutor = Callable[[str], Awaitable[dict[str, Any]]]


def plan_goal(goal: str, max_steps: int) -> list[str]:
    parts = [part.strip() for part in re.split(r"(?:[.;]\s+|\n+)", goal) if part.strip()]
    return (parts or [goal.strip()])[:max_steps]


async def run_agent(
    agent: dict[str, Any],
    goal: str,
    settings: Settings,
    execute: StepExecutor,
    *,
    max_steps: int = 8,
    timeout: float = 120,
    retry_limit: int = 1,
) -> dict[str, Any]:
    if not agent.get("enabled"):
        raise ValueError("Агент отключён")
    max_steps = min(max(max_steps, 1), 20)
    retry_limit = min(max(retry_limit, 0), 3)
    steps = plan_goal(goal, max_steps)
    events: list[dict[str, Any]] = [{"status": "planning", "message": f"План: {len(steps)} шагов"}]

    async def workflow() -> None:
        for index, step in enumerate(steps, 1):
            last_error: Exception | None = None
            for attempt in range(retry_limit + 1):
                try:
                    events.append({"status": "running", "step": index, "message": step})
                    result = await execute(step)
                    reply = str(result.get("reply", "")).strip()
                    if not reply:
                        raise RuntimeError("Пустой результат")
                    events.append({"status": "verified", "step": index, "message": reply, "tools": result.get("tools", [])})
                    last_error = None
                    break
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    events.append({"status": "retry", "step": index, "attempt": attempt + 1, "message": type(exc).__name__})
            if last_error is not None:
                raise last_error

    try:
        await asyncio.wait_for(workflow(), timeout=min(max(timeout, 1), 600))
    except TimeoutError:
        events.append({"status": "stopped", "message": "Превышен лимит времени"})
        audit("agent_timeout", str(agent.get("name", "")), level="WARNING", category="AGENT")
        raise
    events.append({"status": "completed", "message": "Задача проверена"})
    audit("agent_completed", f"{agent.get('name', '')}; steps={len(steps)}", category="AGENT")
    return {"agent": agent.get("name"), "goal": goal, "events": events, "completed": True}
