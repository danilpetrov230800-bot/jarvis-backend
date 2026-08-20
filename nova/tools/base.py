from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


@dataclass
class ToolResult:
    ok: bool
    reply: str
    data: dict[str, Any] = field(default_factory=dict)
    sources: list[dict[str, str]] = field(default_factory=list)
    needs_confirmation: bool = False
    confirmation_token: str | None = None
    confirmation_summary: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "ok": self.ok,
            "reply": self.reply,
            "data": self.data,
            "sources": self.sources,
        }
        if self.needs_confirmation:
            payload.update(
                {
                    "needs_confirmation": True,
                    "confirmation_token": self.confirmation_token,
                    "confirmation_summary": self.confirmation_summary,
                }
            )
        return payload


@dataclass
class ToolSpec:
    name: str
    title: str
    description: str
    permission: str
    handler: Callable[..., Awaitable[ToolResult]]
    schema: dict[str, Any]
    dangerous: bool = False
    offline: bool = True
