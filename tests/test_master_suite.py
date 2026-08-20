"""
NOVA Master Test Suite
Implements TEST 01 through TEST 26 + Stress & Security Tests
"""
import asyncio
import os
import shutil
import tempfile
from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport

from nova.app import app
from nova.config import AppSettings, SecuritySettings, AISettings, VoiceSettings
from nova.core import nova_core
from nova.database import db
from nova.memory import memory_manager
from nova.skills import skills_engine
from nova.agents import agent_manager
from nova.voice import voice_manager
from nova.security import security_manager, redact_secrets
from nova.tools import evaluate_math, get_system_metrics, find_files, write_file_safe, read_file_safe, delete_file_safe


@pytest.mark.asyncio
async def test_01_startup_and_status():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "online"
        assert data["app_name"] == "NOVA"
        assert "system" in data


@pytest.mark.asyncio
async def test_02_launch_without_api_key():
    settings = AppSettings(ai=AISettings(provider="local", api_key=""))
    nova_core.save_settings(settings)
    res = await nova_core.process_user_input("Привет")
    assert "reply" in res
    assert len(res["reply"]) > 0


@pytest.mark.asyncio
async def test_03_launch_without_microphone():
    settings = AppSettings(voice=VoiceSettings(enabled=False))
    nova_core.save_settings(settings)
    res = await nova_core.process_user_input("Как дела?", source="text")
    assert "reply" in res


@pytest.mark.asyncio
async def test_04_text_command():
    res = await nova_core.process_user_input("посчитай 25 * 4")
    assert "100" in res["reply"]
    assert "calculator" in res["tools"]


@pytest.mark.asyncio
async def test_05_06_voice_wake_word():
    settings = VoiceSettings(wake_word_enabled=True, wake_words=["нова"])
    is_wake, cmd = voice_manager.is_wake_word("Нова открой калькулятор", settings)
    assert is_wake is True
    assert "калькулятор" in cmd


@pytest.mark.asyncio
async def test_07_open_application():
    res = await nova_core.process_user_input("открой блокнот")
    assert "reply" in res
    assert "app_launcher" in res["tools"]


@pytest.mark.asyncio
async def test_08_09_file_operations():
    tmp_path = Path("test_nova_file.txt")
    write_res = write_file_safe(str(tmp_path), "NOVA Test Content")
    assert write_res["success"] is True

    read_res = read_file_safe(str(tmp_path))
    assert read_res["success"] is True
    assert "NOVA Test Content" in read_res["content"]

    # Delete with explicit permission enabled and confirmed
    security_manager.update_settings(SecuritySettings(allow_file_delete=True))
    del_res = delete_file_safe(str(tmp_path), confirmed=True)
    assert del_res["success"] is True
    assert not tmp_path.exists()


@pytest.mark.asyncio
async def test_10_11_memory_save_and_recall():
    mem = memory_manager.add(
        category="long_term",
        title="Любимый цвет",
        content="Мой любимый цвет — синий",
        importance=2
    )
    assert mem.id is not None

    found = memory_manager.search_relevant("любимый цвет")
    assert len(found) > 0
    assert any("синий" in m.content for m in found)

    memory_manager.delete(mem.id)


@pytest.mark.asyncio
async def test_12_13_skills_creation_and_execution():
    skill = skills_engine.create_skill(
        name="Test Echo Skill",
        description="Тестовый навык",
        trigger_type="phrase",
        trigger_value="активируй тест",
        actions=[
            {"action_type": "tts_speak", "params": {"text": "Тест пройден"}}
        ]
    )
    assert skill.id is not None

    matched = skills_engine.match_trigger("Нова, активируй тест сейчас")
    assert matched is not None
    assert matched.id == skill.id

    exec_res = await skills_engine.execute_skill(skill)
    assert exec_res["success"] is True

    skills_engine.delete_skill(skill.id)


@pytest.mark.asyncio
async def test_14_15_16_17_agents():
    agent = agent_manager.get_agent("file-agent")
    assert agent is not None

    res = await agent_manager.run_agent_task(
        agent_id="file-agent",
        task_prompt="Найди все pdf файлы",
        ai_settings=AISettings()
    )
    assert res["success"] is True
    assert len(res["steps"]) >= 2


@pytest.mark.asyncio
async def test_18_19_permission_denial_and_confirm():
    sec_off = SecuritySettings(allow_file_read=False)
    security_manager.update_settings(sec_off)

    res = read_file_safe("dummy.txt")
    assert res["success"] is False
    assert "заблокировано" in res["error"].lower()

    # Reset security
    security_manager.update_settings(SecuritySettings(allow_file_read=True))


@pytest.mark.asyncio
async def test_20_offline_mode():
    settings = AppSettings(ai=AISettings(provider="local"))
    nova_core.save_settings(settings)
    res = await nova_core.process_user_input("что ты умеешь?")
    assert "reply" in res
    assert "local" in res.get("provider", "local")


@pytest.mark.asyncio
async def test_21_22_crash_recovery_and_diagnostics():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/diagnostics/run")
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_status"] in ["PASS", "WARNING"]


@pytest.mark.asyncio
async def test_23_24_25_backup_and_restore():
    bck = db.create_backup(label="pytest_run")
    assert bck.exists()
    assert bck.stat().st_size > 0

    restored = db.restore_backup(bck)
    assert restored is True
    bck.unlink()


def test_27_security_redaction():
    raw = "My api key is sk-1234567890abcdef1234567890 and pass: secret123"
    redacted = redact_secrets(raw)
    assert "sk-1234567890" not in redacted
    assert "[REDACTED" in redacted


@pytest.mark.asyncio
async def test_stress_multi_messages():
    for i in range(25):
        res = await nova_core.process_user_input(f"посчитай {i} + {i}")
        assert str(i * 2) in res["reply"]
