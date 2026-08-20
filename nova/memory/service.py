from __future__ import annotations

from nova.db import Database, utcnow
from nova.logging_service import LogService


class MemoryService:
    def __init__(self, db: Database, log: LogService) -> None:
        self.db = db
        self.log = log

    def add(
        self,
        content: str,
        *,
        kind: str = "long_term",
        category: str = "general",
        title: str = "",
        importance: int = 3,
        tags: str = "",
        source: str = "user",
    ) -> dict:
        now = utcnow()
        cur = self.db.execute(
            """
            INSERT INTO memories(kind, category, title, content, importance, tags, source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (kind, category, title or content[:48], content.strip(), int(importance), tags, source, now, now),
        )
        self.log.info("memory saved", kind=kind)
        return self.get(cur.lastrowid)

    def get(self, memory_id: int) -> dict:
        row = self.db.query_one("SELECT * FROM memories WHERE id = ?", (memory_id,))
        if not row:
            raise KeyError(memory_id)
        return row

    def list(self, kind: str | None = None, query: str | None = None, limit: int = 200) -> list[dict]:
        sql = "SELECT * FROM memories WHERE 1=1"
        params: list = []
        if kind:
            sql += " AND kind = ?"
            params.append(kind)
        if query:
            sql += " AND (content LIKE ? OR title LIKE ? OR tags LIKE ?)"
            like = f"%{query}%"
            params.extend([like, like, like])
        sql += " ORDER BY importance DESC, updated_at DESC LIMIT ?"
        params.append(limit)
        return self.db.query(sql, params)

    def update(self, memory_id: int, **fields: object) -> dict:
        allowed = {"kind", "category", "title", "content", "importance", "tags"}
        sets = []
        params: list = []
        for key, value in fields.items():
            if key in allowed and value is not None:
                sets.append(f"{key} = ?")
                params.append(value)
        if not sets:
            return self.get(memory_id)
        sets.append("updated_at = ?")
        params.append(utcnow())
        params.append(memory_id)
        self.db.execute(f"UPDATE memories SET {', '.join(sets)} WHERE id = ?", params)
        return self.get(memory_id)

    def delete(self, memory_id: int) -> None:
        self.db.execute("DELETE FROM memories WHERE id = ?", (memory_id,))

    def clear(self, kind: str | None = None) -> int:
        if kind:
            cur = self.db.execute("DELETE FROM memories WHERE kind = ?", (kind,))
        else:
            cur = self.db.execute("DELETE FROM memories")
        return cur.rowcount

    def recall(self, query: str, limit: int = 8) -> list[dict]:
        return self.list(query=query, limit=limit)

    def conversation_add(self, role: str, content: str, source: str = "text") -> None:
        self.db.execute(
            "INSERT INTO conversations(role, content, source, created_at) VALUES (?, ?, ?, ?)",
            (role, content, source, utcnow()),
        )
        self.db.execute(
            "DELETE FROM conversations WHERE id NOT IN (SELECT id FROM conversations ORDER BY id DESC LIMIT 200)"
        )

    def conversation(self, limit: int = 40) -> list[dict]:
        rows = self.db.query(
            "SELECT role, content, source, created_at FROM conversations ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return list(reversed(rows))

    def conversation_clear(self) -> None:
        self.db.execute("DELETE FROM conversations")

    def export(self) -> list[dict]:
        return self.list(limit=10_000)

    def import_rows(self, rows: list[dict]) -> int:
        count = 0
        for row in rows:
            self.add(
                row.get("content", ""),
                kind=row.get("kind", "long_term"),
                category=row.get("category", "general"),
                title=row.get("title", ""),
                importance=int(row.get("importance", 3)),
                tags=row.get("tags", ""),
                source=row.get("source", "import"),
            )
            count += 1
        return count

    def relevant_context(self, text: str, limit: int = 6) -> str:
        tokens = [part for part in text.lower().replace(",", " ").split() if len(part) > 3]
        if not tokens:
            rows = self.list(limit=limit)
        else:
            rows = []
            seen = set()
            for token in tokens[:6]:
                for row in self.list(query=token, limit=4):
                    if row["id"] not in seen:
                        seen.add(row["id"])
                        rows.append(row)
            rows = rows[:limit]
        if not rows:
            return ""
        lines = ["Известные факты о пользователе:"]
        for row in rows:
            lines.append(f"- ({row['kind']}) {row['content']}")
        return "\n".join(lines)
