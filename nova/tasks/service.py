from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from nova.db import Database, utcnow


class TaskService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(
        self,
        title: str,
        kind: str = "one-time",
        payload: dict[str, Any] | None = None,
        schedule: str = "",
        delay_seconds: int | None = None,
    ) -> dict:
        now = utcnow()
        next_run = None
        if delay_seconds:
            next_run = (datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)).isoformat()
        elif schedule:
            next_run = schedule
        cur = self.db.execute(
            """
            INSERT INTO tasks(kind, title, payload_json, status, schedule, next_run, last_run, history_json, created_at, updated_at)
            VALUES (?, ?, ?, 'pending', ?, ?, NULL, '[]', ?, ?)
            """,
            (kind, title, json.dumps(payload or {}, ensure_ascii=False), schedule, next_run, now, now),
        )
        return self.get(cur.lastrowid)

    def get(self, task_id: int) -> dict:
        row = self.db.query_one("SELECT * FROM tasks WHERE id = ?", (task_id,))
        if not row:
            raise KeyError(task_id)
        return self._decode(row)

    def list(self) -> list[dict]:
        return [self._decode(row) for row in self.db.query("SELECT * FROM tasks ORDER BY id DESC LIMIT 200")]

    def set_status(self, task_id: int, status: str, note: str = "") -> dict:
        task = self.get(task_id)
        history = task["history"]
        history.append({"status": status, "note": note, "at": utcnow()})
        self.db.execute(
            "UPDATE tasks SET status=?, last_run=?, history_json=?, updated_at=? WHERE id=?",
            (status, utcnow(), json.dumps(history, ensure_ascii=False), utcnow(), task_id),
        )
        return self.get(task_id)

    def due(self) -> list[dict]:
        now = datetime.now(timezone.utc).isoformat()
        rows = self.db.query(
            "SELECT * FROM tasks WHERE status IN ('pending', 'scheduled') AND next_run IS NOT NULL AND next_run <= ?",
            (now,),
        )
        return [self._decode(row) for row in rows]

    def _decode(self, row: dict) -> dict:
        return {
            "id": row["id"],
            "kind": row["kind"],
            "title": row["title"],
            "payload": json.loads(row["payload_json"] or "{}"),
            "status": row["status"],
            "schedule": row["schedule"],
            "next_run": row["next_run"],
            "last_run": row["last_run"],
            "history": json.loads(row["history_json"] or "[]"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
