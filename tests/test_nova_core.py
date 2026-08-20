from jarvis.files_agent import _safe, find_files
from jarvis.logs import redact
from jarvis.memory_long import add_memory, list_memories, recall_text
from jarvis.permissions import DEFAULTS, allowed, save
from jarvis.skills import create_skill, list_skills, parse_actions
from jarvis.store import migrate


def test_redact_secrets():
    assert "[redacted]" in redact("key=gsk_abcdefghijklmnop")
    assert "hello" in redact("hello")


def test_memory_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr("jarvis.store.DATA_DIR", tmp_path)
    migrate()
    add_memory("любимый чай — улун")
    items = list_memories("чай")
    assert items
    assert "улун" in recall_text("чай")


def test_skill_parse_and_store(tmp_path, monkeypatch):
    monkeypatch.setattr("jarvis.store.DATA_DIR", tmp_path)
    migrate()
    actions = parse_actions("открой chrome и калькулятор")
    assert actions
    skill = create_skill("work", "режим работы", action_text="открой chrome")
    assert skill["trigger_text"] == "режим работы"
    assert list_skills()


def test_permissions_default_delete_off(tmp_path, monkeypatch):
    monkeypatch.setattr("jarvis.permissions.PATH", tmp_path / "permissions.json")
    monkeypatch.setattr("jarvis.permissions.DATA_DIR", tmp_path)
    assert DEFAULTS["DELETE_FILES"] is False
    save({"RESEARCH": True})
    assert allowed("RESEARCH") is True


def test_file_search_and_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr("jarvis.files_agent.user_roots", lambda: [tmp_path])
    (tmp_path / "report.pdf").write_bytes(b"pdf")
    items = find_files("pdf")
    assert any(row["name"] == "report.pdf" for row in items)
    try:
        _safe(tmp_path.parent / "outside.txt")
        raised = False
    except PermissionError:
        raised = True
    assert raised
