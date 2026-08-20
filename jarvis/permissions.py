from __future__ import annotations

from dataclasses import dataclass

from jarvis.storage import audit, connect, initialize, utc_now

PERMISSIONS = {
    "READ_FILES": False,
    "WRITE_FILES": False,
    "DELETE_FILES": False,
    "RUN_APPLICATIONS": True,
    "SYSTEM_SETTINGS": False,
    "NETWORK": True,
    "SCREEN_CONTROL": False,
    "MICROPHONE": False,
    "CAMERA": False,
    "RESEARCH": False,
}
DANGEROUS = {"DELETE_FILES", "SYSTEM_SETTINGS", "SCREEN_CONTROL", "CAMERA", "RESEARCH"}


@dataclass(slots=True)
class PermissionDenied(RuntimeError):
    permission: str

    def __str__(self) -> str:
        return f"Разрешение {self.permission} отключено"


def initialize_permissions() -> None:
    initialize()
    with connect() as db:
        for name, enabled in PERMISSIONS.items():
            db.execute(
                "INSERT OR IGNORE INTO permissions(name, enabled, updated_at) VALUES(?,?,?)",
                (name, int(enabled), utc_now()),
            )


def list_permissions() -> list[dict[str, object]]:
    initialize_permissions()
    with connect() as db:
        return [
            {"name": row["name"], "enabled": bool(row["enabled"]), "dangerous": row["name"] in DANGEROUS}
            for row in db.execute("SELECT name, enabled FROM permissions ORDER BY name")
        ]


def set_permission(name: str, enabled: bool) -> dict[str, object]:
    if name not in PERMISSIONS:
        raise ValueError("Неизвестное разрешение")
    initialize_permissions()
    with connect() as db:
        db.execute("UPDATE permissions SET enabled=?, updated_at=? WHERE name=?", (int(enabled), utc_now(), name))
    audit("permission_changed", f"{name}={'enabled' if enabled else 'disabled'}", category="SECURITY")
    return {"name": name, "enabled": enabled, "dangerous": name in DANGEROUS}


def require(name: str) -> None:
    initialize_permissions()
    with connect() as db:
        row = db.execute("SELECT enabled FROM permissions WHERE name=?", (name,)).fetchone()
    if not row or not bool(row["enabled"]):
        audit("permission_denied", name, level="WARNING", category="SECURITY")
        raise PermissionDenied(name)
