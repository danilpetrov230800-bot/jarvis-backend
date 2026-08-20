"""
NOVA Task Scheduler & Background Job Manager
- Types: one_time, recurring, background, agent, reminder
- Cron / Interval / Timestamp scheduling
- Pause, Resume, Cancel, History, Auto-retry with backoff
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from nova.database import db
from nova.security import security_manager

log = logging.getLogger("nova.tasks")


@dataclass
class TaskItem:
    id: str
    title: str
    task_type: str # one_time, recurring, background, agent, reminder
    status: str # pending, running, completed, failed, cancelled, paused
    schedule_cron: str = ""
    scheduled_at: str | None = None
    payload: dict[str, Any] = None # type: ignore
    result: str = ""
    error: str = ""
    retry_count: int = 0
    max_retries: int = 3
    created_at: str = ""
    updated_at: str = ""


class TaskManager:
    def __init__(self):
        self._running_jobs: dict[str, asyncio.Task] = {}

    def create_task(
        self,
        title: str,
        task_type: str = "one_time",
        scheduled_at: str | None = None,
        schedule_cron: str = "",
        payload: dict[str, Any] | None = None,
        max_retries: int = 3,
        task_id: str | None = None
    ) -> TaskItem:
        t_id = task_id or str(uuid.uuid4())
        now = datetime.now().isoformat()
        payload_json = json.dumps(payload or {}, ensure_ascii=False)

        with db.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tasks (id, title, task_type, status, schedule_cron, scheduled_at, payload, result, error, retry_count, max_retries, created_at, updated_at)
                VALUES (?, ?, ?, 'pending', ?, ?, ?, '', '', 0, ?, COALESCE((SELECT created_at FROM tasks WHERE id = ?), ?), ?)
                """,
                (t_id, title, task_type, schedule_cron, scheduled_at, payload_json, max_retries, t_id, now, now)
            )
            conn.commit()

        security_manager.log_audit("INFO", "TASKS", f"Created task: {title}", {"id": t_id, "type": task_type})
        return self.get_task(t_id) # type: ignore

    def get_task(self, task_id: str) -> TaskItem | None:
        with db.get_connection() as conn:
            cur = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_task(row)

    def list_tasks(self, status: str | None = None, limit: int = 100) -> list[TaskItem]:
        sql = "SELECT * FROM tasks WHERE 1=1"
        params: list[Any] = []
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        with db.get_connection() as conn:
            cur = conn.execute(sql, params)
            return [self._row_to_task(r) for r in cur.fetchall()]

    def update_task_status(
        self,
        task_id: str,
        status: str,
        result: str = "",
        error: str = ""
    ) -> bool:
        now = datetime.now().isoformat()
        with db.get_connection() as conn:
            cur = conn.execute(
                """
                UPDATE tasks
                SET status = ?, result = CASE WHEN ? != '' THEN ? ELSE result END,
                    error = CASE WHEN ? != '' THEN ? ELSE error END, updated_at = ?
                WHERE id = ?
                """,
                (status, result, result, error, error, now, task_id)
            )
            conn.commit()
            return cur.rowcount > 0

    def cancel_task(self, task_id: str) -> bool:
        if task_id in self._running_jobs:
            self._running_jobs[task_id].cancel()
            self._running_jobs.pop(task_id, None)
        return self.update_task_status(task_id, "cancelled")

    def delete_task(self, task_id: str) -> bool:
        self.cancel_task(task_id)
        with db.get_connection() as conn:
            cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
            return cur.rowcount > 0

    def _row_to_task(self, row: Any) -> TaskItem:
        payload = {}
        try:
            payload = json.loads(row["payload"] or "{}")
        except Exception:
            pass

        return TaskItem(
            id=row["id"],
            title=row["title"],
            task_type=row["task_type"],
            status=row["status"],
            schedule_cron=row["schedule_cron"] or "",
            scheduled_at=str(row["scheduled_at"]) if row["scheduled_at"] else None,
            payload=payload,
            result=row["result"] or "",
            error=row["error"] or "",
            retry_count=row["retry_count"] or 0,
            max_retries=row["max_retries"] or 3,
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"])
        )


task_manager = TaskManager()
