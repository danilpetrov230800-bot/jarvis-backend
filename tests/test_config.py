from jarvis.config import Settings, infer_provider, inferred_base_url, inferred_model, merge_settings, public_settings


def test_openrouter_inference():
    settings = Settings(api_key="sk-or-1234567890abcdef", provider="auto")
    settings.base_url = ""
    # without env, openai is default unless base_url/provider hint
    settings = Settings(provider="openrouter", api_key="sk-or-1234567890abcdef")
    assert infer_provider(settings) == "openrouter"
    assert "openrouter.ai" in inferred_base_url(settings)
    assert inferred_model(settings)


def test_merge_keeps_unknown_out():
    current = Settings(user_name="Данила", api_key="secret")
    updated = merge_settings(current, {"user_name": "Сэр", "drop_me": 1, "api_key": "newkey"})
    assert updated.user_name == "Сэр"
    assert updated.api_key == "newkey"
    assert not hasattr(updated, "drop_me") or "drop_me" not in updated.model_dump()


def test_public_settings_masks_key():
    data = public_settings(Settings(api_key="sk-abcdefghijklmnop", provider="openai"))
    assert data["has_api_key"] is True
    assert "sk-a" in data["api_key_preview"]
    assert "mnop" in data["api_key_preview"]
    assert "cdef" not in data["api_key_preview"]
