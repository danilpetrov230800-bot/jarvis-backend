from __future__ import annotations

import json
from typing import Any

from nova.constants import AGENT_ROLES
from nova.db import Database, utcnow


class AgentCatalog:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.ensure_defaults()

    def ensure_defaults(self) -> None:
        if self.db.query_one("SELECT id FROM agents LIMIT 1"):
            return
        defaults = [
            ("Research Agent", "research", "Ищет и сравнивает открытую информацию.", ["web_search", "browse_url"]),
            ("Coding Agent", "coding", "Помогает с кодом и файлами проекта.", ["read_file", "write_file", "list_files"]),
            ("File Agent", "file", "Ищет, сортирует и архивирует файлы.", ["find_files", "rename_file", "archive"]),
            ("System Agent", "system", "Следит за состоянием компьютера.", ["system_info", "list_processes"]),
            ("Creative Agent", "creative", "Пишет тексты, идеи и черновики.", []),
            ("Testing Agent", "testing", "Проверяет результаты и диагностику.", ["diagnostics"]),
            ("Automation Agent", "automation", "Запускает навыки и последовательности.", ["run_skill"]),
        ]
        now = utcnow()
        for name, role, instructions, tools in defaults:
            self.db.execute(
                """
                INSERT INTO agents(name, role, instructions, model, tools_json, permissions_json, enabled, created_at, updated_at)
                VALUES (?, ?, ?, '', ?, '[]', 1, ?, ?)
                """,
                (name, role, instructions, json.dumps(tools), now, now),
            )

    def list(self) -> list[dict[str, Any]]:
        rows = self.db.query("SELECT * FROM agents ORDER BY id")
        return [self._decode(row) for row in rows]

    def get(self, agent_id: int) -> dict[str, Any]:
        row = self.db.query_one("SELECT * FROM agents WHERE id = ?", (agent_id,))
        if not row:
            raise KeyError(agent_id)
        return self._decode(row)

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = utcnow()
        role = payload.get("role") or "general"
        if role not in AGENT_ROLES:
            role = "general"
        cur = self.db.execute(
            """
            INSERT INTO agents(name, role, instructions, model, tools_json, permissions_json, enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("name") or "Новый агент",
                role,
                payload.get("instructions") or "",
                payload.get("model") or "",
                json.dumps(payload.get("tools") or [], ensure_ascii=False),
                json.dumps(payload.get("permissions") or [], ensure_ascii=False),
                int(payload.get("enabled", True)),
                now,
                now,
            ),
        )
        return self.get(cur.lastrowid)

    def update(self, agent_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        current = self.get(agent_id)
        merged = {**current, **payload}
        self.db.execute(
            """
            UPDATE agents SET name=?, role=?, instructions=?, model=?, tools_json=?, permissions_json=?, enabled=?, updated_at=?
            WHERE id=?
            """,
            (
                merged["name"],
                merged.get("role") or "general",
                merged.get("instructions") or "",
                merged.get("model") or "",
                json.dumps(merged.get("tools") or [], ensure_ascii=False),
                json.dumps(merged.get("permissions") or [], ensure_ascii=False),
                int(merged.get("enabled", True)),
                utcnow(),
                agent_id,
            ),
        )
        return self.get(agent_id)

    def delete(self, agent_id: int) -> None:
        self.db.execute("DELETE FROM agents WHERE id = ?", (agent_id,))

    def find_by_role(self, role: str) -> dict[str, Any] | None:
        row = self.db.query_one("SELECT * FROM agents WHERE role = ? AND enabled = 1 LIMIT 1", (role,))
        return self._decode(row) if row else None

    def _decode(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "role": row["role"],
            "instructions": row["instructions"],
            "model": row["model"],
            "tools": json.loads(row["tools_json"] or "[]"),
            "permissions": json.loads(row["permissions_json"] or "[]"),
            "enabled": bool(row["enabled"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
