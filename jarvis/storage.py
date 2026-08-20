from __future__ import annotations

import json
import shutil
import sqlite3
import threading
import zipfile
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from jarvis.config import DATA_DIR

SCHEMA_VERSION = 1
DATABASE = DATA_DIR / "nova.db"
PROFILE_FILES = ("settings.json", "memory.json", "notes.txt", "nova.db")
_lock = threading.RLock()


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATABASE, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=WAL")
    try:
        yield db
        db.commit()
    finally:
        db.close()


def initialize() -> None:
    with _lock, connect() as db:
        version = int(db.execute("PRAGMA user_version").fetchone()[0])
        if version > SCHEMA_VERSION:
            raise RuntimeError("База данных создана более новой версией NOVA")
        if version < 1:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL DEFAULT 'long_term',
                    content TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'general',
                    importance INTEGER NOT NULL DEFAULT 3 CHECK(importance BETWEEN 1 AND 5),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS skills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT NOT NULL DEFAULT '',
                    trigger_text TEXT NOT NULL,
                    actions_json TEXT NOT NULL DEFAULT '[]',
                    permissions_json TEXT NOT NULL DEFAULT '[]',
                    version INTEGER NOT NULL DEFAULT 1,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS agents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    role TEXT NOT NULL,
                    instructions TEXT NOT NULL DEFAULT '',
                    model TEXT NOT NULL DEFAULT '',
                    tools_json TEXT NOT NULL DEFAULT '[]',
                    permissions_json TEXT NOT NULL DEFAULT '[]',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    task_type TEXT NOT NULL DEFAULT 'one-time',
                    schedule TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'pending',
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS permissions (
                    name TEXT PRIMARY KEY,
                    enabled INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level TEXT NOT NULL,
                    category TEXT NOT NULL,
                    action TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                PRAGMA user_version=1;
                """
            )


def rows(table: str) -> list[dict[str, Any]]:
    if table not in {"memories", "skills", "agents", "tasks", "permissions", "audit_log"}:
        raise ValueError("unknown table")
    initialize()
    with connect() as db:
        return [dict(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY id DESC" if table != "permissions" else "SELECT * FROM permissions ORDER BY name")]


def audit(action: str, detail: str = "", *, level: str = "INFO", category: str = "CORE") -> None:
    initialize()
    safe_detail = detail[:2000]
    with connect() as db:
        db.execute(
            "INSERT INTO audit_log(level, category, action, detail, created_at) VALUES(?,?,?,?,?)",
            (level, category, action, safe_detail, utc_now()),
        )


def create_backup(destination: Path | None = None) -> Path:
    initialize()
    backup_dir = DATA_DIR / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = destination or backup_dir / f"NOVA-profile-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
    target = target.resolve()
    with _lock, zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in PROFILE_FILES:
            path = DATA_DIR / name
            if path.exists():
                archive.write(path, name)
    audit("backup_created", target.name)
    return target


def restore_backup(source: Path) -> None:
    source = source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    automatic = create_backup()
    with _lock, zipfile.ZipFile(source) as archive:
        names = set(archive.namelist())
        if not names or any(Path(name).is_absolute() or ".." in Path(name).parts for name in names):
            raise ValueError("Небезопасный архив")
        if not names.issubset(PROFILE_FILES):
            raise ValueError("Архив содержит неизвестные файлы")
        for name in names:
            destination = DATA_DIR / name
            with archive.open(name) as src, destination.open("wb") as dst:
                shutil.copyfileobj(src, dst)
    initialize()
    audit("backup_restored", f"{source.name}; safety={automatic.name}", category="SECURITY")


def decode_json_fields(item: dict[str, Any]) -> dict[str, Any]:
    for key in tuple(item):
        if key.endswith("_json"):
            raw = item.pop(key)
            default = "{}" if key == "payload_json" else "[]"
            item[key.removesuffix("_json")] = json.loads(raw or default)
    for key in ("enabled",):
        if key in item:
            item[key] = bool(item[key])
    return item
