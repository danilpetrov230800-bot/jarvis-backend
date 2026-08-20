"""
NOVA Voice Subsystem
- Speech-to-Text (Web Speech API integration + local audio processing)
- Text-to-Speech (Edge-TTS + SAPI + Web Speech audio fallback)
- Wake Word Detection ("Нова", "NOVA") with anti-echo and self-trigger prevention
- Audio Caching and Diagnostics
"""
from __future__ import annotations

import hashlib
import io
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import edge_tts

from nova.config import TTS_CACHE_DIR, VoiceSettings

log = logging.getLogger("nova.voice")

DEFAULT_VOICE = "ru-RU-DmitryNeural"
MAX_TTS_CHARS = 1000

# Russian voices database
VOICES_CATALOG = [
    {"id": "ru-RU-DmitryNeural", "name": "Дмитрий (Естественный, Мужской)", "gender": "Male", "locale": "ru-RU"},
    {"id": "ru-RU-SvetlanaNeural", "name": "Светлана (Естественный, Женский)", "gender": "Female", "locale": "ru-RU"},
    {"id": "ru-RU-Wavenet-D", "name": "Локальный системный SAPI / Web", "gender": "Neutral", "locale": "ru-RU"}
]


def clean_text_for_speech(text: str) -> str:
    cleaned = re.sub(r"[#*_`>~]+", "", text)
    cleaned = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", cleaned)
    cleaned = re.sub(r"https?://\S+", "", cleaned)
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:MAX_TTS_CHARS]


def _get_cache_path(text: str, voice: str, rate: str) -> Path:
    key = hashlib.sha256(f"{voice}|{rate}|{text}".encode("utf-8")).hexdigest()[:32]
    return TTS_CACHE_DIR / f"{key}.bin"


class VoiceManager:
    def __init__(self):
        self._last_spoken_time = 0.0
        self._last_spoken_text = ""

    def is_wake_word(self, phrase: str, settings: VoiceSettings) -> tuple[bool, str]:
        """
        Detect wake words ('нова', 'nova') and strip them to extract the actual command.
        Includes anti-echo prevention if the microphone hears NOVA's own recent speech.
        """
        if not settings.wake_word_enabled:
            return False, phrase

        # Anti-echo protection
        if settings.prevent_echo and (time.time() - self._last_spoken_time < 2.0):
            # Microphone might be picking up residual speaker sound
            if self._last_spoken_text and phrase.lower() in self._last_spoken_text.lower():
                log.info("Ignored wake word due to echo protection")
                return False, ""

        lowered = phrase.strip().lower()
        for w in settings.wake_words:
            w_low = w.lower()
            if lowered.startswith(w_low):
                command = lowered[len(w_low):].strip(" ,.!?")
                return True, command
            elif f" {w_low}" in lowered:
                parts = lowered.split(w_low, 1)
                return True, parts[1].strip(" ,.!?")

        return False, phrase

    async def synthesize_speech(
        self,
        text: str,
        voice: str = DEFAULT_VOICE,
        rate: str = "+10%"
    ) -> tuple[bytes, str]:
        """
        Synthesize speech from text. Returns (audio_bytes, mime_type).
        Tries Edge-TTS, falls back to Windows SAPI.
        """
        clean = clean_text_for_speech(text)
        if not clean:
            clean = "Готово."

        self._last_spoken_text = clean
        self._last_spoken_time = time.time()

        cache_file = _get_cache_path(clean, voice, rate)
        if cache_file.exists() and cache_file.stat().st_size > 32:
            data = cache_file.read_bytes()
            mime = "audio/wav" if data[:4] == b"RIFF" else "audio/mpeg"
            return data, mime

        # 1. Edge-TTS synthesis
        try:
            communicate = edge_tts.Communicate(clean, voice=voice or DEFAULT_VOICE, rate=rate)
            buf = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    buf.write(chunk["data"])
            audio_bytes = buf.getvalue()
            if audio_bytes:
                cache_file.write_bytes(audio_bytes)
                return audio_bytes, "audio/mpeg"
        except Exception as e:
            log.warning(f"Edge-TTS synthesis error: {e}. Trying SAPI fallback.")

        # 2. Windows SAPI fallback
        if sys.platform == "win32":
            sapi_data = self._synthesize_sapi(clean)
            if sapi_data:
                cache_file.write_bytes(sapi_data)
                return sapi_data, "audio/wav"

        return b"", "audio/mpeg"

    def _synthesize_sapi(self, text: str) -> bytes:
        wav_out = TTS_CACHE_DIR / "sapi_temp.wav"
        escaped = text.replace("'", "''")
        ps = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.SetOutputToWaveFile('{wav_out.as_posix()}'); "
            f"$s.Speak('{escaped}'); "
            "$s.Dispose()"
        )
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=False, timeout=15)
            if wav_out.exists():
                return wav_out.read_bytes()
        except Exception:
            pass
        return b""

    def get_available_voices(self) -> list[dict[str, str]]:
        return VOICES_CATALOG


voice_manager = VoiceManager()
