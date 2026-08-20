"""Permission system for NOVA tools."""

from __future__ import annotations

from nova.core.logging import get_audit_log, get_logger
from nova.database.db import PermissionRecord, get_session

logger = get_logger("nova.security.permissions")
audit = get_audit_log()


class PermissionDenied(Exception):
    def __init__(self, permission: str):
        self.permission = permission
        super().__init__(f"Permission denied: {permission}")


class PermissionManager:
    def list_permissions(self) -> list[dict]:
        with get_session() as session:
            records = session.query(PermissionRecord).all()
            return [
                {
                    "name": r.name,
                    "enabled": r.enabled,
                    "dangerous": r.dangerous,
                }
                for r in records
            ]

    def is_enabled(self, name: str) -> bool:
        with get_session() as session:
            record = session.get(PermissionRecord, name)
            return bool(record and record.enabled)

    def set_enabled(self, name: str, enabled: bool) -> None:
        with get_session() as session:
            record = session.get(PermissionRecord, name)
            if not record:
                raise ValueError(f"Unknown permission: {name}")
            record.enabled = enabled
            session.commit()
        audit.record("SECURITY", "permission_changed", {"name": name, "enabled": enabled})
        logger.info("Permission %s set to %s", name, enabled)

    def require(self, name: str) -> None:
        if not self.is_enabled(name):
            audit.record("SECURITY", "permission_denied", {"name": name})
            raise PermissionDenied(name)


_manager: PermissionManager | None = None


def get_permission_manager() -> PermissionManager:
    global _manager
    if _manager is None:
        _manager = PermissionManager()
    return _manager
