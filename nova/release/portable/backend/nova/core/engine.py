"""NOVA Core Engine - central orchestrator."""

from __future__ import annotations

import json
import re
from typing import Any

from nova.agents.manager import get_agent_manager
from nova.ai.manager import get_ai_manager
from nova.ai.provider import AIMessage
from nova.core.config import get_settings, reload_settings
from nova.core.logging import get_audit_log, get_logger
from nova.core.state import NovaStatus, get_state
from nova.database.db import ChatMessage, SettingRecord, get_session
from nova.memory.store import get_memory_store
from nova.skills.manager import get_skill_manager
from nova.tools.registry import get_tool_registry
from nova.voice.pipeline import get_voice_pipeline

logger = get_logger("nova.core.engine")
audit = get_audit_log()


class NovaEngine:
    def __init__(self):
        self.settings = get_settings()
        self.ai = get_ai_manager()
        self.memory = get_memory_store()
        self.skills = get_skill_manager()
        self.agents = get_agent_manager()
        self.tools = get_tool_registry()
        self.voice = get_voice_pipeline()
        self.state = get_state()
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return

        from nova.database.db import init_db
        init_db()

        network = await self.ai.check_network()
        self.state.offline = not network
        self.settings.offline_mode = not network

        voice_status = await self.voice.initialize()
        self.state.component_health["voice"] = voice_status.get("microphone", "UNKNOWN")

        self.voice.set_command_handler(self.process_message)
        if self.settings.voice_enabled and self.settings.wake_word_enabled:
            self.voice.start()

        self._initialized = True
        logger.info("NOVA Core initialized (offline=%s)", self.state.offline)
        audit.record("SYSTEM", "startup", {"offline": self.state.offline})

    async def process_message(self, text: str, confirmed: bool = False) -> str:
        await self.state.set_status(NovaStatus.PROCESSING)
        self._save_chat("user", text)

        try:
            response = await self._route_message(text, confirmed)
            self._save_chat("assistant", response)
            await self.state.set_status(NovaStatus.IDLE)
            return response
        except Exception as e:
            logger.error("Message processing failed: %s", e)
            await self.state.set_status(NovaStatus.ERROR)
            self.state.last_error = str(e)
            return "Произошла ошибка. Подробности в Logs."

    async def _route_message(self, text: str, confirmed: bool) -> str:
        text_lower = text.lower().strip()

        if re.search(r"запомни|научись|всегда делай|когда я говорю", text_lower):
            skill_data = self.skills.parse_learn_command(text)
            if skill_data:
                skill = self.skills.create(skill_data)
                self.memory.create(
                    content=skill_data.get("description", skill_data["trigger"]),
                    type="skill",
                    category="learned",
                )
                return f"Запомнила! Создан Skill «{skill['name']}»."

        if re.search(r"запомни(?:,\s*|\s+)что\s+", text_lower):
            content = re.sub(r".*запомни(?:,\s*|\s+)что\s+", "", text, flags=re.I).strip()
            self.memory.create(content=content, type="long-term", category="user")
            return f"Запомнила: {content}"

        memory_match = re.search(r"что ты знаешь о|вспомни|найди в памяти\s+(.+)", text_lower)
        if memory_match:
            query = memory_match.group(1) if memory_match.lastindex else text
            results = self.memory.search(query)
            if results:
                return "В памяти:\n" + "\n".join(f"- {r['content']}" for r in results[:5])
            return "В памяти ничего не найдено по этому запросу."

        skill_matches = self.skills.find_by_trigger(text)
        if skill_matches:
            result = await self.skills.execute(skill_matches[0]["id"])
            return f"Skill «{skill_matches[0]['name']}» выполнен."

        tool_result = await self._try_tool_command(text, confirmed)
        if tool_result:
            return tool_result

        if any(w in text_lower for w in ("агент", "agent", "найди информацию", "подготовь", "сравни")):
            result = await self.agents.run_task(text)
            if "error" in result:
                return f"Не удалось выполнить задачу: {result['error']}"
            return result.get("summary", "Задача выполнена.")

        history = self._get_chat_history(limit=10)
        messages = [AIMessage(role=m["role"], content=m["content"]) for m in history]
        messages.append(AIMessage(role="user", content=text))

        memory_context = self.memory.search(text, limit=3)
        system = (
            "Ты NOVA — персональный AI-ассистент. Отвечай по-русски, естественно и полезно. "
            "Не раскрывай внутренние рассуждения."
        )
        if memory_context:
            system += "\nКонтекст из памяти:\n" + "\n".join(m["content"] for m in memory_context)

        response = await self.ai.chat(messages, system=system)
        return response.content

    async def _try_tool_command(self, text: str, confirmed: bool) -> str | None:
        text_lower = text.lower()

        if re.search(r"(\d+\s*[\+\-\*/]\s*\d+)", text):
            expr = re.search(r"(\d+\s*[\+\-\*/]\s*\d+)", text).group(1)
            result = await self.tools.execute("calculator", {"expression": expr})
            if "result" in result:
                return f"Результат: {result['result']}"

        if any(w in text_lower for w in ("систем", "компьютер", "cpu", "ram", "тормоз")):
            result = await self.tools.execute("system_info", {})
            info = result
            return (
                f"CPU: {info.get('cpu_percent', '?')}%, "
                f"RAM: {info.get('ram_used_percent', '?')}% "
                f"({info.get('ram_available_gb', '?')} GB свободно). "
                f"{' '.join(info.get('analysis', []))}"
            )

        if "диск" in text_lower or "место" in text_lower:
            result = await self.tools.execute("disk_info", {})
            lines = [f"{d['mountpoint']}: {d['free_gb']} GB свободно ({d['percent']}% занято)" for d in result.get("disks", [])]
            return "Диски:\n" + "\n".join(lines) if lines else "Информация о дисках недоступна."

        if any(w in text_lower for w in ("найди файл", "найди все", "поиск файлов")):
            query = re.sub(r".*(?:найди|поиск)\s+(?:файл|файлы|all)?\s*", "", text_lower).strip() or "*"
            ext = ""
            if "pdf" in text_lower:
                ext = ".pdf"
            elif "фото" in text_lower or "jpg" in text_lower:
                ext = ".jpg"
            result = await self.tools.execute("file_search", {"query": query, "extension": ext})
            files = result.get("files", [])
            if files:
                return f"Найдено {len(files)} файлов:\n" + "\n".join(files[:10])
            return "Файлы не найдены."

        if any(w in text_lower for w in ("открой", "запусти", "launch")):
            app = re.sub(r".*(?:открой|запусти)\s+", "", text_lower).strip()
            result = await self.tools.execute("launch_app", {"name": app}, confirmed=confirmed)
            if result.get("confirmation_required"):
                return result["message"] + " Подтвердите действие."
            if "launched" in result:
                return f"Запускаю {result['launched']}."
            return result.get("error", "Не удалось запустить приложение.")

        if "скриншот" in text_lower or "посмотри на экран" in text_lower:
            result = await self.tools.execute("screenshot", {})
            if "path" in result:
                ocr = await self.tools.execute("ocr", {"path": result["path"]})
                if ocr.get("text"):
                    return f"На экране:\n{ocr['text'][:500]}"
                return f"Скриншот сохранён: {result['path']}"
            return result.get("error", "Не удалось сделать скриншот.")

        return None

    def _save_chat(self, role: str, content: str) -> None:
        with get_session() as session:
            session.add(ChatMessage(role=role, content=content))
            session.commit()

    def _get_chat_history(self, limit: int = 20) -> list[dict]:
        with get_session() as session:
            messages = session.query(ChatMessage).order_by(ChatMessage.id.desc()).limit(limit).all()
            return [{"role": m.role, "content": m.content} for m in reversed(messages)]

    def get_settings_dict(self) -> dict:
        s = self.settings
        return {
            "app_name": s.app_name,
            "version": s.version,
            "ai_provider": s.ai_provider,
            "ai_model": s.ai_model,
            "voice_enabled": s.voice_enabled,
            "wake_word_enabled": s.wake_word_enabled,
            "wake_word_sensitivity": s.wake_word_sensitivity,
            "tts_rate": s.tts_rate,
            "tts_volume": s.tts_volume,
            "theme": s.theme,
            "language": s.language,
            "offline_mode": s.offline_mode,
            "first_run_complete": s.first_run_complete,
            "research_mode_enabled": s.research_mode_enabled,
            "agent_max_steps": s.agent_max_steps,
            "agent_timeout_sec": s.agent_timeout_sec,
        }

    async def update_settings(self, data: dict) -> dict:
        for key, value in data.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
        with get_session() as session:
            for key, value in data.items():
                existing = session.get(SettingRecord, key)
                if existing:
                    existing.value = json.dumps(value)
                else:
                    session.add(SettingRecord(key=key, value=json.dumps(value)))
            session.commit()
        reload_settings()
        return self.get_settings_dict()

    def get_status(self) -> dict:
        return {
            **self.state.to_dict(),
            "version": self.settings.version,
            "initialized": self._initialized,
        }


_engine: NovaEngine | None = None


def get_engine() -> NovaEngine:
    global _engine
    if _engine is None:
        _engine = NovaEngine()
    return _engine
