"""Structured logging for NOVA."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nova.core.config import get_settings

SENSITIVE_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),
    re.compile(r"api[_-]?key[\"'\s:=]+[\"']?[a-zA-Z0-9_-]+", re.I),
    re.compile(r"password[\"'\s:=]+[\"']?[^\s\"']+", re.I),
    re.compile(r"token[\"'\s:=]+[\"']?[a-zA-Z0-9._-]+", re.I),
]


def _redact(message: str) -> str:
    result = message
    for pattern in SENSITIVE_PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result


class NovaLogHandler(logging.Handler):
    def __init__(self, log_dir: Path):
        super().__init__()
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._file = open(self.log_dir / "nova.log", "a", encoding="utf-8")

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = _redact(self.format(record))
            self._file.write(msg + "\n")
            self._file.flush()
        except Exception:
            self.handleError(record)


def setup_logging() -> logging.Logger:
    settings = get_settings()
    logger = logging.getLogger("nova")
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    file_handler = NovaLogHandler(settings.logs_dir)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "nova") -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)


class AuditLog:
    def __init__(self):
        settings = get_settings()
        self.path = settings.logs_dir / "audit.log"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, category: str, action: str, details: dict[str, Any] | None = None) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "category": category,
            "action": action,
            "details": details or {},
        }
        line = _redact(str(entry))
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line + "\n")


_audit: AuditLog | None = None


def get_audit_log() -> AuditLog:
    global _audit
    if _audit is None:
        _audit = AuditLog()
    return _audit
