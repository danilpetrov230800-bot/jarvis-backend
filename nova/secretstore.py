from __future__ import annotations

import os
import sys
from pathlib import Path

from nova.paths import secrets_path


class SecretStore:
    """OS-protected secret storage. Never logs values."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or secrets_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def set(self, name: str, value: str) -> None:
        blob = self._load()
        if value:
            blob[name] = value
        elif name in blob:
            del blob[name]
        self._save(blob)

    def get(self, name: str, default: str = "") -> str:
        env = os.environ.get(name, "").strip()
        if env:
            return env
        return self._load().get(name, default)

    def delete(self, name: str) -> None:
        blob = self._load()
        blob.pop(name, None)
        self._save(blob)

    def has(self, name: str) -> bool:
        return bool(self.get(name))

    def names(self) -> list[str]:
        return sorted(self._load().keys())

    def export_plain(self) -> dict[str, str]:
        return dict(self._load())

    def _load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        raw = self.path.read_bytes()
        text = self._unprotect(raw)
        result: dict[str, str] = {}
        for line in text.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                result[key] = value
        return result

    def _save(self, blob: dict[str, str]) -> None:
        text = "\n".join(f"{k}={v}" for k, v in blob.items())
        data = self._protect(text)
        self.path.write_bytes(data)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def _protect(self, text: str) -> bytes:
        payload = text.encode("utf-8")
        if sys.platform == "win32":
            protected = _dpapi_protect(payload)
            if protected:
                return b"DPAPI" + protected
        return b"PLAIN" + payload

    def _unprotect(self, raw: bytes) -> str:
        if raw.startswith(b"DPAPI"):
            return _dpapi_unprotect(raw[5:]).decode("utf-8", errors="replace")
        if raw.startswith(b"PLAIN"):
            return raw[5:].decode("utf-8", errors="replace")
        return raw.decode("utf-8", errors="replace")


def _dpapi_protect(data: bytes) -> bytes:
    try:
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        buffer = ctypes.create_string_buffer(data)
        blob_in = DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
        blob_out = DATA_BLOB()
        if not crypt32.CryptProtectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
            return b""
        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            kernel32.LocalFree(blob_out.pbData)
    except Exception:
        return b""


def _dpapi_unprotect(data: bytes) -> bytes:
    try:
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        buffer = ctypes.create_string_buffer(data)
        blob_in = DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
        blob_out = DATA_BLOB()
        if not crypt32.CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
            return b""
        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            kernel32.LocalFree(blob_out.pbData)
    except Exception:
        return b""
