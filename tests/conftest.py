import os
import tempfile
from pathlib import Path

_DATA = Path(tempfile.mkdtemp(prefix="nova-test-"))
os.environ["NOVA_DATA_DIR"] = str(_DATA)
os.environ["NOVA_NO_WINDOW"] = "1"
os.environ.pop("OPENAI_API_KEY", None)
os.environ.pop("NOVA_API_KEY", None)

from fastapi.testclient import TestClient

from nova.app import app, kernel

import pytest


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def nova():
    return kernel
