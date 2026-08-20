from __future__ import annotations

import json
from typing import Any

from jarvis.store import connect, migrate, utc_now

DEFAULTS = (
    ("Research", "research", "Ищет и сравнивает открытые источники.", ["search", "wiki"]),
    ("Coding", "coding", "Помогает с кодом и файлами проекта.", ["files", "search"]),
    ("File", "file", "Ищет и организует файлы пользователя.", ["files"]),
    ("System", "system", "Смотрит состояние компьютера.", ["system"]),
    ("Creative", "creative", "Помогает с текстами и идеями.", ["search"]),
    ("Testing", "testing", "Проверяет NOVA и сообщает результат.", ["diagnostics"]),
    ("Automation", "automation", "Запускает навыки и программы.", ["skills", "apps"]),
)


def seed_agents() -> None:
    migrate()
    with connect() as conn:
        count = conn.execute("SELECT COUNT(*) AS n FROM agents").fetchone()["n"]
        if count:
            return
        now = utc_now()
        for name, role, instructions, tools in DEFAULTS:
            conn.execute(
                "INSERT INTO agents(name, role, instructions, tools_json, model, enabled, created_at, updated_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (name, role, instructions, json.dumps(tools), "", 1, now, now),
            )


def list_agents() -> list[dict[str, Any]]:
    seed_agents()
    with connect() as conn:
        rows = conn.execute("SELECT * FROM agents ORDER BY id").fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["tools"] = json.loads(item.pop("tools_json") or "[]")
        item["enabled"] = bool(item["enabled"])
        result.append(item)
    return result


def get_agent(ident: int) -> dict[str, Any]:
    seed_agents()
    with connect() as conn:
        row = conn.execute("SELECT * FROM agents WHERE id=?", (ident,)).fetchone()
    if not row:
        raise KeyError("agent not found")
    item = dict(row)
    item["tools"] = json.loads(item.pop("tools_json") or "[]")
    item["enabled"] = bool(item["enabled"])
    return item


def find_agent(name: str) -> dict[str, Any] | None:
    needle = name.strip().lower()
    if not needle:
        return None
    for item in list_agents():
        if item["enabled"] and (needle == item["name"].lower() or needle == item["role"].lower()):
            return item
    return None


def create_agent(
    name: str,
    role: str = "",
    instructions: str = "",
    tools: list[str] | None = None,
    model: str = "",
) -> dict[str, Any]:
    seed_agents()
    now = utc_now()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO agents(name, role, instructions, tools_json, model, enabled, created_at, updated_at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (
                name.strip(),
                (role or name).strip().lower(),
                instructions.strip() or f"Специализированный агент {name.strip()}.",
                json.dumps(tools or ["search"]),
                model.strip(),
                1,
                now,
                now,
            ),
        )
        ident = int(cur.lastrowid or 0)
    return get_agent(ident)


def toggle_agent(ident: int) -> dict[str, Any]:
    agent = get_agent(ident)
    enabled = 0 if agent["enabled"] else 1
    with connect() as conn:
        conn.execute(
            "UPDATE agents SET enabled=?, updated_at=? WHERE id=?",
            (enabled, utc_now(), ident),
        )
    return get_agent(ident)


def delete_agent(ident: int) -> bool:
    seed_agents()
    with connect() as conn:
        cur = conn.execute("DELETE FROM agents WHERE id=?", (ident,))
        return cur.rowcount > 0
