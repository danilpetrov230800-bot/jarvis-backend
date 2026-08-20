from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from nova_core.security import Permission, PermissionService
from nova_core.storage import BACKUP_DIR, Database, backup_database, export_profile, restore_profile, utcnow


@dataclass
class MemoryRecord:
    id: str
    category: str
    content: str
    importance: int
    created_at: str
    updated_at: str


class NovaServices:
    """Business services exposed by the compatible HTTP application."""

    def __init__(self, database: Database | None = None) -> None:
        self.database = database or Database()
        self.database.initialize()
        self.permissions = PermissionService(self.database)

    def memories(self, query: str = "") -> list[dict[str, Any]]:
        sql = "SELECT * FROM memories"
        params: tuple[str, ...] = ()
        if query.strip():
            sql += " WHERE content LIKE ? OR category LIKE ?"
            needle = f"%{query.strip()}%"
            params = (needle, needle)
        sql += " ORDER BY updated_at DESC LIMIT 500"
        with self.database.connect() as conn:
            return [dict(row) for row in conn.execute(sql, params)]

    def add_memory(self, content: str, category: str = "long_term", importance: int = 0) -> dict[str, Any]:
        if not content.strip():
            raise ValueError("Текст памяти не может быть пустым.")
        if category not in {"long_term", "preference", "episodic", "semantic", "skill"}:
            raise ValueError("Недопустимая категория памяти.")
        record = MemoryRecord(str(uuid.uuid4()), category, content.strip(), max(0, min(5, importance)), utcnow(), utcnow())
        with self.database.connect() as conn:
            conn.execute(
                "INSERT INTO memories VALUES (?, ?, ?, ?, ?, ?)",
                tuple(asdict(record).values()),
            )
        self.permissions.audit("INFO", "memory_saved", f"category={category}")
        return asdict(record)

    def delete_memory(self, memory_id: str) -> None:
        with self.database.connect() as conn:
            conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))

    def skills(self) -> list[dict[str, Any]]:
        with self.database.connect() as conn:
            rows = conn.execute("SELECT * FROM skills ORDER BY updated_at DESC").fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["enabled"] = bool(item["enabled"])
            item["actions"] = json.loads(item.pop("actions_json"))
            result.append(item)
        return result

    def create_skill(self, name: str, trigger: str, actions: list[dict[str, Any]], description: str = "") -> dict[str, Any]:
        if not name.strip() or not trigger.strip() or not actions:
            raise ValueError("Skill требует имени, trigger и хотя бы одного действия.")
        permitted_actions = {"open_app", "open_url", "note", "wait"}
        if any(action.get("type") not in permitted_actions for action in actions):
            raise ValueError("Skill содержит неподдерживаемое или небезопасное действие.")
        now = utcnow()
        skill = {
            "id": str(uuid.uuid4()), "name": name.strip(), "description": description.strip(),
            "trigger_text": trigger.strip(), "actions_json": json.dumps(actions, ensure_ascii=False),
            "enabled": 1, "version": 1, "created_at": now, "updated_at": now,
        }
        with self.database.connect() as conn:
            conn.execute(
                "INSERT INTO skills VALUES (:id,:name,:description,:trigger_text,:actions_json,:enabled,:version,:created_at,:updated_at)",
                skill,
            )
        self.permissions.audit("AGENT", "skill_created", f"name={skill['name']}")
        return {**skill, "enabled": True, "actions": actions}

    def create_task(self, title: str, kind: str = "one_time", due_at: str | None = None, repeat_rule: str | None = None) -> dict[str, Any]:
        if kind not in {"one_time", "recurring", "background", "agent", "reminder"}:
            raise ValueError("Недопустимый тип задачи.")
        now = utcnow()
        task = {
            "id": str(uuid.uuid4()), "title": title.strip(), "kind": kind, "due_at": due_at,
            "repeat_rule": repeat_rule, "state": "active", "payload_json": "{}", "created_at": now, "updated_at": now,
        }
        if not task["title"]:
            raise ValueError("Задача должна иметь название.")
        with self.database.connect() as conn:
            conn.execute(
                "INSERT INTO tasks VALUES (:id,:title,:kind,:due_at,:repeat_rule,:state,:payload_json,:created_at,:updated_at)",
                task,
            )
        return {**task, "payload": {}}

    def list_tasks(self) -> list[dict[str, Any]]:
        with self.database.connect() as conn:
            rows = conn.execute("SELECT * FROM tasks ORDER BY due_at IS NULL, due_at, created_at DESC").fetchall()
        return [{**dict(row), "payload": json.loads(row["payload_json"])} for row in rows]

    def diagnostics(self) -> list[dict[str, str]]:
        checks = [
            ("database", self.database.path.exists(), "База данных доступна."),
            ("storage", self.database.path.parent.exists(), "Папка пользовательских данных доступна."),
            ("disk", shutil.disk_usage(self.database.path.parent).free > 100 * 1024 * 1024, "Проверено свободное место."),
            ("network", True, "Сетевые функции доступны при подключении к интернету."),
            ("voice", True, "Текстовый режим доступен; голос зависит от устройств Windows."),
        ]
        return [{"name": name, "status": "PASS" if ok else "FAIL", "detail": detail} for name, ok, detail in checks]

    def backup(self, destination: Path | None = None) -> Path:
        if destination is None:
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            destination = BACKUP_DIR / f"NOVA-profile-{utcnow().replace(':', '-')}.zip"
        return export_profile(destination)

    def restore(self, source: Path) -> None:
        restore_profile(source)

    def permissions_status(self) -> dict[str, bool]:
        return {item.value: self.permissions.allowed(item) for item in Permission}
