"""
NOVA Memory Subsystem
- Short-term: In-memory session context
- Long-term: User-verified persistent facts
- Preferences: User habits, styles, preferred apps
- Episodic: Action and task logs
- Semantic: Knowledge graph & entities
- Skill memory: Linked skill recipes
- Import / Export / Backup / Full-text search
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from nova.database import db
from nova.security import security_manager

MemoryCategory = Literal["short_term", "long_term", "preference", "episodic", "semantic", "skill"]


@dataclass
class MemoryItem:
    id: str
    category: MemoryCategory
    title: str
    content: str
    importance: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""


class MemoryManager:
    def __init__(self):
        self._short_term_buffer: list[dict[str, str]] = []

    # --- Short-term Memory (Chat Context) ---
    def add_short_term(self, role: str, content: str) -> None:
        self._short_term_buffer.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        if len(self._short_term_buffer) > 40:
            self._short_term_buffer = self._short_term_buffer[-40:]

    def get_short_term(self, limit: int = 20) -> list[dict[str, str]]:
        return self._short_term_buffer[-limit:]

    def clear_short_term(self) -> None:
        self._short_term_buffer.clear()

    # --- Persistent Memory (SQLite) ---
    def add(
        self,
        category: MemoryCategory,
        title: str,
        content: str,
        importance: int = 1,
        metadata: dict[str, Any] | None = None,
        item_id: str | None = None
    ) -> MemoryItem:
        mem_id = item_id or str(uuid.uuid4())
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)
        now = datetime.now().isoformat()

        with db.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO memory (id, category, title, content, importance, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM memory WHERE id = ?), ?), ?)
                """,
                (mem_id, category, title, content, importance, meta_json, mem_id, now, now)
            )
            conn.commit()

        security_manager.log_audit("INFO", "MEMORY", f"Added memory item: {title}", {"id": mem_id, "category": category})
        return MemoryItem(
            id=mem_id,
            category=category,
            title=title,
            content=content,
            importance=importance,
            metadata=metadata or {},
            created_at=now,
            updated_at=now
        )

    def get(self, item_id: str) -> MemoryItem | None:
        with db.get_connection() as conn:
            cur = conn.execute("SELECT * FROM memory WHERE id = ?", (item_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_item(row)

    def list_all(
        self,
        category: MemoryCategory | None = None,
        query: str | None = None,
        limit: int = 100,
        offset: int = 0
    ) -> list[MemoryItem]:
        sql = "SELECT * FROM memory WHERE 1=1"
        params: list[Any] = []

        if category:
            sql += " AND category = ?"
            params.append(category)

        if query:
            sql += " AND (title LIKE ? OR content LIKE ?)"
            q_like = f"%{query}%"
            params.extend([q_like, q_like])

        sql += " ORDER BY importance DESC, updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with db.get_connection() as conn:
            cur = conn.execute(sql, params)
            return [self._row_to_item(row) for row in cur.fetchall()]

    def delete(self, item_id: str) -> bool:
        with db.get_connection() as conn:
            cur = conn.execute("DELETE FROM memory WHERE id = ?", (item_id,))
            conn.commit()
            deleted = cur.rowcount > 0
        if deleted:
            security_manager.log_audit("INFO", "MEMORY", f"Deleted memory item: {item_id}")
        return deleted

    def clear_category(self, category: MemoryCategory) -> int:
        with db.get_connection() as conn:
            cur = conn.execute("DELETE FROM memory WHERE category = ?", (category,))
            conn.commit()
            count = cur.rowcount
        security_manager.log_audit("WARNING", "MEMORY", f"Cleared memory category: {category}", {"count": count})
        return count

    def search_relevant(self, query: str, limit: int = 5) -> list[MemoryItem]:
        words = [w.strip() for w in query.lower().split() if len(w.strip()) > 2]
        if not words:
            return self.list_all(limit=limit)

        sql = "SELECT * FROM memory WHERE " + " OR ".join(["(LOWER(title) LIKE ? OR LOWER(content) LIKE ?)" for _ in words])
        params: list[Any] = []
        for w in words:
            params.extend([f"%{w}%", f"%{w}%"])
        sql += " ORDER BY importance DESC LIMIT ?"
        params.append(limit)

        with db.get_connection() as conn:
            cur = conn.execute(sql, params)
            return [self._row_to_item(row) for row in cur.fetchall()]

    def export_json(self) -> dict[str, Any]:
        items = self.list_all(limit=10000)
        return {
            "exported_at": datetime.now().isoformat(),
            "count": len(items),
            "memories": [
                {
                    "id": i.id,
                    "category": i.category,
                    "title": i.title,
                    "content": i.content,
                    "importance": i.importance,
                    "metadata": i.metadata,
                    "created_at": i.created_at,
                    "updated_at": i.updated_at
                }
                for i in items
            ]
        }

    def import_json(self, data: dict[str, Any]) -> int:
        memories = data.get("memories", [])
        count = 0
        for item in memories:
            self.add(
                category=item.get("category", "long_term"),
                title=item.get("title", "Imported Note"),
                content=item.get("content", ""),
                importance=item.get("importance", 1),
                metadata=item.get("metadata", {}),
                item_id=item.get("id")
            )
            count += 1
        security_manager.log_audit("INFO", "MEMORY", f"Imported {count} memory records")
        return count

    def _row_to_item(self, row: Any) -> MemoryItem:
        meta = {}
        try:
            meta = json.loads(row["metadata"] or "{}")
        except Exception:
            pass
        return MemoryItem(
            id=row["id"],
            category=row["category"],
            title=row["title"],
            content=row["content"],
            importance=row["importance"],
            metadata=meta,
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"])
        )


memory_manager = MemoryManager()
