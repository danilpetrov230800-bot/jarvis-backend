"""SQLite database layer with migrations."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    event,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from nova.core.config import get_settings
from nova.core.logging import get_logger

logger = get_logger("nova.database")

SCHEMA_VERSION = 1


class Base(DeclarativeBase):
    pass


class SettingRecord(Base):
    __tablename__ = "settings"
    key = Column(String, primary_key=True)
    value = Column(Text, nullable=False)


class MemoryRecord(Base):
    __tablename__ = "memory"
    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String, nullable=False)
    category = Column(String, default="general")
    content = Column(Text, nullable=False)
    importance = Column(Integer, default=5)
    metadata_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class SkillRecord(Base):
    __tablename__ = "skills"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    trigger = Column(String, nullable=False)
    conditions_json = Column(Text, default="[]")
    actions_json = Column(Text, nullable=False)
    tools_json = Column(Text, default="[]")
    permissions_json = Column(Text, default="[]")
    version = Column(Integer, default=1)
    enabled = Column(Boolean, default=True)
    history_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AgentRecord(Base):
    __tablename__ = "agents"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    instructions = Column(Text, default="")
    model = Column(String, default="local")
    tools_json = Column(Text, default="[]")
    permissions_json = Column(Text, default="[]")
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class TaskRecord(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    type = Column(String, default="one-time")
    schedule = Column(String, default="")
    payload_json = Column(Text, default="{}")
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    metadata_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class PermissionRecord(Base):
    __tablename__ = "permissions"
    name = Column(String, primary_key=True)
    enabled = Column(Boolean, default=False)
    dangerous = Column(Boolean, default=False)


class SecretRecord(Base):
    __tablename__ = "secrets"
    key = Column(String, primary_key=True)
    encrypted_value = Column(Text, nullable=False)


class ActionHistory(Base):
    __tablename__ = "action_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(String, nullable=False)
    details_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


_engine = None
_SessionLocal = None


def _backup_db(db_path: Path) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup = db_path.parent / "backups" / f"nova_{ts}.db"
    backup.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        shutil.copy2(db_path, backup)
        logger.info("Database backup created: %s", backup)
    return backup


def init_db() -> sessionmaker[Session]:
    global _engine, _SessionLocal
    if _SessionLocal is not None:
        return _SessionLocal

    settings = get_settings()
    db_path = settings.db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    _engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    Base.metadata.create_all(_engine)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)

    with _SessionLocal() as session:
        _run_migrations(session, db_path)

    return _SessionLocal


def _run_migrations(session: Session, db_path: Path) -> None:
    row = session.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_meta'")
    ).fetchone()
    if not row:
        session.execute(
            text("CREATE TABLE schema_meta (version INTEGER NOT NULL)")
        )
        session.execute(text("INSERT INTO schema_meta (version) VALUES (0)"))
        session.commit()

    current = session.execute(text("SELECT version FROM schema_meta")).scalar() or 0
    if current < SCHEMA_VERSION:
        _backup_db(db_path)
        session.execute(
            text("UPDATE schema_meta SET version = :v"),
            {"v": SCHEMA_VERSION},
        )
        session.commit()
        logger.info("Migrated database to version %s", SCHEMA_VERSION)

    _seed_permissions(session)


DEFAULT_PERMISSIONS = [
    ("READ_FILES", False, False),
    ("WRITE_FILES", False, True),
    ("DELETE_FILES", False, True),
    ("RUN_APPLICATIONS", False, False),
    ("SYSTEM_SETTINGS", False, True),
    ("NETWORK", False, False),
    ("SCREEN_CONTROL", False, True),
    ("MICROPHONE", False, False),
    ("CAMERA", False, True),
    ("RESEARCH_MODE", False, True),
]


def _seed_permissions(session: Session) -> None:
    for name, enabled, dangerous in DEFAULT_PERMISSIONS:
        existing = session.get(PermissionRecord, name)
        if not existing:
            session.add(PermissionRecord(name=name, enabled=enabled, dangerous=dangerous))
    session.commit()


def get_session() -> Session:
    factory = init_db()
    return factory()
