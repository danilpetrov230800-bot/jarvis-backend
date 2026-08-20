from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from pathlib import Path
from typing import Any, Callable

from jarvis.permissions import require
from jarvis.storage import audit, connect, decode_json_fields, initialize, utc_now

NAME_RE = re.compile(r"^[\w .А-Яа-яЁё-]{1,80}$")
VALID_MEMORY_KINDS = {"short_term", "long_term", "preference", "episodic", "semantic", "skill"}
VALID_TASK_TYPES = {"one-time", "recurring", "background", "agent", "reminder"}


def _valid_name(value: str) -> str:
    value = value.strip()
    if not NAME_RE.fullmatch(value):
        raise ValueError("Недопустимое имя")
    return value


def list_records(table: str) -> list[dict[str, Any]]:
    if table not in {"memories", "skills", "agents", "tasks"}:
        raise ValueError("unknown collection")
    initialize()
    with connect() as db:
        data = [decode_json_fields(dict(row)) for row in db.execute(f"SELECT * FROM {table} ORDER BY updated_at DESC")]
    return data


def delete_record(table: str, record_id: int) -> bool:
    if table not in {"memories", "skills", "agents", "tasks"}:
        raise ValueError("unknown collection")
    initialize()
    with connect() as db:
        cursor = db.execute(f"DELETE FROM {table} WHERE id=?", (record_id,))
    if cursor.rowcount:
        audit("record_deleted", f"{table}:{record_id}", category="DATA")
    return bool(cursor.rowcount)


def save_memory(content: str, kind: str = "long_term", category: str = "general", importance: int = 3) -> dict[str, Any]:
    content = content.strip()
    if not content or len(content) > 10_000:
        raise ValueError("Текст памяти должен содержать от 1 до 10000 символов")
    if kind not in VALID_MEMORY_KINDS:
        raise ValueError("Неизвестный тип памяти")
    if not 1 <= importance <= 5:
        raise ValueError("Важность должна быть от 1 до 5")
    stamp = utc_now()
    initialize()
    with connect() as db:
        cursor = db.execute(
            "INSERT INTO memories(kind,content,category,importance,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (kind, content, category.strip()[:80] or "general", importance, stamp, stamp),
        )
        record_id = int(cursor.lastrowid)
    audit("memory_saved", f"id={record_id}", category="MEMORY")
    return next(item for item in list_records("memories") if item["id"] == record_id)


def search_memory(query: str) -> list[dict[str, Any]]:
    initialize()
    escaped = query.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    with connect() as db:
        return [
            dict(row)
            for row in db.execute(
                "SELECT * FROM memories WHERE content LIKE ? ESCAPE '\\' OR category LIKE ? ESCAPE '\\' ORDER BY importance DESC, updated_at DESC",
                (f"%{escaped}%", f"%{escaped}%"),
            )
        ]


def save_skill(data: dict[str, Any]) -> dict[str, Any]:
    name = _valid_name(str(data.get("name", "")))
    trigger = str(data.get("trigger", "")).strip()
    actions = data.get("actions", [])
    permissions = data.get("permissions", [])
    if not trigger or len(trigger) > 500 or not isinstance(actions, list) or not actions:
        raise ValueError("Skill требует trigger и хотя бы одно действие")
    stamp = utc_now()
    initialize()
    with connect() as db:
        existing = db.execute("SELECT id, version, created_at FROM skills WHERE name=?", (name,)).fetchone()
        if existing:
            record_id, version, created = existing["id"], existing["version"] + 1, existing["created_at"]
            db.execute(
                """UPDATE skills SET description=?, trigger_text=?, actions_json=?, permissions_json=?,
                   version=?, enabled=?, updated_at=? WHERE id=?""",
                (str(data.get("description", ""))[:1000], trigger, json.dumps(actions, ensure_ascii=False),
                 json.dumps(permissions), version, int(data.get("enabled", True)), stamp, record_id),
            )
        else:
            created, version = stamp, 1
            cursor = db.execute(
                """INSERT INTO skills(name,description,trigger_text,actions_json,permissions_json,version,enabled,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (name, str(data.get("description", ""))[:1000], trigger, json.dumps(actions, ensure_ascii=False),
                 json.dumps(permissions), version, int(data.get("enabled", True)), created, stamp),
            )
            record_id = int(cursor.lastrowid)
    audit("skill_saved", f"{name} v{version}", category="SKILL")
    return next(item for item in list_records("skills") if item["id"] == record_id)


def save_agent(data: dict[str, Any]) -> dict[str, Any]:
    name = _valid_name(str(data.get("name", "")))
    role = str(data.get("role", "")).strip()
    if not role:
        raise ValueError("Укажите роль агента")
    stamp = utc_now()
    initialize()
    with connect() as db:
        cursor = db.execute(
            """INSERT INTO agents(name,role,instructions,model,tools_json,permissions_json,enabled,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?)
               ON CONFLICT(name) DO UPDATE SET role=excluded.role,instructions=excluded.instructions,
               model=excluded.model,tools_json=excluded.tools_json,permissions_json=excluded.permissions_json,
               enabled=excluded.enabled,updated_at=excluded.updated_at""",
            (name, role[:500], str(data.get("instructions", ""))[:5000], str(data.get("model", ""))[:200],
             json.dumps(data.get("tools", [])), json.dumps(data.get("permissions", [])),
             int(data.get("enabled", True)), stamp, stamp),
        )
        record_id = int(cursor.lastrowid or db.execute("SELECT id FROM agents WHERE name=?", (name,)).fetchone()["id"])
    audit("agent_saved", name, category="AGENT")
    return next(item for item in list_records("agents") if item["id"] == record_id)


def save_task(data: dict[str, Any]) -> dict[str, Any]:
    title = str(data.get("title", "")).strip()
    task_type = str(data.get("task_type", "one-time"))
    if not title or len(title) > 500 or task_type not in VALID_TASK_TYPES:
        raise ValueError("Некорректная задача")
    stamp = utc_now()
    initialize()
    with connect() as db:
        cursor = db.execute(
            "INSERT INTO tasks(title,task_type,schedule,status,payload_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
            (title, task_type, str(data.get("schedule", ""))[:200], "pending",
             json.dumps(data.get("payload", {}), ensure_ascii=False), stamp, stamp),
        )
        record_id = int(cursor.lastrowid)
    audit("task_created", f"id={record_id}", category="TASK")
    return next(item for item in list_records("tasks") if item["id"] == record_id)


def run_bounded(action: Callable[[], Any], *, timeout: float = 30, retry_limit: int = 1) -> Any:
    timeout = min(max(timeout, 0.1), 300)
    retry_limit = min(max(retry_limit, 0), 3)
    last_error: BaseException | None = None
    for attempt in range(retry_limit + 1):
        pool = ThreadPoolExecutor(max_workers=1)
        future = pool.submit(action)
        try:
            return future.result(timeout=timeout)
        except FutureTimeout as exc:
            future.cancel()
            last_error = TimeoutError(f"Операция превысила лимит {timeout:g} сек.")
            audit("operation_timeout", f"attempt={attempt + 1}", level="WARNING", category="AGENT")
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            audit("operation_retry", f"attempt={attempt + 1}; {type(exc).__name__}", level="WARNING", category="AGENT")
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
    assert last_error is not None
    raise last_error


def safe_user_path(raw: str, *, permission: str) -> Path:
    require(permission)
    path = Path(raw).expanduser().resolve()
    allowed_roots = [Path.home().resolve()]
    if not any(path == root or root in path.parents for root in allowed_roots):
        raise ValueError("Доступ разрешён только внутри профиля пользователя")
    return path
