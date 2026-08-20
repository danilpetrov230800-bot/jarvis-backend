"""Unit tests for NOVA backend."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    from nova.database.db import init_db
    init_db()
    yield


@pytest.mark.asyncio
async def test_local_ai_chat():
    from nova.ai.local_provider import LocalProvider
    from nova.ai.provider import AIMessage
    provider = LocalProvider()
    response = await provider.chat([AIMessage(role="user", content="привет")])
    assert response.content
    assert response.provider == "local"


@pytest.mark.asyncio
async def test_calculator():
    from nova.tools.registry import get_tool_registry
    result = await get_tool_registry().execute("calculator", {"expression": "10*5"})
    assert result["result"] == 50


@pytest.mark.asyncio
async def test_memory_crud():
    from nova.memory.store import get_memory_store
    store = get_memory_store()
    mem = store.create(content="pytest memory", type="long-term")
    assert mem["id"]
    found = store.search("pytest")
    assert len(found) >= 1
    store.delete(mem["id"])


@pytest.mark.asyncio
async def test_skill_lifecycle():
    from nova.skills.manager import get_skill_manager
    mgr = get_skill_manager()
    skill = mgr.create({
        "name": "Pytest Skill",
        "trigger": "pytest",
        "actions": [{"type": "message", "text": "ok"}],
    })
    assert skill["id"]
    result = await mgr.execute(skill["id"], {"test_mode": True})
    assert "results" in result
    mgr.delete(skill["id"])


@pytest.mark.asyncio
async def test_permission_denied():
    from nova.tools.registry import get_tool_registry
    result = await get_tool_registry().execute("file_delete", {"path": "/etc/passwd"})
    assert "permission_required" in result or "error" in result


@pytest.mark.asyncio
async def test_engine_chat():
    from nova.core.engine import get_engine
    engine = get_engine()
    await engine.initialize()
    reply = await engine.process_message("Привет, NOVA")
    assert reply
    assert "traceback" not in reply.lower()


def test_secret_store():
    from nova.security.secrets import get_secret_store
    store = get_secret_store()
    store.set("pytest", "secret123")
    assert store.get("pytest") == "secret123"
    assert store.has("pytest")
    store.delete("pytest")
    assert not store.has("pytest")


@pytest.mark.asyncio
async def test_diagnostics():
    from nova.diagnostics.runner import get_diagnostics
    result = await get_diagnostics().run_all()
    assert result["overall"] in ("PASS", "WARNING", "FAIL")
    assert len(result["checks"]) >= 5
