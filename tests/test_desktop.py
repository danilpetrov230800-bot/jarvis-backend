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
