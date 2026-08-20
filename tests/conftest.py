import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jarvis.app import app  # noqa: E402


@pytest.fixture(autouse=True)
def _offline_fast(monkeypatch):
    monkeypatch.setattr("jarvis.offline.is_offline", lambda force=False: False)
    monkeypatch.setattr("jarvis.app.is_offline", lambda force=False: False)


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.chdir(ROOT)
    return TestClient(app)
