from __future__ import annotations

from typing import Any

from nova.db import Database, utcnow
from nova.tools.base import ToolResult


class NotesTool:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def save(self, text: str = "", title: str = "", **_: Any) -> ToolResult:
        now = utcnow()
        cur = self.db.execute(
            "INSERT INTO notes(title, body, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (title or text[:48], text, now, now),
        )
        return ToolResult(True, "Заметка сохранена.", {"id": cur.lastrowid})

    async def list(self, **_: Any) -> ToolResult:
        rows = self.db.query("SELECT * FROM notes ORDER BY id DESC LIMIT 50")
        if not rows:
            return ToolResult(True, "Заметок пока нет.", {"notes": []})
        body = "\n".join(f"{row['id']}. {row['title']}: {row['body'][:80]}" for row in rows[:15])
        return ToolResult(True, body, {"notes": rows})
