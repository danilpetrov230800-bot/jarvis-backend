"""AI Provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AIMessage:
    role: str
    content: str


@dataclass
class AIResponse:
    content: str
    model: str
    provider: str
    usage: dict[str, Any] = field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class AIProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def chat(
        self,
        messages: list[AIMessage],
        system: str | None = None,
        tools: list[dict] | None = None,
    ) -> AIResponse:
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        pass

    async def health_check(self) -> dict[str, Any]:
        available = await self.is_available()
        return {
            "provider": self.name,
            "available": available,
            "status": "PASS" if available else "FAIL",
        }
