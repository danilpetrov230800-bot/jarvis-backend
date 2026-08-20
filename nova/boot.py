from __future__ import annotations

import multiprocessing
import os
import sys
import traceback
from pathlib import Path


def _null_stream(mode: str):
    return open(os.devnull, mode, encoding="utf-8", errors="replace")


def ensure_stdio() -> None:
    """Windowed PyInstaller builds leave stdin/stdout/stderr as None."""
    if sys.stdin is None:
        sys.stdin = _null_stream("r")
    if sys.stdout is None:
        sys.stdout = _null_stream("w")
    if sys.stderr is None:
        sys.stderr = _null_stream("w")


def crash_path() -> Path:
    override = os.environ.get("NOVA_DATA_DIR", "").strip()
    if override:
        base = Path(override)
    elif sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "NOVA"
    else:
        base = Path.home() / ".local" / "share" / "nova"
    base.mkdir(parents=True, exist_ok=True)
    return base / "crash.txt"


def write_crash(exc: BaseException | None = None) -> None:
    try:
        text = traceback.format_exc() if exc is None else "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )
        crash_path().write_text(text or "NOVA crashed.", encoding="utf-8")
    except Exception:
        pass


def prepare() -> None:
    multiprocessing.freeze_support()
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    ensure_stdio()
    sys.excepthook = _hook


def _hook(exc_type, exc, tb) -> None:
    try:
        write_crash(exc)
    finally:
        sys.__excepthook__(exc_type, exc, tb)
