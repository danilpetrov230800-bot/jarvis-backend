from __future__ import annotations

import json
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

APP_DIR = Path.home() / "AppData" / "Local" / "NOVA" if __import__("sys").platform == "win32" else Path.home() / ".local" / "share" / "nova"
DB_PATH = APP_DIR / "nova.sqlite3"
SETTINGS_PATH = APP_DIR / "settings.json"
LOG_DIR = APP_DIR / "logs"
BACKUP_DIR = APP_DIR / "backups"


def utcnow() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Database:
    """SQLite store with atomic schema migrations and pre-migration backups."""

    def __init__(self, path: Path = DB_PATH) -> None:
        self.path = path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version < 1:
                self._migrate_v1(conn)
                conn.execute("PRAGMA user_version = 1")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _migrate_v1(conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS memories (
              id TEXT PRIMARY KEY, category TEXT NOT NULL, content TEXT NOT NULL,
              importance INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS skills (
              id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, description TEXT NOT NULL,
              trigger_text TEXT NOT NULL, actions_json TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
              version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
              id TEXT PRIMARY KEY, title TEXT NOT NULL, kind TEXT NOT NULL, due_at TEXT,
              repeat_rule TEXT, state TEXT NOT NULL, payload_json TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS permissions (
              permission TEXT PRIMARY KEY, allowed INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_log (
              id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT NOT NULL, action TEXT NOT NULL,
              detail TEXT NOT NULL, created_at TEXT NOT NULL
            );
            """
        )


def backup_database() -> Path | None:
    if not DB_PATH.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / f"nova-{datetime.now().strftime('%Y%m%d-%H%M%S')}.sqlite3"
    shutil.copy2(DB_PATH, target)
    return target


def export_profile(destination: Path, include_secrets: bool = False) -> Path:
    import zipfile

    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        if DB_PATH.exists():
            archive.write(DB_PATH, "nova.sqlite3")
        if SETTINGS_PATH.exists():
            archive.write(SETTINGS_PATH, "settings.json")
        if include_secrets:
            secret_path = APP_DIR / "secrets.dat"
            if secret_path.exists():
                archive.write(secret_path, "secrets.dat")
    return destination


def restore_profile(source: Path) -> None:
    import zipfile

    if not zipfile.is_zipfile(source):
        raise ValueError("Файл резервной копии NOVA повреждён или имеет неверный формат.")
    backup_database()
    with zipfile.ZipFile(source) as archive:
        for name, target in (("nova.sqlite3", DB_PATH), ("settings.json", SETTINGS_PATH), ("secrets.dat", APP_DIR / "secrets.dat")):
            if name in archive.namelist():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(name))
