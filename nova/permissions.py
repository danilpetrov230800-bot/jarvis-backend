from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from nova.constants import CONFIRMATION_TTL_SEC, DANGEROUS_PERMISSIONS, DEFAULT_PERMISSIONS
from nova.db import Database, utcnow
from nova.errors import ConfirmationRequired, PermissionDenied
from nova.logging_service import LogService


class PermissionService:
    def __init__(self, db: Database, log: LogService) -> None:
        self.db = db
        self.log = log
        self._ensure_defaults()

    def _ensure_defaults(self) -> None:
        for key, allowed in DEFAULT_PERMISSIONS.items():
            existing = self.db.query_one("SELECT key FROM permissions WHERE key = ?", (key,))
            if existing:
                continue
            self.db.execute(
                "INSERT INTO permissions(key, allowed, dangerous) VALUES (?, ?, ?)",
                (key, int(allowed), int(key in DANGEROUS_PERMISSIONS)),
            )

    def all(self) -> list[dict[str, Any]]:
        rows = self.db.query("SELECT key, allowed, dangerous FROM permissions ORDER BY key")
        return [
            {
                "key": row["key"],
                "allowed": bool(row["allowed"]),
                "dangerous": bool(row["dangerous"]),
            }
            for row in rows
        ]

    def allowed(self, key: str) -> bool:
        row = self.db.query_one("SELECT allowed FROM permissions WHERE key = ?", (key,))
        if row is None:
            return DEFAULT_PERMISSIONS.get(key, False)
        return bool(row["allowed"])

    def set(self, key: str, allowed: bool) -> None:
        self.db.execute(
            "INSERT INTO permissions(key, allowed, dangerous) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET allowed = excluded.allowed",
            (key, int(allowed), int(key in DANGEROUS_PERMISSIONS)),
        )
        self.log.security("permission updated", key=key, allowed=allowed)

    def require(self, key: str) -> None:
        if not self.allowed(key):
            self.log.security("permission denied", key=key)
            raise PermissionDenied(f"Разрешение {key} выключено.")

    def require_confirmation(self, action: str, summary: str, payload: dict[str, Any]) -> None:
        token = secrets.token_urlsafe(16)
        expires = (datetime.now(timezone.utc) + timedelta(seconds=CONFIRMATION_TTL_SEC)).isoformat()
        self.db.execute(
            "INSERT INTO confirmations(token, action, payload_json, summary, expires_at) VALUES (?, ?, ?, ?, ?)",
            (token, action, json.dumps(payload, ensure_ascii=False), summary, expires),
        )
        self.log.security("confirmation required", action=action)
        raise ConfirmationRequired(token, summary, payload)

    def confirm(self, token: str) -> dict[str, Any]:
        row = self.db.query_one("SELECT * FROM confirmations WHERE token = ?", (token,))
        if not row:
            raise PermissionDenied("Подтверждение не найдено или уже использовано.")
        self.db.execute("DELETE FROM confirmations WHERE token = ?", (token,))
        expires = datetime.fromisoformat(row["expires_at"])
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < datetime.now(timezone.utc):
            raise PermissionDenied("Подтверждение истекло.")
        return {
            "action": row["action"],
            "payload": json.loads(row["payload_json"]),
            "summary": row["summary"],
        }

    def audit(self, category: str, level: str, message: str, meta: dict[str, Any] | None = None) -> None:
        self.db.execute(
            "INSERT INTO audit(category, level, message, meta_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (category, level, message, json.dumps(meta or {}, ensure_ascii=False), utcnow()),
        )
