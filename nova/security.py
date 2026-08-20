"""
NOVA Security & Audit System
- Redacts secrets (API keys, tokens, passwords)
- Permission validations
- Structured audit logging to DB and rotating log files
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from nova.config import LOGS_DIR, SecuritySettings
from nova.database import db

log = logging.getLogger("nova.security")

# Secret redaction patterns
SECRET_PATTERNS = [
    (re.compile(r"sk-[a-zA-Z0-9_-]{20,}", re.I), "[REDACTED_API_KEY]"),
    (re.compile(r"bearer\s+[a-zA-Z0-9_\-\.]{20,}", re.I), "Bearer [REDACTED_TOKEN]"),
    (re.compile(r"(password|secret|token|api_key|apikey)\s*[:=]\s*['\"]?([^\s'\"]+)['\"]?", re.I), r"\1=[REDACTED]"),
]


def redact_secrets(text: str) -> str:
    if not isinstance(text, str):
        return text
    result = text
    for pattern, repl in SECRET_PATTERNS:
        result = pattern.sub(repl, result)
    return result


class SecurityManager:
    def __init__(self):
        self._load_settings()

    def _load_settings(self) -> SecuritySettings:
        with db.get_connection() as conn:
            cur = conn.execute("SELECT value FROM settings WHERE key = 'security'")
            row = cur.fetchone()
            if row:
                try:
                    return SecuritySettings.model_validate_json(row["value"])
                except Exception:
                    pass
        return SecuritySettings()

    def get_settings(self) -> SecuritySettings:
        return self._load_settings()

    def update_settings(self, settings: SecuritySettings) -> None:
        with db.get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES ('security', ?, CURRENT_TIMESTAMP)",
                (settings.model_dump_json(),)
            )
            conn.commit()
        self.log_audit("INFO", "SECURITY", "Security permissions updated", settings.model_dump())

    def check_permission(self, permission: str, is_dangerous: bool = False, confirmed: bool = False) -> tuple[bool, str]:
        settings = self.get_settings()
        perm_map = {
            "READ_FILES": settings.allow_file_read,
            "WRITE_FILES": settings.allow_file_write,
            "DELETE_FILES": settings.allow_file_delete,
            "RUN_APPLICATIONS": settings.allow_app_launch,
            "SYSTEM_CONTROL": settings.allow_system_control,
            "NETWORK": settings.allow_network,
            "SCREEN_CAPTURE": settings.allow_screen_capture,
            "MICROPHONE": settings.allow_microphone,
            "CMD_EXECUTION": settings.allow_cmd_execution,
        }
        
        allowed = perm_map.get(permission, True)
        if not allowed:
            self.log_audit("WARNING", "SECURITY", f"Permission denied for {permission}")
            return False, f"Действие заблокировано: разрешение {permission} отключено в настройках безопасности."
            
        if is_dangerous and settings.require_confirmation_for_dangerous and not confirmed:
            return False, f"Требуется подтверждение пользователя для выполнения опасной операции ({permission})."

        return True, "OK"

    def log_audit(self, level: str, category: str, message: str, details: dict[str, Any] | None = None) -> None:
        clean_msg = redact_secrets(message)
        clean_details = json.dumps(details or {}, ensure_ascii=False)
        clean_details = redact_secrets(clean_details)

        try:
            with db.get_connection() as conn:
                conn.execute(
                    "INSERT INTO audit_logs (level, category, message, details) VALUES (?, ?, ?, ?)",
                    (level.upper(), category.upper(), clean_msg, clean_details)
                )
                conn.commit()
        except Exception as e:
            log.error(f"Failed to write audit log to DB: {e}")

        # Also write to file
        log_file = LOGS_DIR / f"nova_{datetime.now().strftime('%Y%m%d')}.log"
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().isoformat()}] [{level.upper()}] [{category.upper()}] {clean_msg} | {clean_details}\n")
        except Exception:
            pass


security_manager = SecurityManager()
