from jarvis.desktop import handle_intent, help_text, safe_eval_math


def test_time_intent():
    result = handle_intent("который час")
    assert result is not None
    assert "Москва" in result.reply
    assert "datetime" in result.tools


def test_help_intent():
    result = handle_intent("что ты умеешь")
    assert result is not None
    assert "YouTube" in result.reply


def test_open_youtube(monkeypatch):
    opened = []
    monkeypatch.setattr("jarvis.desktop.open_url", lambda url: opened.append(url) or url)
    result = handle_intent("открой youtube")
    assert result is not None
    assert opened
    assert "youtube" in opened[0]


def test_open_github(monkeypatch):
    opened = []
    monkeypatch.setattr("jarvis.desktop.open_url", lambda url: opened.append(url) or url)
    result = handle_intent("открой GitHub")
    assert result is not None
    assert any("github" in url for url in opened)


def test_launch_notepad(monkeypatch):
    monkeypatch.setattr("jarvis.desktop.open_app", lambda name: "notepad.exe")
    result = handle_intent("запусти блокнот")
    assert result is not None
    assert "блокнот" in result.reply.lower() or "Запускаю" in result.reply


def test_math():
    assert safe_eval_math("24*7") == "168"
    result = handle_intent("посчитай 10+5")
    assert result is not None
    assert "15" in result.reply


def test_note(tmp_path, monkeypatch):
    monkeypatch.setattr("jarvis.desktop.NOTES_PATH", tmp_path / "notes.txt")
    monkeypatch.setattr("jarvis.desktop.DATA_DIR", tmp_path)
    result = handle_intent("запиши: купить молоко")
    assert result is not None
    assert "Записала" in result.reply
    assert "молоко" in (tmp_path / "notes.txt").read_text(encoding="utf-8")


def test_unknown_smalltalk_is_none():
    assert handle_intent("расскажи анекдот") is None


def test_help_text_lists_commands():
    text = help_text()
    assert "калькулятор" in text
    assert "скриншот" in text


def test_lock_without_computer_word(monkeypatch):
    monkeypatch.setattr("jarvis.desktop.lock_workstation", lambda: "locked")
    result = handle_intent("заблокируй")
    assert result is not None
    assert "lock" in result.tools


def test_clipboard_copy(monkeypatch):
    captured = []
    monkeypatch.setattr("jarvis.desktop.set_clipboard", lambda text: captured.append(text) or "ok")
    result = handle_intent("скопируй: купить хлеб")
    assert result is not None
    assert captured == ["купить хлеб"]


def test_timer_schedules_notify(monkeypatch):
    scheduled = []
    monkeypatch.setattr("jarvis.desktop.threading.Timer", lambda seconds, fn: type("T", (), {"start": lambda self: scheduled.append(seconds) or fn()})())
    monkeypatch.setattr("jarvis.desktop._notify_timer", lambda label: None)
    result = handle_intent("таймер 5 секунд")
    assert result is not None
    assert "timer" in result.tools
    assert scheduled == [5]
