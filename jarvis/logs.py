from __future__ import annotations

import re
from pathlib import Path

from jarvis.config import DATA_DIR

SECRET_RE = re.compile(r"(gsk_|sk-|sk-or-|api[_-]?key)[=: ]?[A-Za-z0-9._-]{8,}", re.I)


def redact(text: str) -> str:
    return SECRET_RE.sub("[redacted]", text)


def tail_log(lines: int = 120) -> str:
    path = DATA_DIR / "nova.log"
    if not path.exists():
        return "Лог ещё пуст."
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return redact("\n".join(content[-lines:]))
