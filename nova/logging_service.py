from __future__ import annotations

import json
import logging
import logging.handlers
import re
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

from nova.constants import MAX_LOG_BYTES
from nova.paths import logs_dir

SECRET_RE = re.compile(
    r"(api[_-]?key|authorization|bearer|password|secret|token)\s*[:=]\s*([^\s,;]+)",
    re.I,
)
LONG_TOKEN_RE = re.compile(r"\b(?:sk-|ghp_|gho_|xox[baprs]-)[A-Za-z0-9_\-]{8,}\b")

LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "SECURITY": 35,
    "AGENT": 25,
}

logging.addLevelName(35, "SECURITY")
logging.addLevelName(25, "AGENT")


def redact(text: str) -> str:
    cleaned = SECRET_RE.sub(lambda m: f"{m.group(1)}=***", text)
    return LONG_TOKEN_RE.sub("***", cleaned)


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        return redact(original)


class LogService:
    def __init__(self) -> None:
        self.dir = logs_dir()
        self.path = self.dir / "nova.log"
        self.logger = logging.getLogger("nova")
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False
        if not self.logger.handlers:
            handler = logging.handlers.RotatingFileHandler(
                self.path,
                maxBytes=MAX_LOG_BYTES,
                backupCount=5,
                encoding="utf-8",
            )
            handler.setFormatter(
                RedactingFormatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
            )
            self.logger.addHandler(handler)
            stream = getattr(sys, "stderr", None) or getattr(sys, "stdout", None)
            if stream is not None:
                try:
                    console = logging.StreamHandler(stream)
                    console.setFormatter(RedactingFormatter("%(asctime)s [%(levelname)s] %(message)s"))
                    self.logger.addHandler(console)
                except Exception:
                    pass

    def emit(self, level: str, message: str, *, category: str = "INFO", extra: dict[str, Any] | None = None) -> None:
        lvl = LEVELS.get(level.upper(), logging.INFO)
        payload = redact(message)
        if extra:
            payload = f"{payload} | {redact(json.dumps(extra, ensure_ascii=False, default=str))}"
        self.logger.log(lvl, "[%s] %s", category.upper(), payload)

    def info(self, message: str, **extra: Any) -> None:
        self.emit("INFO", message, category="INFO", extra=extra or None)

    def warning(self, message: str, **extra: Any) -> None:
        self.emit("WARNING", message, category="WARNING", extra=extra or None)

    def error(self, message: str, **extra: Any) -> None:
        self.emit("ERROR", message, category="ERROR", extra=extra or None)

    def debug(self, message: str, **extra: Any) -> None:
        self.emit("DEBUG", message, category="DEBUG", extra=extra or None)

    def security(self, message: str, **extra: Any) -> None:
        self.emit("SECURITY", message, category="SECURITY", extra=extra or None)

    def agent(self, message: str, **extra: Any) -> None:
        self.emit("AGENT", message, category="AGENT", extra=extra or None)

    def tail(self, limit: int = 400) -> list[str]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8", errors="replace").splitlines()
        return [redact(line) for line in lines[-limit:]]

    def export(self, destination: Path | None = None) -> Path:
        dest = destination or (self.dir / f"nova-logs-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.txt")
        dest.write_text("\n".join(self.tail(5000)), encoding="utf-8")
        return dest
