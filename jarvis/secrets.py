from __future__ import annotations

import base64
import ctypes
import os
import sys
from ctypes import wintypes
from pathlib import Path

from jarvis.config import DATA_DIR

SECRET_FILE = DATA_DIR / ".api-key"


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(data: bytes) -> tuple[DATA_BLOB, ctypes.Array[ctypes.c_char]]:
    buffer = ctypes.create_string_buffer(data)
    return DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


def _protect(data: bytes) -> bytes:
    source, keepalive = _blob(data)
    output = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(ctypes.byref(source), "NOVA", None, None, None, 0, ctypes.byref(output)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output.pbData)


def _unprotect(data: bytes) -> bytes:
    source, keepalive = _blob(data)
    output = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(output)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output.pbData)


def save_api_key(value: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not value:
        SECRET_FILE.unlink(missing_ok=True)
        return
    if sys.platform == "win32":
        payload = b"dpapi:" + base64.b64encode(_protect(value.encode("utf-8")))
    else:
        payload = b"plain:" + base64.b64encode(value.encode("utf-8"))
    SECRET_FILE.write_bytes(payload)
    try:
        os.chmod(SECRET_FILE, 0o600)
    except OSError:
        pass


def load_api_key() -> str:
    if not SECRET_FILE.exists():
        return ""
    try:
        prefix, encoded = SECRET_FILE.read_bytes().split(b":", 1)
        payload = base64.b64decode(encoded)
        if prefix == b"dpapi" and sys.platform == "win32":
            payload = _unprotect(payload)
        elif prefix != b"plain":
            return ""
        return payload.decode("utf-8")
    except (OSError, ValueError):
        return ""
