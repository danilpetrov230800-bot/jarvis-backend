from __future__ import annotations

import json
import threading
from typing import Any

from nova.agents.catalog import AgentCatalog
from nova.agents.runtime import AgentRuntime
from nova.ai.base import ChatMessage
from nova.ai.router import ProviderRouter
from nova.backup import BackupService
from nova.crash import Supervisor
from nova.db import Database
from nova.diagnostics import Diagnostics
from nova.intent import IntentRouter, help_text
from nova.logging_service import LogService
from nova.memory.service import MemoryService
from nova.notify import NotifyService
from nova.permissions import PermissionService
from nova.research.service import ResearchService
from nova.secretstore import SecretStore
from nova.settings import SettingsService
from nova.skills.service import SkillService
from nova.tasks.service import TaskService
from nova.tools.notes import NotesTool
from nova.tools.registry import ToolRegistry
from nova.updates import UpdateService
from nova.voice.pipeline import EchoGuard, is_wake_word, speech_preview, strip_wake_word


class NovaKernel:
    def __init__(self) -> None:
        self.log = LogService()
        self.secrets = SecretStore()
        self.settings = SettingsService(secrets=self.secrets)
        self.db = Database()
        self.permissions = PermissionService(self.db, self.log)
        self.memory = MemoryService(self.db, self.log)
        self.skills = SkillService(self.db, self.log)
        self.agents = AgentCatalog(self.db)
        self.tasks = TaskService(self.db)
        self.notify = NotifyService(self.db)
        self.notes = NotesTool(self.db)
        self.tools = ToolRegistry(self.permissions, self.log, self.notes)
        self.providers = ProviderRouter(self.settings)
        self.intent = IntentRouter()
        self.echo = EchoGuard(self.settings.current.echo_guard_ms)
        self.research = ResearchService(self.permissions)
        self.backup = BackupService(self.db, self.settings, self.secrets)
        self.updates = UpdateService()
        self.supervisor = Supervisor(self.log)
        self.agent_runtime = AgentRuntime(self.log, self.tools.run)
        self.diagnostics = Diagnostics(self)
        self._lock = threading.RLock()
        self.log.info("NOVA kernel started")

    def snapshot(self) -> dict[str, Any]:
        settings = self.settings.current
        return {
            "status": "online",
            "assistant": settings.assistant_name,
            "user": settings.user_name,
            "offline": settings.offline_mode or settings.ai_provider == "local" and not self.settings.api_key(),
            "provider": self.settings.resolved_provider(),
            "first_run": not settings.first_run_complete,
            "wake_word": settings.wake_word_enabled,
            "voice": settings.voice_enabled,
            "theme": settings.theme,
            "scale": settings.ui_scale,
        }

    async def handle_chat(self, text: str, source: str = "text", nested: bool = False) -> dict[str, Any]:
        original = text.strip()
        if not original:
            return self._pack("Скажите или напишите команду.")
        if is_wake_word(original, self.settings.current.wake_words) and len(original.split()) <= 2:
            return self._pack("Слушаю.", tools=["wake"])
        text = strip_wake_word(original, self.settings.current.wake_words) or original
        if source != "text" and self.echo.blocked(text):
            return self._pack("", tools=["echo_guard"], silent=True)

        if not nested:
            self.memory.conversation_add("user", text, source)

        try:
            local = await self.intent.route(text, self)
            if local:
                return self._finalize(text, local, source, nested)
        except Exception as exc:
            self.log.error("intent failed", error=str(exc))

        if self._wants_agent(text):
            run = await self.agent_runtime.run(text)
            payload = self._pack(
                run.result or run.error or "Готово.",
                tools=["agent"],
                extra={
                    "agent": {
                        "status": run.status,
                        "steps": self.agent_runtime.visualize(run),
                    }
                },
            )
            return self._finalize(text, payload, source, nested)

        if self.settings.resolved_provider() != "local" and not self.settings.current.offline_mode:
            try:
                history = [
                    ChatMessage(role=m["role"], content=m["content"])
                    for m in self.memory.conversation(self.settings.current.max_history)
                ]
                context = self.memory.relevant_context(text)
                system = (
                    f"Ты {self.settings.current.assistant_name} — персональный ассистент. "
                    "Отвечай по-русски, кратко и по делу. Не выдумывай системные действия, которых не делала."
                )
                if context:
                    system += "\n" + context
                result = await self.providers.chat(
                    [ChatMessage("system", system), *history, ChatMessage("user", text)],
                    tools=self.tools.schemas(),
                )
                if result.tool_calls:
                    notes = []
                    for call in result.tool_calls:
                        args = call.get("arguments") or "{}"
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except json.JSONDecodeError:
                                args = {}
                        tool_result = await self.tools.run(call["name"], args)
                        notes.append(tool_result.get("reply") or "")
                    if notes and not result.text:
                        result.text = "\n".join(notes)
                payload = self._pack(result.text or help_text(), tools=["llm"], extra={"provider": result.provider, "model": result.model})
                return self._finalize(text, payload, source, nested)
            except Exception as exc:
                self.log.error("provider failed, local fallback", error=str(exc))

        recalled = self.memory.recall(text, limit=3)
        if recalled:
            facts = "; ".join(row["content"] for row in recalled)
            payload = self._pack(f"Из памяти: {facts}", tools=["memory"])
            return self._finalize(text, payload, source, nested)

        payload = self._pack(help_text(), tools=["help"])
        return self._finalize(text, payload, source, nested)

    def _wants_agent(self, text: str) -> bool:
        lowered = text.lower()
        markers = (
            "сравни варианты",
            "подготовь результат",
            "разложи",
            "найди все",
            "построй план",
            "агент",
            "сделай исследование",
        )
        return any(m in lowered for m in markers)

    def _finalize(self, text: str, payload: dict[str, Any], source: str, nested: bool) -> dict[str, Any]:
        reply = payload.get("reply") or ""
        payload["speech"] = speech_preview(reply) if reply else ""
        if reply and source == "voice":
            self.echo.mark_spoken(reply)
        if not nested:
            if reply:
                self.memory.conversation_add("assistant", reply, source)
            self.db.execute(
                "INSERT INTO action_history(action, summary, ok, created_at) VALUES (?, ?, ?, datetime('now'))",
                ("chat", reply[:180], int(payload.get("ok", True))),
            )
        payload.setdefault("ok", True)
        payload.setdefault("sources", [])
        payload.setdefault("tools", [])
        payload.setdefault("provider", self.settings.resolved_provider())
        payload.setdefault("model", self.settings.resolved_model())
        return payload

    def _pack(self, reply: str, tools: list[str] | None = None, extra: dict | None = None, silent: bool = False) -> dict[str, Any]:
        payload = {
            "ok": True,
            "reply": reply,
            "tools": tools or [],
            "sources": [],
            "silent": silent,
            "provider": "local",
            "model": "nova-local",
        }
        if extra:
            payload.update(extra)
        return payload

    def close(self) -> None:
        self.supervisor.stop()
        self.db.close()
