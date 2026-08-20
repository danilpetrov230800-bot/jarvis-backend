from __future__ import annotations

import json
from typing import Any

from nova.db import Database, utcnow
from nova.logging_service import LogService


class SkillService:
    def __init__(self, db: Database, log: LogService) -> None:
        self.db = db
        self.log = log

    def create(self, payload: dict[str, Any]) -> dict:
        now = utcnow()
        cur = self.db.execute(
            """
            INSERT INTO skills(name, description, trigger_text, conditions_json, actions_json, tools_json,
                               params_json, permissions_json, version, enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (
                payload.get("name") or "Новый навык",
                payload.get("description") or "",
                (payload.get("trigger") or payload.get("trigger_text") or "").strip(),
                json.dumps(payload.get("conditions") or [], ensure_ascii=False),
                json.dumps(payload.get("actions") or [], ensure_ascii=False),
                json.dumps(payload.get("tools") or [], ensure_ascii=False),
                json.dumps(payload.get("params") or {}, ensure_ascii=False),
                json.dumps(payload.get("permissions") or [], ensure_ascii=False),
                int(payload.get("enabled", True)),
                now,
                now,
            ),
        )
        skill = self.get(cur.lastrowid)
        self._revision(skill)
        self.log.info("skill created", name=skill["name"])
        return skill

    def get(self, skill_id: int) -> dict:
        row = self.db.query_one("SELECT * FROM skills WHERE id = ?", (skill_id,))
        if not row:
            raise KeyError(skill_id)
        return self._decode(row)

    def list(self) -> list[dict]:
        return [self._decode(row) for row in self.db.query("SELECT * FROM skills ORDER BY name")]

    def update(self, skill_id: int, payload: dict[str, Any]) -> dict:
        current = self.get(skill_id)
        merged = {**current, **payload}
        self.db.execute(
            """
            UPDATE skills SET name=?, description=?, trigger_text=?, conditions_json=?, actions_json=?,
                tools_json=?, params_json=?, permissions_json=?, version=version+1, enabled=?, updated_at=?
            WHERE id=?
            """,
            (
                merged.get("name"),
                merged.get("description") or "",
                (merged.get("trigger") or merged.get("trigger_text") or "").strip(),
                json.dumps(merged.get("conditions") or [], ensure_ascii=False),
                json.dumps(merged.get("actions") or [], ensure_ascii=False),
                json.dumps(merged.get("tools") or [], ensure_ascii=False),
                json.dumps(merged.get("params") or {}, ensure_ascii=False),
                json.dumps(merged.get("permissions") or [], ensure_ascii=False),
                int(merged.get("enabled", True)),
                utcnow(),
                skill_id,
            ),
        )
        skill = self.get(skill_id)
        self._revision(skill)
        return skill

    def delete(self, skill_id: int) -> None:
        self.db.execute("DELETE FROM skills WHERE id = ?", (skill_id,))

    def set_enabled(self, skill_id: int, enabled: bool) -> dict:
        self.db.execute(
            "UPDATE skills SET enabled = ?, updated_at = ? WHERE id = ?",
            (int(enabled), utcnow(), skill_id),
        )
        return self.get(skill_id)

    def match(self, text: str) -> dict | None:
        lowered = text.strip().lower()
        for skill in self.list():
            if not skill["enabled"]:
                continue
            trigger = (skill.get("trigger") or "").strip().lower()
            if trigger and (trigger == lowered or trigger in lowered):
                return skill
        return None

    def learn_from_phrase(self, phrase: str) -> dict | None:
        """Parse 'когда я говорю X, выполняй Y' / 'всегда делай Y'."""
        lowered = phrase.strip()
        patterns = [
            ("когда я говорю", "выполняй"),
            ("когда говорю", "делай"),
            ("если я говорю", "то"),
        ]
        for left, right in patterns:
            if left in lowered.lower() and right in lowered.lower():
                part = lowered.lower()
                trigger = part.split(left, 1)[1].split(right, 1)[0].strip(" «»\"'")
                action = lowered.lower().split(right, 1)[1].strip(" .")
                if trigger and action:
                    return self.create(
                        {
                            "name": trigger[:48],
                            "description": f"Создано из фразы: {phrase}",
                            "trigger": trigger,
                            "actions": [{"type": "chat_command", "value": action}],
                        }
                    )
        if lowered.lower().startswith("всегда делай") or lowered.lower().startswith("всегда делай"):
            action = lowered.split("делай", 1)[-1].strip(" .")
            if action:
                return self.create(
                    {
                        "name": action[:48],
                        "description": "Постоянное правило",
                        "trigger": action,
                        "actions": [{"type": "chat_command", "value": action}],
                    }
                )
        return None

    def _revision(self, skill: dict) -> None:
        self.db.execute(
            "INSERT INTO skill_revisions(skill_id, version, payload, created_at) VALUES (?, ?, ?, ?)",
            (skill["id"], skill["version"], json.dumps(skill, ensure_ascii=False), utcnow()),
        )

    def _decode(self, row: dict) -> dict:
        return {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "trigger": row["trigger_text"],
            "conditions": _json(row["conditions_json"], []),
            "actions": _json(row["actions_json"], []),
            "tools": _json(row["tools_json"], []),
            "params": _json(row["params_json"], {}),
            "permissions": _json(row["permissions_json"], []),
            "version": row["version"],
            "enabled": bool(row["enabled"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


def _json(raw: str, default: Any) -> Any:
    try:
        return json.loads(raw or "")
    except json.JSONDecodeError:
        return default
