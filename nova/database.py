"""
NOVA SQLite Database Manager with Migrations and Backups
"""
from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from nova.config import DB_PATH, BACKUPS_DIR

log = logging.getLogger(__name__)

CURRENT_SCHEMA_VERSION = 1


class Database:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def _init_db(self) -> None:
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor = conn.execute("SELECT MAX(version) FROM schema_version")
            row = cursor.fetchone()
            current_ver = row[0] if (row and row[0] is not None) else 0

            if current_ver < 1:
                self._migrate_v1(conn)
                conn.execute("INSERT INTO schema_version (version) VALUES (1)")
                conn.commit()

    def _migrate_v1(self, conn: sqlite3.Connection) -> None:
        # Settings KV
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Memory Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                id TEXT PRIMARY KEY,
                category TEXT NOT NULL, -- short_term, long_term, preference, episodic, semantic, skill
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                importance INTEGER DEFAULT 1,
                metadata TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_cat ON memory(category)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_title ON memory(title)")

        # Skills Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS skills (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                trigger_type TEXT NOT NULL, -- phrase, regex, schedule, event
                trigger_value TEXT NOT NULL,
                conditions TEXT DEFAULT '[]',
                actions TEXT NOT NULL, -- JSON array of action definitions
                permissions TEXT DEFAULT '[]',
                enabled INTEGER DEFAULT 1,
                version INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_skills_trigger ON skills(trigger_type, trigger_value)")

        # Agents Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                system_prompt TEXT NOT NULL,
                model TEXT DEFAULT 'default',
                tools TEXT DEFAULT '[]',
                permissions TEXT DEFAULT '[]',
                enabled INTEGER DEFAULT 1,
                is_system INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tasks Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                task_type TEXT NOT NULL, -- one_time, recurring, background, agent, reminder
                status TEXT DEFAULT 'pending', -- pending, running, completed, failed, cancelled, paused
                schedule_cron TEXT DEFAULT '',
                scheduled_at TIMESTAMP,
                payload TEXT DEFAULT '{}',
                result TEXT DEFAULT '',
                error TEXT DEFAULT '',
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")

        # Audit / Logs Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,
                category TEXT NOT NULL,
                message TEXT NOT NULL,
                details TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_level ON audit_logs(level)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at)")

        # Research / OSINT Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS research_targets (
                id TEXT PRIMARY KEY,
                query TEXT NOT NULL,
                target_type TEXT NOT NULL, -- person, company, domain, general
                status TEXT DEFAULT 'completed',
                sources TEXT DEFAULT '[]',
                findings TEXT DEFAULT '[]',
                notes TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def create_backup(self, label: str = "auto") -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = BACKUPS_DIR / f"nova_backup_{label}_{timestamp}.db"
        with self.get_connection() as conn:
            bck = sqlite3.connect(str(backup_file))
            with bck:
                conn.backup(bck)
            bck.close()
        log.info(f"Created database backup: {backup_file}")
        return backup_file

    def restore_backup(self, backup_file: Path) -> bool:
        if not backup_file.exists():
            return False
        # Create safety backup first
        self.create_backup(label="pre_restore_safety")
        bck = sqlite3.connect(str(backup_file))
        with self.get_connection() as conn:
            with conn:
                bck.backup(conn)
        bck.close()
        log.info(f"Restored database from {backup_file}")
        return True


db = Database()
