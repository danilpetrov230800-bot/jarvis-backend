from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChatMessage:
    role: str
    content: str


@dataclass
class ProviderResult:
    text: str
    provider: str
    model: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


class AIProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        timeout: float = 45,
    ) -> ProviderResult:
        raise NotImplementedError

    async def health(self) -> dict[str, Any]:
        return {"provider": self.name, "ok": True}
