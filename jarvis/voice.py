from __future__ import annotations

import hashlib
import io
import logging
import re
import subprocess
import sys
from pathlib import Path

import edge_tts

from jarvis.config import DATA_DIR

DEFAULT_VOICE = "ru-RU-DmitryNeural"
MAX_TTS_CHARS = 420
CACHE = DATA_DIR / "tts_cache"

log = logging.getLogger(__name__)


def prepare_speech_text(text: str) -> str:
    cleaned = re.sub(r"[#*_`>~]+", "", text)
    cleaned = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", cleaned)
    cleaned = re.sub(r"https?://\S+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:MAX_TTS_CHARS]


def speech_preview(text: str) -> str:
    speak = prepare_speech_text(text)
    parts = re.split(r"(?<=[.!?…])\s+", speak)
    preview = " ".join(parts[:2]).strip()
    return preview[:280] or speak[:280] or "Готово."


def _cache_key(text: str, voice: str, rate: str) -> Path:
    digest = hashlib.sha256(f"{voice}|{rate}|{text}".encode("utf-8")).hexdigest()[:32]
    return CACHE / f"{digest}.bin"


def _read_cache(path: Path) -> bytes | None:
    if path.exists() and path.stat().st_size > 32:
        return path.read_bytes()
    return None


def _write_cache(path: Path, data: bytes) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    _prune_cache()


def _prune_cache(limit: int = 80) -> None:
    files = sorted(CACHE.glob("*.bin"), key=lambda item: item.stat().st_mtime)
    extra = len(files) - limit
    for item in files[: max(0, extra)]:
        try:
            item.unlink()
        except OSError:
            pass


def _sapi_wav(text: str) -> bytes:
    CACHE.mkdir(parents=True, exist_ok=True)
    wav = CACHE / "sapi-last.wav"
    escaped = text.replace("'", "''")
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$s.Rate = 2; "
        f"$s.SetOutputToWaveFile('{wav.as_posix()}'); "
        f"$s.Speak('{escaped}'); "
        "$s.Dispose()"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", script], check=False, capture_output=True, timeout=20)
    if wav.exists():
        return wav.read_bytes()
    return b""


async def synthesize(text: str, voice: str = DEFAULT_VOICE, rate: str = "+12%") -> tuple[bytes, str]:
    speak = prepare_speech_text(text) or "Готово."
    path = _cache_key(speak, voice or DEFAULT_VOICE, rate)
    cached = _read_cache(path)
    if cached:
        mime = "audio/wav" if cached[:4] == b"RIFF" else "audio/mpeg"
        return cached, mime

    try:
        communicate = edge_tts.Communicate(speak, voice=voice or DEFAULT_VOICE, rate=rate)
        buffer = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buffer.write(chunk["data"])
        data = buffer.getvalue()
        if data:
            from jarvis.recovery import mark_ok

            mark_ok("tts")
            _write_cache(path, data)
            return data, "audio/mpeg"
    except Exception:
        from jarvis.recovery import mark_fail

        mark_fail("tts")
        log.exception("edge-tts failed, trying local voice")

    if sys.platform == "win32":
        wav = _sapi_wav(speak)
        if wav:
            _write_cache(path, wav)
            return wav, "audio/wav"
    return b"", "audio/mpeg"


async def list_russian_voices() -> list[dict[str, str]]:
    try:
        voices = await edge_tts.list_voices()
    except Exception:
        voices = []
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
