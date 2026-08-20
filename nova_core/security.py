from __future__ import annotations

import json
import os
from enum import StrEnum
from pathlib import Path
from typing import Any

from nova_core.storage import APP_DIR, Database, utcnow


class Permission(StrEnum):
    READ_FILES = "READ_FILES"
    WRITE_FILES = "WRITE_FILES"
    DELETE_FILES = "DELETE_FILES"
    RUN_APPLICATIONS = "RUN_APPLICATIONS"
    SYSTEM_SETTINGS = "SYSTEM_SETTINGS"
    NETWORK = "NETWORK"
    SCREEN_CONTROL = "SCREEN_CONTROL"
    MICROPHONE = "MICROPHONE"
    CAMERA = "CAMERA"


SAFE_DEFAULTS = {Permission.READ_FILES, Permission.RUN_APPLICATIONS}


class PermissionService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def allowed(self, permission: Permission) -> bool:
        with self.database.connect() as conn:
            row = conn.execute("SELECT allowed FROM permissions WHERE permission = ?", (permission.value,)).fetchone()
        return permission in SAFE_DEFAULTS if row is None else bool(row["allowed"])

    def set(self, permission: Permission, allowed: bool) -> None:
        with self.database.connect() as conn:
            conn.execute(
                "INSERT INTO permissions(permission, allowed, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(permission) DO UPDATE SET allowed=excluded.allowed, updated_at=excluded.updated_at",
                (permission.value, int(allowed), utcnow()),
            )
        self.audit("SECURITY", "permission_changed", f"{permission.value}={allowed}")

    def audit(self, category: str, action: str, detail: str) -> None:
        with self.database.connect() as conn:
            conn.execute(
                "INSERT INTO audit_log(category, action, detail, created_at) VALUES (?, ?, ?, ?)",
                (category, action, detail[:2000], utcnow()),
            )


class SecretStore:
    """Stores secrets outside settings. Uses per-user DPAPI on Windows."""

    def __init__(self, path: Path = APP_DIR / "secrets.dat") -> None:
        self.path = path

    def get(self, name: str) -> str:
        values = self._load()
        return str(values.get(name, ""))

    def set(self, name: str, value: str) -> None:
        values = self._load()
        if value:
            values[name] = value
        else:
            values.pop(name, None)
        self._save(values)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        payload = self.path.read_bytes()
        try:
            if os.name == "nt":
                payload = self._unprotect(payload)
            return json.loads(payload.decode("utf-8"))
        except Exception:
            return {}

    def _save(self, values: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(values, ensure_ascii=False).encode("utf-8")
        if os.name == "nt":
            payload = self._protect(payload)
        self.path.write_bytes(payload)
        if os.name != "nt":
            os.chmod(self.path, 0o600)

    @staticmethod
    def _protect(data: bytes) -> bytes:
        import ctypes
        from ctypes import wintypes

        class Blob(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        source = ctypes.create_string_buffer(data)
        in_blob = Blob(len(data), source)
        out_blob = Blob()
        if not ctypes.windll.crypt32.CryptProtectData(ctypes.byref(in_blob), "NOVA", None, None, None, 0, ctypes.byref(out_blob)):
            raise OSError("Windows could not protect the secret.")
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(out_blob.pbData)

    @staticmethod
    def _unprotect(data: bytes) -> bytes:
        import ctypes
        from ctypes import wintypes

        class Blob(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        source = ctypes.create_string_buffer(data)
        in_blob = Blob(len(data), source)
        out_blob = Blob()
        if not ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)):
            raise OSError("Windows could not read the secret.")
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(out_blob.pbData)
