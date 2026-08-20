"""Memory system for NOVA."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from nova.core.logging import get_logger
from nova.database.db import MemoryRecord, get_session

logger = get_logger("nova.memory")

MEMORY_TYPES = ("short-term", "long-term", "preferences", "episodic", "semantic", "skill")


class MemoryStore:
    def create(
        self,
        content: str,
        type: str = "long-term",
        category: str = "general",
        importance: int = 5,
        metadata: dict | None = None,
        require_confirmation: bool = False,
    ) -> dict:
        if type not in MEMORY_TYPES:
            raise ValueError(f"Invalid memory type: {type}")

        now = datetime.now(timezone.utc)
        with get_session() as session:
            record = MemoryRecord(
                type=type,
                category=category,
                content=content,
                importance=importance,
                metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
                created_at=now,
                updated_at=now,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            logger.info("Memory created: id=%s type=%s", record.id, type)
            return self._to_dict(record)

    def get(self, memory_id: int) -> dict | None:
        with get_session() as session:
            record = session.get(MemoryRecord, memory_id)
            return self._to_dict(record) if record else None

    def search(self, query: str, type: str | None = None, limit: int = 20) -> list[dict]:
        with get_session() as session:
            q = session.query(MemoryRecord)
            if type:
                q = q.filter(MemoryRecord.type == type)
            q = q.filter(MemoryRecord.content.ilike(f"%{query}%"))
            q = q.order_by(MemoryRecord.importance.desc(), MemoryRecord.updated_at.desc())
            return [self._to_dict(r) for r in q.limit(limit).all()]

    def list_all(self, type: str | None = None, limit: int = 100) -> list[dict]:
        with get_session() as session:
            q = session.query(MemoryRecord)
            if type:
                q = q.filter(MemoryRecord.type == type)
            q = q.order_by(MemoryRecord.updated_at.desc())
            return [self._to_dict(r) for r in q.limit(limit).all()]

    def update(self, memory_id: int, **kwargs: Any) -> dict | None:
        with get_session() as session:
            record = session.get(MemoryRecord, memory_id)
            if not record:
                return None
            for key in ("content", "category", "importance", "type"):
                if key in kwargs:
                    setattr(record, key, kwargs[key])
            if "metadata" in kwargs:
                record.metadata_json = json.dumps(kwargs["metadata"], ensure_ascii=False)
            record.updated_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(record)
            return self._to_dict(record)

    def delete(self, memory_id: int) -> bool:
        with get_session() as session:
            record = session.get(MemoryRecord, memory_id)
            if not record:
                return False
            session.delete(record)
            session.commit()
            return True

    def clear(self, type: str | None = None) -> int:
        with get_session() as session:
            q = session.query(MemoryRecord)
            if type:
                q = q.filter(MemoryRecord.type == type)
            count = q.count()
            q.delete()
            session.commit()
            return count

    def export_all(self) -> list[dict]:
        return self.list_all(limit=10000)

    def import_records(self, records: list[dict]) -> int:
        count = 0
        for r in records:
            self.create(
                content=r["content"],
                type=r.get("type", "long-term"),
                category=r.get("category", "general"),
                importance=r.get("importance", 5),
                metadata=r.get("metadata"),
            )
            count += 1
        return count

    def _to_dict(self, record: MemoryRecord) -> dict:
        return {
            "id": record.id,
            "type": record.type,
            "category": record.category,
            "content": record.content,
            "importance": record.importance,
            "metadata": json.loads(record.metadata_json or "{}"),
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        }


_store: MemoryStore | None = None


def get_memory_store() -> MemoryStore:
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store
