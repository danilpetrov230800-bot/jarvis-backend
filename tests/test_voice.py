from nova.tools.calculator import safe_calc
from nova.voice.pipeline import is_wake_word, strip_wake_word, EchoGuard, prepare_speech


def test_safe_calc():
    assert safe_calc("10+5*2") == "20"


def test_wake_words():
    assert is_wake_word("Нова")
    assert is_wake_word("NOVA, открой блокнот")
    assert not is_wake_word("новости сегодня")


def test_strip_wake():
    assert "открой" in strip_wake_word("Нова, открой блокнот").lower()


def test_echo_guard():
    guard = EchoGuard(cooldown_ms=50)
    guard.mark_spoken("Привет мир", duration_ms=10)
    assert guard.blocked("Привет мир")


def test_prepare_speech_strips_urls():
    text = prepare_speech("Смотри https://example.com сейчас")
    assert "http" not in text
