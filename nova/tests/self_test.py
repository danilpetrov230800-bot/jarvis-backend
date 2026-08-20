#!/usr/bin/env python3
"""NOVA self-test suite for production builds."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

PASSED = 0
FAILED = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  PASS  {name}")
    else:
        FAILED += 1
        print(f"  FAIL  {name} — {detail}")


async def run_tests():
    print("\n=== NOVA Self-Test ===\n")

    # TEST 01 - Import core
    try:
        from nova.core.engine import get_engine
        from nova.database.db import init_db
        check("Import NOVA Core", True)
    except Exception as e:
        check("Import NOVA Core", False, str(e))
        return

    # TEST 02 - Database
    try:
        init_db()
        check("Database init", True)
    except Exception as e:
        check("Database init", False, str(e))

    # TEST 03 - Engine init
    try:
        engine = get_engine()
        await engine.initialize()
        check("Engine initialize", True)
    except Exception as e:
        check("Engine initialize", False, str(e))

    # TEST 04 - Chat without API
    try:
        reply = await engine.process_message("Привет")
        check("Chat without API key", bool(reply), reply[:50] if reply else "empty")
    except Exception as e:
        check("Chat without API key", False, str(e))

    # TEST 05 - Calculator tool
    try:
        from nova.tools.registry import get_tool_registry
        result = await get_tool_registry().execute("calculator", {"expression": "2+2"})
        check("Calculator tool", result.get("result") == 4, str(result))
    except Exception as e:
        check("Calculator tool", False, str(e))

    # TEST 06 - System info
    try:
        result = await get_tool_registry().execute("system_info", {})
        check("System info", "cpu_percent" in result, str(result))
    except Exception as e:
        check("System info", False, str(e))

    # TEST 07 - Memory save
    try:
        from nova.memory.store import get_memory_store
        mem = get_memory_store().create(content="Test memory", type="long-term")
        check("Memory save", mem.get("id") is not None)
    except Exception as e:
        check("Memory save", False, str(e))

    # TEST 08 - Memory recall
    try:
        results = get_memory_store().search("Test memory")
        check("Memory recall", len(results) > 0)
    except Exception as e:
        check("Memory recall", False, str(e))

    # TEST 09 - Skill create
    try:
        from nova.skills.manager import get_skill_manager
        skill = get_skill_manager().create({
            "name": "Test Skill",
            "trigger": "test trigger",
            "actions": [{"type": "message", "text": "Skill works"}],
        })
        check("Skill create", skill.get("id") is not None)
    except Exception as e:
        check("Skill create", False, str(e))

    # TEST 10 - Skill execute
    try:
        result = await get_skill_manager().execute(skill["id"], {"test_mode": True})
        check("Skill execute", "results" in result)
    except Exception as e:
        check("Skill execute", False, str(e))

    # TEST 11 - Agent list
    try:
        from nova.agents.manager import get_agent_manager
        agents = get_agent_manager().list_all()
        check("Agent list", len(agents) >= 3, f"{len(agents)} agents")
    except Exception as e:
        check("Agent list", False, str(e))

    # TEST 12 - Permissions
    try:
        from nova.security.permissions import get_permission_manager
        perms = get_permission_manager().list_permissions()
        check("Permissions", len(perms) >= 9, f"{len(perms)} permissions")
    except Exception as e:
        check("Permissions", False, str(e))

    # TEST 13 - Permission denial
    try:
        result = await get_tool_registry().execute("file_delete", {"path": "/tmp/test"})
        check("Permission denial", "permission_required" in result or "error" in result)
    except Exception as e:
        check("Permission denial", False, str(e))

    # TEST 14 - Diagnostics
    try:
        from nova.diagnostics.runner import get_diagnostics
        diag = await get_diagnostics().run_all()
        check("Diagnostics", diag["overall"] in ("PASS", "WARNING"), diag["overall"])
    except Exception as e:
        check("Diagnostics", False, str(e))

    # TEST 15 - Backup
    try:
        from nova.backup.manager import get_backup_manager
        path = get_backup_manager().create_backup()
        check("Backup", Path(path).exists() or "backup" in path)
    except Exception as e:
        check("Backup", False, str(e))

    # TEST 16 - AI providers
    try:
        from nova.ai.manager import get_ai_manager
        providers = get_ai_manager().list_providers()
        check("AI providers", len(providers) >= 4, str(providers))
    except Exception as e:
        check("AI providers", False, str(e))

    # TEST 17 - Local AI chat
    try:
        from nova.ai.provider import AIMessage
        response = await get_ai_manager().chat([AIMessage(role="user", content="2+2")])
        check("Local AI chat", bool(response.content))
    except Exception as e:
        check("Local AI chat", False, str(e))

    # TEST 18 - Secret store
    try:
        from nova.security.secrets import get_secret_store
        store = get_secret_store()
        store.set("test_key", "test_value")
        val = store.get("test_key")
        store.delete("test_key")
        check("Secret store", val == "test_value")
    except Exception as e:
        check("Secret store", False, str(e))

    # TEST 19 - Tasks
    try:
        from nova.tasks.manager import get_task_manager
        task = get_task_manager().create({"title": "Test task"})
        check("Task create", task.get("id") is not None)
    except Exception as e:
        check("Task create", False, str(e))

    # TEST 20 - Offline mode
    try:
        reply = await engine.process_message("офлайн режим")
        check("Offline mode", bool(reply))
    except Exception as e:
        check("Offline mode", False, str(e))

    print(f"\n=== Results: {PASSED} passed, {FAILED} failed ===\n")
    return FAILED == 0


if __name__ == "__main__":
    ok = asyncio.run(run_tests())
    sys.exit(0 if ok else 1)
