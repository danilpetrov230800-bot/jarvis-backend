from __future__ import annotations

import io
import re

import edge_tts

DEFAULT_VOICE = "ru-RU-DmitryNeural"
MAX_TTS_CHARS = 1800


def prepare_speech_text(text: str) -> str:
    cleaned = re.sub(r"[#*_`>~]+", "", text)
    cleaned = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", cleaned)
    cleaned = re.sub(r"https?://\S+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:MAX_TTS_CHARS]


async def synthesize(text: str, voice: str = DEFAULT_VOICE, rate: str = "+8%") -> bytes:
    speak = prepare_speech_text(text)
    if not speak:
        speak = "Готово."
    communicate = edge_tts.Communicate(speak, voice=voice or DEFAULT_VOICE, rate=rate)
    buffer = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buffer.write(chunk["data"])
    return buffer.getvalue()


async def list_russian_voices() -> list[dict[str, str]]:
    voices = await edge_tts.list_voices()
    result = []
    for voice in voices:
        locale = voice.get("Locale", "")
        if locale.startswith("ru"):
            result.append(
                {
                    "id": voice.get("ShortName", ""),
                    "name": voice.get("FriendlyName", ""),
                    "gender": voice.get("Gender", ""),
                    "locale": locale,
                }
            )
    if not result:
        result = [
            {"id": "ru-RU-DmitryNeural", "name": "Dmitry", "gender": "Male", "locale": "ru-RU"},
            {"id": "ru-RU-SvetlanaNeural", "name": "Svetlana", "gender": "Female", "locale": "ru-RU"},
        ]
    return result
