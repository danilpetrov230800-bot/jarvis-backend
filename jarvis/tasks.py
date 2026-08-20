from __future__ import annotations

import threading
from typing import Any

from jarvis.desktop import _notify_timer
from jarvis.store import connect, migrate, utc_now


def add_task(title: str, seconds: int = 0, kind: str = "reminder") -> dict[str, Any]:
    migrate()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO tasks(title, kind, due_at, status, created_at) VALUES(?,?,?,?,?)",
            (title.strip(), kind, None, "active", utc_now()),
        )
        ident = int(cur.lastrowid or 0)
    if seconds > 0:
        threading.Timer(seconds, lambda: _notify_timer(title)).start()
    return {"id": ident, "title": title, "kind": kind, "status": "active"}


def list_tasks() -> list[dict[str, Any]]:
    migrate()
    with connect() as conn:
        rows = conn.execute("SELECT * FROM tasks ORDER BY id DESC LIMIT 50").fetchall()
    return [dict(row) for row in rows]


def cancel_task(ident: int) -> bool:
    migrate()
    with connect() as conn:
        cur = conn.execute("UPDATE tasks SET status='cancelled' WHERE id=?", (ident,))
        return cur.rowcount > 0
