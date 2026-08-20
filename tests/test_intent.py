from nova.intent import IntentRouter, help_text


def test_help_text_not_empty():
    assert "NOVA" in help_text()
