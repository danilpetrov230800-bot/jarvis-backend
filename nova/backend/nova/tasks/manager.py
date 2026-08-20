"""Task manager for NOVA."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from nova.core.logging import get_logger
from nova.database.db import TaskRecord, get_session

logger = get_logger("nova.tasks")


class TaskManager:
    def create(self, data: dict) -> dict:
        now = datetime.now(timezone.utc)
        with get_session() as session:
            record = TaskRecord(
                title=data["title"],
                type=data.get("type", "one-time"),
                schedule=data.get("schedule", ""),
                payload_json=json.dumps(data.get("payload", {}), ensure_ascii=False),
                status="pending",
                created_at=now,
                updated_at=now,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return self._to_dict(record)

    def list_all(self, status: str | None = None) -> list[dict]:
        with get_session() as session:
            q = session.query(TaskRecord)
            if status:
                q = q.filter(TaskRecord.status == status)
            return [self._to_dict(r) for r in q.order_by(TaskRecord.created_at.desc()).all()]

    def update_status(self, task_id: int, status: str) -> dict | None:
        with get_session() as session:
            record = session.get(TaskRecord, task_id)
            if not record:
                return None
            record.status = status
            record.updated_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(record)
            return self._to_dict(record)

    def delete(self, task_id: int) -> bool:
        with get_session() as session:
            record = session.get(TaskRecord, task_id)
            if not record:
                return False
            session.delete(record)
            session.commit()
            return True

    def _to_dict(self, record: TaskRecord) -> dict:
        return {
            "id": record.id,
            "title": record.title,
            "type": record.type,
            "schedule": record.schedule,
            "payload": json.loads(record.payload_json or "{}"),
            "status": record.status,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        }


_manager: TaskManager | None = None


def get_task_manager() -> TaskManager:
    global _manager
    if _manager is None:
        _manager = TaskManager()
    return _manager
