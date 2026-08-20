from __future__ import annotations

from nova.db import Database, utcnow


class NotifyService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def push(self, title: str, body: str, kind: str = "info") -> dict:
        cur = self.db.execute(
            "INSERT INTO notifications(kind, title, body, read, created_at) VALUES (?, ?, ?, 0, ?)",
            (kind, title, body, utcnow()),
        )
        return {"id": cur.lastrowid, "title": title, "body": body, "kind": kind}

    def list(self, limit: int = 50) -> list[dict]:
        return self.db.query("SELECT * FROM notifications ORDER BY id DESC LIMIT ?", (limit,))

    def mark_read(self, note_id: int) -> None:
        self.db.execute("UPDATE notifications SET read = 1 WHERE id = ?", (note_id,))
