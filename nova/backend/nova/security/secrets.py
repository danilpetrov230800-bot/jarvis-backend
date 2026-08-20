"""Secure secret storage."""

from __future__ import annotations

import base64
import hashlib
import os
import platform
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from nova.core.logging import get_logger
from nova.database.db import SecretRecord, get_session

logger = get_logger("nova.security.secrets")


def _derive_key() -> bytes:
    if platform.system() == "Windows":
        seed = os.environ.get("LOCALAPPDATA", "") + os.environ.get("USERNAME", "nova")
    else:
        seed = str(Path.home()) + "nova-secret-key"
    digest = hashlib.sha256(seed.encode()).digest()
    return base64.urlsafe_b64encode(digest)


class SecretStore:
    def __init__(self):
        self._fernet = Fernet(_derive_key())

    def set(self, key: str, value: str) -> None:
        encrypted = self._fernet.encrypt(value.encode()).decode()
        with get_session() as session:
            record = session.get(SecretRecord, key)
            if record:
                record.encrypted_value = encrypted
            else:
                session.add(SecretRecord(key=key, encrypted_value=encrypted))
            session.commit()
        logger.info("Secret stored: %s", key)

    def get(self, key: str) -> str | None:
        with get_session() as session:
            record = session.get(SecretRecord, key)
            if not record:
                return None
            try:
                return self._fernet.decrypt(record.encrypted_value.encode()).decode()
            except InvalidToken:
                logger.error("Failed to decrypt secret: %s", key)
                return None

    def delete(self, key: str) -> bool:
        with get_session() as session:
            record = session.get(SecretRecord, key)
            if not record:
                return False
            session.delete(record)
            session.commit()
        logger.info("Secret deleted: %s", key)
        return True

    def has(self, key: str) -> bool:
        with get_session() as session:
            return session.get(SecretRecord, key) is not None


_store: SecretStore | None = None


def get_secret_store() -> SecretStore:
    global _store
    if _store is None:
        _store = SecretStore()
    return _store
