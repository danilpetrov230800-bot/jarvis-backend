"""Skills system for NOVA."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from nova.core.logging import get_audit_log, get_logger
from nova.database.db import SkillRecord, get_session
from nova.tools.registry import get_tool_registry

logger = get_logger("nova.skills")
audit = get_audit_log()


class SkillManager:
    def create(self, data: dict) -> dict:
        now = datetime.now(timezone.utc)
        with get_session() as session:
            record = SkillRecord(
                name=data["name"],
                description=data.get("description", ""),
                trigger=data["trigger"],
                conditions_json=json.dumps(data.get("conditions", []), ensure_ascii=False),
                actions_json=json.dumps(data["actions"], ensure_ascii=False),
                tools_json=json.dumps(data.get("tools", []), ensure_ascii=False),
                permissions_json=json.dumps(data.get("permissions", []), ensure_ascii=False),
                version=1,
                enabled=data.get("enabled", True),
                history_json=json.dumps([{"version": 1, "at": now.isoformat()}]),
                created_at=now,
                updated_at=now,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            audit.record("SKILL", "created", {"id": record.id, "name": record.name})
            return self._to_dict(record)

    def get(self, skill_id: int) -> dict | None:
        with get_session() as session:
            record = session.get(SkillRecord, skill_id)
            return self._to_dict(record) if record else None

    def list_all(self) -> list[dict]:
        with get_session() as session:
            records = session.query(SkillRecord).order_by(SkillRecord.name).all()
            return [self._to_dict(r) for r in records]

    def update(self, skill_id: int, data: dict) -> dict | None:
        with get_session() as session:
            record = session.get(SkillRecord, skill_id)
            if not record:
                return None
            for key in ("name", "description", "trigger", "enabled"):
                if key in data:
                    setattr(record, key, data[key])
            if "conditions" in data:
                record.conditions_json = json.dumps(data["conditions"], ensure_ascii=False)
            if "actions" in data:
                record.actions_json = json.dumps(data["actions"], ensure_ascii=False)
            if "tools" in data:
                record.tools_json = json.dumps(data["tools"], ensure_ascii=False)
            record.version += 1
            history = json.loads(record.history_json or "[]")
            history.append({"version": record.version, "at": datetime.now(timezone.utc).isoformat()})
            record.history_json = json.dumps(history)
            record.updated_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(record)
            return self._to_dict(record)

    def delete(self, skill_id: int) -> bool:
        with get_session() as session:
            record = session.get(SkillRecord, skill_id)
            if not record:
                return False
            session.delete(record)
            session.commit()
            return True

    def find_by_trigger(self, text: str) -> list[dict]:
        text_lower = text.lower()
        matches = []
        for skill in self.list_all():
            if not skill["enabled"]:
                continue
            trigger = skill["trigger"].lower()
            if trigger in text_lower or text_lower in trigger:
                matches.append(skill)
        return matches

    async def execute(self, skill_id: int, context: dict | None = None) -> dict:
        skill = self.get(skill_id)
        if not skill:
            raise ValueError("Skill not found")
        if not skill["enabled"]:
            raise ValueError("Skill is disabled")

        registry = get_tool_registry()
        results = []
        for action in skill["actions"]:
            action_type = action.get("type", "tool")
            if action_type == "tool":
                tool_name = action["tool"]
                params = action.get("params", {})
                result = await registry.execute(tool_name, params, context)
                results.append({"action": action, "result": result})
            elif action_type == "delay":
                import asyncio
                await asyncio.sleep(action.get("seconds", 1))
                results.append({"action": action, "result": "delayed"})
            elif action_type == "message":
                results.append({"action": action, "result": action.get("text", "")})

        audit.record("SKILL", "executed", {"id": skill_id, "name": skill["name"]})
        return {"skill": skill["name"], "results": results}

    async def test(self, skill_id: int) -> dict:
        return await self.execute(skill_id, {"test_mode": True})

    def parse_learn_command(self, text: str) -> dict | None:
        patterns = [
            r"запомни(?:,\s*|\s+)что\s+(.+)",
            r"всегда\s+делай\s+(.+)",
            r"когда\s+я\s+говорю\s+['\"]?(.+?)['\"]?\s*,?\s*выполняй\s+(.+)",
            r"научись\s+(.+)",
        ]
        text_lower = text.lower().strip()

        for i, pattern in enumerate(patterns):
            m = re.search(pattern, text_lower, re.I)
            if m:
                if i == 2:
                    trigger, action = m.group(1), m.group(2)
                    return {
                        "name": f"Skill: {trigger[:30]}",
                        "trigger": trigger,
                        "actions": [{"type": "message", "text": action}],
                    }
                content = m.group(1)
                return {
                    "name": f"Auto: {content[:30]}",
                    "trigger": content.split()[0] if content else "custom",
                    "actions": [{"type": "message", "text": content}],
                    "description": content,
                }
        return None

    def _to_dict(self, record: SkillRecord) -> dict:
        return {
            "id": record.id,
            "name": record.name,
            "description": record.description,
            "trigger": record.trigger,
            "conditions": json.loads(record.conditions_json or "[]"),
            "actions": json.loads(record.actions_json or "[]"),
            "tools": json.loads(record.tools_json or "[]"),
            "permissions": json.loads(record.permissions_json or "[]"),
            "version": record.version,
            "enabled": record.enabled,
            "history": json.loads(record.history_json or "[]"),
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        }


_manager: SkillManager | None = None


def get_skill_manager() -> SkillManager:
    global _manager
    if _manager is None:
        _manager = SkillManager()
    return _manager
