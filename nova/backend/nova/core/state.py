"""Global NOVA runtime state."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class NovaStatus(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    AGENT_RUNNING = "agent_running"
    OFFLINE = "offline"
    ERROR = "error"


@dataclass
class AgentProgress:
    task_id: str
    title: str
    status: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    current_step: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    error: str | None = None


@dataclass
class NovaState:
    status: NovaStatus = NovaStatus.IDLE
    offline: bool = False
    current_task: str | None = None
    active_agent: AgentProgress | None = None
    voice_active: bool = False
    wake_word_active: bool = False
    last_error: str | None = None
    component_health: dict[str, str] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def set_status(self, status: NovaStatus) -> None:
        async with self._lock:
            self.status = status

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "offline": self.offline,
            "current_task": self.current_task,
            "voice_active": self.voice_active,
            "wake_word_active": self.wake_word_active,
            "last_error": self.last_error,
            "component_health": self.component_health,
            "active_agent": (
                {
                    "task_id": self.active_agent.task_id,
                    "title": self.active_agent.title,
                    "status": self.active_agent.status,
                    "steps": self.active_agent.steps,
                    "current_step": self.active_agent.current_step,
                }
                if self.active_agent
                else None
            ),
        }


_state: NovaState | None = None


def get_state() -> NovaState:
    global _state
    if _state is None:
        _state = NovaState()
    return _state
