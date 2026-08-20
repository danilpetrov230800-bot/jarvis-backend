"""
NOVA Skills Engine & Visual Skill Builder Backend
- Skill triggers: phrase, regex, event, schedule
- Actions sequence: app launch, system command, web request, TTS, memory update, file action
- Variable substitution, delays, conditions, permissions, testing execution
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from nova.database import db
from nova.security import security_manager
from nova.tools import control_pc_action, evaluate_math, open_application, read_file_safe, write_file_safe

log = logging.getLogger("nova.skills")


@dataclass
class SkillAction:
    action_type: str # open_app, pc_action, file_read, file_write, delay, tts_speak, memory_save
    params: dict[str, Any] = field(default_factory=dict)
    condition: str | None = None
    require_confirmation: bool = False


@dataclass
class Skill:
    id: str
    name: str
    description: str
    trigger_type: str # phrase, regex, schedule, event
    trigger_value: str
    conditions: list[str] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    enabled: bool = True
    version: int = 1
    created_at: str = ""
    updated_at: str = ""


class SkillsEngine:
    def __init__(self):
        self._ensure_default_skills()

    def _ensure_default_skills(self) -> None:
        """Create helpful out-of-the-box skills"""
        if not self.list_skills():
            # Work Mode Skill
            self.create_skill(
                name="Режим работы",
                description="Открывает рабочие инструменты и настраивает громкость",
                trigger_type="phrase",
                trigger_value="режим работы",
                actions=[
                    {"action_type": "open_app", "params": {"name": "chrome"}},
                    {"action_type": "open_app", "params": {"name": "notepad"}},
                    {"action_type": "pc_action", "params": {"action": "volume_up"}},
                    {"action_type": "tts_speak", "params": {"text": "Рабочий режим активирован."}}
                ],
                permissions=["RUN_APPLICATIONS", "SYSTEM_CONTROL"]
            )
            # Sleep / Leaving Mode Skill
            self.create_skill(
                name="Я ухожу",
                description="Блокирует рабочий стол и выключает звук",
                trigger_type="phrase",
                trigger_value="я ухожу",
                actions=[
                    {"action_type": "pc_action", "params": {"action": "volume_mute"}},
                    {"action_type": "pc_action", "params": {"action": "lock"}},
                    {"action_type": "tts_speak", "params": {"text": "Компьютер заблокирован. До встречи!"}}
                ],
                permissions=["SYSTEM_CONTROL"]
            )

    def create_skill(
        self,
        name: str,
        description: str,
        trigger_type: str,
        trigger_value: str,
        actions: list[dict[str, Any]],
        conditions: list[str] | None = None,
        permissions: list[str] | None = None,
        skill_id: str | None = None
    ) -> Skill:
        s_id = skill_id or str(uuid.uuid4())
        now = datetime.now().isoformat()
        actions_json = json.dumps(actions, ensure_ascii=False)
        cond_json = json.dumps(conditions or [], ensure_ascii=False)
        perm_json = json.dumps(permissions or [], ensure_ascii=False)

        with db.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO skills (id, name, description, trigger_type, trigger_value, conditions, actions, permissions, enabled, version, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 1, COALESCE((SELECT created_at FROM skills WHERE id = ?), ?), ?)
                """,
                (s_id, name, description, trigger_type, trigger_value, cond_json, actions_json, perm_json, s_id, now, now)
            )
            conn.commit()

        security_manager.log_audit("INFO", "SKILLS", f"Created/Updated skill: {name}", {"id": s_id})
        return self.get_skill(s_id) # type: ignore

    def get_skill(self, skill_id: str) -> Skill | None:
        with db.get_connection() as conn:
            cur = conn.execute("SELECT * FROM skills WHERE id = ?", (skill_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_skill(row)

    def list_skills(self) -> list[Skill]:
        with db.get_connection() as conn:
            cur = conn.execute("SELECT * FROM skills ORDER BY updated_at DESC")
            return [self._row_to_skill(r) for r in cur.fetchall()]

    def delete_skill(self, skill_id: str) -> bool:
        with db.get_connection() as conn:
            cur = conn.execute("DELETE FROM skills WHERE id = ?", (skill_id,))
            conn.commit()
            return cur.rowcount > 0

    def match_trigger(self, text: str) -> Skill | None:
        lowered = text.strip().lower()
        for skill in self.list_skills():
            if not skill.enabled:
                continue
            if skill.trigger_type == "phrase" and skill.trigger_value.lower() in lowered:
                return skill
            elif skill.trigger_type == "regex":
                try:
                    if re.search(skill.trigger_value, lowered, re.IGNORECASE):
                        return skill
                except Exception:
                    pass
        return None

    async def execute_skill(self, skill: Skill, context: dict[str, Any] | None = None) -> dict[str, Any]:
        results = []
        ctx = context or {}

        security_manager.log_audit("INFO", "SKILLS", f"Executing skill: {skill.name}", {"skill_id": skill.id})

        for index, action in enumerate(skill.actions, start=1):
            act_type = action.get("action_type")
            params = action.get("params", {})

            step_res = {"step": index, "action": act_type, "success": True, "details": {}}
            try:
                if act_type == "open_app":
                    app_name = params.get("name", "")
                    res = open_application(app_name)
                    step_res["details"] = res
                    step_res["success"] = res.get("success", False)

                elif act_type == "pc_action":
                    cmd = params.get("action", "")
                    res = control_pc_action(cmd)
                    step_res["details"] = res
                    step_res["success"] = res.get("success", False)

                elif act_type == "file_write":
                    path = params.get("path", "")
                    content = params.get("content", "")
                    res = write_file_safe(path, content)
                    step_res["details"] = res
                    step_res["success"] = res.get("success", False)

                elif act_type == "delay":
                    seconds = float(params.get("seconds", 1))
                    await asyncio.sleep(min(seconds, 30))
                    step_res["details"] = {"delayed_seconds": seconds}

                elif act_type == "tts_speak":
                    text = params.get("text", "")
                    step_res["details"] = {"spoken_text": text}

                else:
                    step_res["success"] = False
                    step_res["details"] = {"error": f"Unknown action type: {act_type}"}

            except Exception as e:
                step_res["success"] = False
                step_res["details"] = {"error": str(e)}

            results.append(step_res)
            if not step_res["success"] and action.get("stop_on_error", False):
                break

        return {
            "skill_id": skill.id,
            "name": skill.name,
            "steps_executed": len(results),
            "results": results,
            "success": all(r["success"] for r in results)
        }

    def _row_to_skill(self, row: Any) -> Skill:
        actions = []
        conds = []
        perms = []
        try:
            actions = json.loads(row["actions"] or "[]")
            conds = json.loads(row["conditions"] or "[]")
            perms = json.loads(row["permissions"] or "[]")
        except Exception:
            pass

        return Skill(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            trigger_type=row["trigger_type"],
            trigger_value=row["trigger_value"],
            conditions=conds,
            actions=actions,
            permissions=perms,
            enabled=bool(row["enabled"]),
            version=row["version"],
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"])
        )


skills_engine = SkillsEngine()
