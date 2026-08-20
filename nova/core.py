"""
NOVA Core Central Coordinator
- Connects AI Provider, Memory, Skills, Tools, Multi-Agent, Voice, Research, Tasks, Security, Logs
- Intent routing (Direct commands, Skills trigger, Agents execution, AI Chat)
- Crash recovery and resilience
- Safe error handling (User friendly Russian messages, full trace in secure logs)
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Any

from nova.agents import agent_manager
from nova.ai_provider import get_ai_provider
from nova.config import AppSettings
from nova.database import db
from nova.memory import memory_manager
from nova.research import research_engine
from nova.security import redact_secrets, security_manager
from nova.skills import skills_engine
from nova.tasks import task_manager
from nova.tools import (
    add_note,
    control_pc_action,
    evaluate_math,
    find_files,
    get_system_metrics,
    list_notes,
    list_processes,
    open_application,
    read_file_safe,
    set_clipboard,
    write_file_safe,
)
from nova.voice import voice_manager

log = logging.getLogger("nova.core")


class NovaCore:
    def __init__(self):
        self.settings = self._load_settings()

    def _load_settings(self) -> AppSettings:
        with db.get_connection() as conn:
            cur = conn.execute("SELECT value FROM settings WHERE key = 'app_settings'")
            row = cur.fetchone()
            if row:
                try:
                    return AppSettings.model_validate_json(row["value"])
                except Exception as e:
                    log.error(f"Error loading settings: {e}")
        return AppSettings()

    def save_settings(self, new_settings: AppSettings) -> None:
        self.settings = new_settings
        with db.get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES ('app_settings', ?, CURRENT_TIMESTAMP)",
                (new_settings.model_dump_json(),)
            )
            conn.commit()
        security_manager.update_settings(new_settings.security)
        security_manager.log_audit("INFO", "CORE", "Updated application settings")

    async def process_user_input(
        self,
        text: str,
        source: str = "text", # text, voice
        confirmed: bool = False
    ) -> dict[str, Any]:
        """
        Master Pipeline:
        Input -> Wake Word Check -> Skill Trigger -> Deterministic PC / Local Tools -> Multi-Agent -> AI Provider -> Memory -> Response
        """
        raw_text = text.strip()
        if not raw_text:
            return {"reply": "Я вас слушаю. Чем могу помочь?", "tools": [], "source": source}

        # 1. Wake word handling
        if source == "voice":
            is_wake, extracted_cmd = voice_manager.is_wake_word(raw_text, self.settings.voice)
            if is_wake and not extracted_cmd:
                return {
                    "reply": "Да, я слушаю вас!",
                    "wake_word_activated": True,
                    "tools": ["wake_word"]
                }
            if is_wake and extracted_cmd:
                raw_text = extracted_cmd

        lowered = raw_text.lower().strip()
        memory_manager.add_short_term(role="user", content=raw_text)

        # 2. Check Skills triggers
        matched_skill = skills_engine.match_trigger(raw_text)
        if matched_skill:
            skill_res = await skills_engine.execute_skill(matched_skill)
            reply = f"Выполнен навык: «{matched_skill.name}»"
            memory_manager.add_short_term(role="assistant", content=reply)
            return {
                "reply": reply,
                "skill_executed": skill_res,
                "tools": ["skills_engine"]
            }

        # 3. Fast Deterministic Intent Matching (Local-First Offline)
        # 3.1 Notes
        note_match = re.match(r"^(?:запиши|заметка|заметку|note)\s*[:\-]?\s*(.+)$", raw_text, re.I)
        if note_match:
            note_text = note_match.group(1).strip()
            res_text = add_note(note_text)
            memory_manager.add(category="episodic", title="Заметка", content=note_text)
            return {"reply": res_text, "tools": ["notes"]}

        if lowered in {"покажи заметки", "список заметок", "мои заметки"}:
            notes = list_notes()
            if not notes:
                return {"reply": "У вас пока нет сохраненных заметок.", "tools": ["notes"]}
            return {"reply": "Ваши последние заметки:\n" + "\n".join([f"— {n}" for n in notes[-5:]]), "tools": ["notes"]}

        # 3.2 Calculator
        calc_match = re.match(r"^(?:посчитай|сколько будет|вычисли|расчет)\s+(.+)$", raw_text, re.I)
        if calc_match:
            expr = calc_match.group(1).strip()
            math_res = evaluate_math(expr)
            if math_res.get("success"):
                reply = f"Результат: {math_res['formatted']}"
                return {"reply": reply, "tools": ["calculator"]}

        # 3.3 PC Control (Volume, Brightness, Lock, Sleep)
        if lowered in {"выключи звук", "без звука", "mute", "мут"}:
            res = control_pc_action("volume_mute")
            return {"reply": res.get("message", "Звук переключен"), "tools": ["volume"]}
        if lowered in {"громче", "сделай громче", "прибавь звук", "громкость выше"}:
            res = control_pc_action("volume_up")
            return {"reply": res.get("message", "Громкость увеличена"), "tools": ["volume"]}
        if lowered in {"тише", "сделай тише", "убавь звук", "громкость ниже"}:
            res = control_pc_action("volume_down")
            return {"reply": res.get("message", "Громкость уменьшена"), "tools": ["volume"]}
        if lowered in {"пауза", "плей", "play", "музыка стоп", "стоп музыка"}:
            res = control_pc_action("media_play_pause")
            return {"reply": res.get("message", "Медиа переключено"), "tools": ["media"]}
        if lowered in {"следующий трек", "следующая песня"}:
            res = control_pc_action("media_next")
            return {"reply": res.get("message", "Следующий трек"), "tools": ["media"]}
        if lowered in {"заблокируй пк", "заблокируй экран", "lock"}:
            res = control_pc_action("lock")
            return {"reply": res.get("message", "Экран заблокирован"), "tools": ["system_control"]}

        # 3.4 Open Applications
        open_match = re.match(r"^(?:открой|запусти|включи|старт)\s+(.+)$", raw_text, re.I)
        if open_match:
            target_app = open_match.group(1).strip()
            res = open_application(target_app)
            if res.get("success"):
                return {"reply": res.get("message", f"Приложение {target_app} запущено"), "tools": ["app_launcher"]}

        # 3.5 System Status
        if "состояние пк" in lowered or "что с компьютером" in lowered or "загрузка пк" in lowered:
            metrics = get_system_metrics()
            cpu_p = metrics["cpu"]["percent"]
            mem_p = metrics["memory"]["percent"]
            free_disk = metrics["main_disk"]["free_gb"]
            reply = (
                f"Состояние ПК:\n"
                f"• Загрузка CPU: {cpu_p}%\n"
                f"• Оперативная память: {mem_p}% занято ({metrics['memory']['used_gb']} / {metrics['memory']['total_gb']} ГБ)\n"
                f"• Свободно на диске: {free_disk} ГБ\n"
                f"• Время работы: с {metrics['boot_time']}"
            )
            return {"reply": reply, "tools": ["system_agent"]}

        # 3.6 Memory Recall or Save Intent
        mem_save_match = re.match(r"^(?:запомни|сохрани в память)\s*[:\-]?\s*(.+)$", raw_text, re.I)
        if mem_save_match:
            mem_content = mem_save_match.group(1).strip()
            memory_manager.add(category="long_term", title=mem_content[:30], content=mem_content, importance=2)
            return {"reply": f"Запомнила: «{mem_content}». Это сохранено в долговременную память.", "tools": ["memory"]}

        # 4. Multi-Agent Delegation Check
        if "агент" in lowered or "найди все файлы" in lowered or "сделай анализ" in lowered:
            # Delegate to Agent
            try:
                agent_res = await agent_manager.run_agent_task("file-agent", raw_text, self.settings.ai)
                return {
                    "reply": agent_res["summary"],
                    "agent_steps": agent_res["steps"],
                    "tools": ["agent_runner"]
                }
            except Exception as e:
                log.error(f"Agent execution error: {e}")

        # 5. AI Provider Chat with Semantic Context
        relevant_memories = memory_manager.search_relevant(raw_text, limit=3)
        context_str = ""
        if relevant_memories:
            context_str = "\n[Факты из памяти пользователя]:\n" + "\n".join([f"- {m.content}" for m in relevant_memories])

        messages = [
            {"role": "system", "content": self.settings.ai.system_prompt + context_str}
        ]
        for item in memory_manager.get_short_term(limit=10):
            messages.append({"role": item["role"], "content": item["content"]})

        try:
            provider = get_ai_provider(self.settings.ai.provider)
            ai_resp = await provider.chat(messages, self.settings.ai)
            reply = ai_resp.get("reply", "Ответ получен.")
            memory_manager.add_short_term(role="assistant", content=reply)
            return {
                "reply": reply,
                "provider": ai_resp.get("provider", "local"),
                "model": ai_resp.get("model", ""),
                "tools": ["ai_chat"]
            }
        except Exception as e:
            err_text = redact_secrets(str(e))
            log.error(f"AI Chat Error: {err_text}")
            # Crash recovery fallback
            return {
                "reply": "Не удалось связаться с внешней AI-моделью. Переключаюсь на локальный режим. Чем я могу помочь на вашем ПК?",
                "provider": "local-fallback",
                "tools": ["fallback"]
            }


nova_core = NovaCore()
