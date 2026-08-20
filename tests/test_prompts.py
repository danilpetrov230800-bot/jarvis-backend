from jarvis.prompts import search_needed, system_prompt


def test_system_prompt_is_russian_and_literate():
    text = system_prompt("Данила", "JARVIS")
    assert "грамотным литературным русским" in text
    assert "web_search" in text
    assert "Данила" in text
    assert "канцелярита" in text
    assert "взлом" in text


def test_search_needed_detects_russian_intents():
    assert search_needed("Погугли курс доллара")
    assert search_needed("Что такое квантовый компьютер")
    assert search_needed("Найди новости про ИИ")
    assert not search_needed("просто поговорим о кино")
