from jarvis.voice import _cache_key, prepare_speech_text, speech_preview


def test_speech_preview_takes_two_sentences():
    text = "Первое предложение. Второе предложение. Третье уже лишнее."
    preview = speech_preview(text)
    assert "Первое" in preview
    assert "Второе" in preview
    assert "Третье" not in preview


def test_prepare_speech_truncates():
    long = "слово " * 400
    cleaned = prepare_speech_text(long)
    assert len(cleaned) <= 420


def test_cache_key_is_stable(tmp_path, monkeypatch):
    monkeypatch.setattr("jarvis.voice.CACHE", tmp_path)
    first = _cache_key("привет", "ru-RU-DmitryNeural", "+12%")
    second = _cache_key("привет", "ru-RU-DmitryNeural", "+12%")
    other = _cache_key("пока", "ru-RU-DmitryNeural", "+12%")
    assert first == second
    assert first != other
