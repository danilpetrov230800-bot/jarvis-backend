from jarvis.pc_control import handle_pc_intent


def test_volume_up_intent(monkeypatch):
    called = []
    monkeypatch.setattr("jarvis.pc_control.require", lambda permission: None)
    monkeypatch.setattr("jarvis.pc_control._key", lambda vk, times=1: called.append((vk, times)))
    result = handle_pc_intent("громче")
    assert result is not None
    assert "volume" in result.tools
    assert "громк" in result.reply.lower()
    assert called


def test_mute_and_play(monkeypatch):
    monkeypatch.setattr("jarvis.pc_control.require", lambda permission: None)
    monkeypatch.setattr("jarvis.pc_control._key", lambda *args, **kwargs: None)
    mute = handle_pc_intent("выключи звук")
    play = handle_pc_intent("пауза")
    assert mute is not None and "volume" in mute.tools
    assert play is not None and "media" in play.tools


def test_brightness_percent(monkeypatch):
    values = []
    monkeypatch.setattr("jarvis.pc_control.set_brightness", lambda percent: values.append(percent) or f"{percent}")
    result = handle_pc_intent("яркость 40")
    assert result is not None
    assert values == [40]


def test_unknown_is_none():
    assert handle_pc_intent("расскажи сказку") is None
