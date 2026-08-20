from __future__ import annotations

import hashlib
import io
import logging
import re
import subprocess
import sys
import time
from pathlib import Path

from nova.constants import ECHO_GUARD_MS, MAX_TTS_CHARS, WAKE_WORDS
from nova.paths import tts_cache_dir

log = logging.getLogger("nova.voice")
DEFAULT_VOICE = "ru-RU-DmitryNeural"


def prepare_speech(text: str) -> str:
    cleaned = re.sub(r"[#*_`>~]+", "", text)
    cleaned = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", cleaned)
    cleaned = re.sub(r"https?://\S+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:MAX_TTS_CHARS]


def speech_preview(text: str) -> str:
    speak = prepare_speech(text)
    parts = re.split(r"(?<=[.!?…])\s+", speak)
    preview = " ".join(parts[:2]).strip()
    return preview[:280] or speak[:280] or "Готово."


class EchoGuard:
    def __init__(self, cooldown_ms: int = ECHO_GUARD_MS) -> None:
        self.cooldown_ms = cooldown_ms
        self._until = 0.0
        self._last_spoken = ""

    def mark_spoken(self, text: str, duration_ms: int = 1200) -> None:
        self._last_spoken = prepare_speech(text).lower()
        self._until = time.monotonic() + (duration_ms + self.cooldown_ms) / 1000

    def blocked(self, heard: str) -> bool:
        if time.monotonic() < self._until:
            return True
        heard_l = heard.lower().strip()
        spoken = self._last_spoken
        if spoken and heard_l and (heard_l in spoken or spoken in heard_l):
            return True
        return False


def is_wake_word(text: str, words: tuple[str, ...] | list[str] = WAKE_WORDS, sensitivity: float = 0.65) -> bool:
    cleaned = re.sub(r"[^\wа-яё]+", " ", text.lower(), flags=re.I).strip()
    tokens = cleaned.split()
    if not tokens:
        return False
    for word in words:
        word = word.lower()
        if word in tokens:
            return True
        if sensitivity < 0.5 and any(token.startswith(word[: max(3, len(word) - 1)]) for token in tokens):
            return True
    return False


def strip_wake_word(text: str, words: tuple[str, ...] | list[str] = WAKE_WORDS) -> str:
    result = text.strip()
    for word in words:
        result = re.sub(rf"^\s*{re.escape(word)}[,:\s]*", "", result, flags=re.I)
    return result.strip(" ,.-")


async def synthesize(text: str, voice: str = DEFAULT_VOICE, rate: str = "+10%") -> tuple[bytes, str]:
    speak = prepare_speech(text) or "Готово."
    cache = tts_cache_dir() / (hashlib.sha256(f"{voice}|{rate}|{speak}".encode()).hexdigest()[:32] + ".bin")
    if cache.exists() and cache.stat().st_size > 32:
        data = cache.read_bytes()
        mime = "audio/wav" if data[:4] == b"RIFF" else "audio/mpeg"
        return data, mime
    try:
        import edge_tts

        communicate = edge_tts.Communicate(speak, voice=voice or DEFAULT_VOICE, rate=rate)
        buffer = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buffer.write(chunk["data"])
        data = buffer.getvalue()
        if data:
            cache.write_bytes(data)
            return data, "audio/mpeg"
    except Exception:
        log.exception("edge-tts failed")
    if sys.platform == "win32":
        wav = _sapi_wav(speak, cache.parent / "sapi-last.wav")
        if wav:
            cache.write_bytes(wav)
            return wav, "audio/wav"
    return b"", "audio/mpeg"


def _sapi_wav(text: str, wav: Path) -> bytes:
    escaped = text.replace("'", "''")
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$s.Rate = 2; "
        f"$s.SetOutputToWaveFile('{wav.as_posix()}'); "
        f"$s.Speak('{escaped}'); "
        "$s.Dispose()"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, timeout=20)
    return wav.read_bytes() if wav.exists() else b""


async def list_voices() -> list[dict[str, str]]:
    try:
        import edge_tts

        voices = await edge_tts.list_voices()
    except Exception:
        voices = []
    result = []
    for voice in voices:
        locale = voice.get("Locale", "")
        if locale.startswith("ru") or locale.startswith("en"):
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
