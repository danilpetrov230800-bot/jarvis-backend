"""Voice pipeline for NOVA."""

from __future__ import annotations

import asyncio
import platform
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Awaitable

from nova.core.config import get_settings
from nova.core.logging import get_logger
from nova.core.state import NovaStatus, get_state

logger = get_logger("nova.voice")

WAKE_WORDS = ("нова", "nova")


class VoiceState(str, Enum):
    IDLE = "idle"
    LISTENING_WAKE = "listening_wake"
    LISTENING_COMMAND = "listening_command"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    COOLDOWN = "cooldown"


@dataclass
class VoiceConfig:
    enabled: bool = True
    wake_word_enabled: bool = True
    sensitivity: float = 0.5
    microphone: str = "default"
    voice: str = "default"
    tts_rate: int = 180
    tts_volume: float = 1.0


class VoicePipeline:
    def __init__(self):
        self.settings = get_settings()
        self.config = VoiceConfig(
            wake_word_enabled=self.settings.wake_word_enabled,
            sensitivity=self.settings.wake_word_sensitivity,
            tts_rate=self.settings.tts_rate,
            tts_volume=self.settings.tts_volume,
        )
        self.state = VoiceState.IDLE
        self._running = False
        self._thread: threading.Thread | None = None
        self._command_callback: Callable[[str], Awaitable[str]] | None = None
        self._last_activation = 0.0
        self._cooldown_sec = 2.0
        self._echo_protection_until = 0.0
        self._microphone_available = True
        self._tts_available = True
        self._stt_engine = None
        self._tts_engine = None

    def set_command_handler(self, handler: Callable[[str], Awaitable[str]]) -> None:
        self._command_callback = handler

    async def initialize(self) -> dict:
        result = {"microphone": "UNKNOWN", "tts": "UNKNOWN", "stt": "UNKNOWN"}
        try:
            import speech_recognition as sr
            self._stt_engine = sr.Recognizer()
            with sr.Microphone() as source:
                self._stt_engine.adjust_for_ambient_noise(source, duration=0.5)
            result["microphone"] = "PASS"
            self._microphone_available = True
        except Exception as e:
            logger.warning("Microphone unavailable: %s", e)
            result["microphone"] = "FAIL"
            self._microphone_available = False

        try:
            if platform.system() == "Windows":
                import pyttsx3
                self._tts_engine = pyttsx3.init()
                self._tts_engine.setProperty("rate", self.config.tts_rate)
            result["tts"] = "PASS" if self._tts_engine else "WARNING"
            self._tts_available = bool(self._tts_engine)
        except Exception as e:
            logger.warning("TTS unavailable: %s", e)
            result["tts"] = "FAIL"
            self._tts_available = False

        result["stt"] = "PASS" if self._microphone_available else "FAIL"
        return result

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        state = get_state()
        state.wake_word_active = self.config.wake_word_enabled
        logger.info("Voice pipeline started")

    def stop(self) -> None:
        self._running = False
        state = get_state()
        state.wake_word_active = False
        logger.info("Voice pipeline stopped")

    def _listen_loop(self) -> None:
        while self._running:
            try:
                if not self._microphone_available:
                    time.sleep(1)
                    continue

                if self.config.wake_word_enabled:
                    self.state = VoiceState.LISTENING_WAKE
                    text = self._listen_once(timeout=3, phrase_limit=3)
                    if text and self._is_wake_word(text):
                        if time.time() < self._echo_protection_until:
                            continue
                        self._on_wake_word_detected()
                else:
                    time.sleep(0.5)
            except Exception as e:
                logger.error("Voice loop error: %s", e)
                time.sleep(1)

    def _is_wake_word(self, text: str) -> bool:
        text_lower = text.lower().strip()
        return any(w in text_lower for w in WAKE_WORDS)

    def _on_wake_word_detected(self) -> None:
        logger.info("Wake word detected")
        self._last_activation = time.time()
        self.state = VoiceState.LISTENING_COMMAND
        asyncio.run_coroutine_threadsafe(self._handle_wake_activation(), asyncio.get_event_loop())

    async def _handle_wake_activation(self) -> None:
        state = get_state()
        await state.set_status(NovaStatus.LISTENING)
        await self.speak("Слушаю")

        command = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self._listen_once(timeout=8, phrase_limit=15)
        )

        if not command:
            await self.speak("Не расслышала команду")
            await state.set_status(NovaStatus.IDLE)
            return

        await state.set_status(NovaStatus.PROCESSING)
        self._echo_protection_until = time.time() + self._cooldown_sec + 3

        if self._command_callback:
            response = await self._command_callback(command)
        else:
            response = "Команда получена"

        await state.set_status(NovaStatus.SPEAKING)
        await self.speak(response)
        await state.set_status(NovaStatus.IDLE)
        self.state = VoiceState.IDLE

    def _listen_once(self, timeout: float = 5, phrase_limit: float = 10) -> str | None:
        if not self._stt_engine:
            return None
        try:
            import speech_recognition as sr
            with sr.Microphone() as source:
                audio = self._stt_engine.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
            text = self._stt_engine.recognize_google(audio, language="ru-RU")
            return text
        except Exception:
            return None

    async def speak(self, text: str) -> bool:
        if not self._tts_available or not self._tts_engine:
            logger.info("TTS fallback (text): %s", text[:100])
            return False

        self.state = VoiceState.SPEAKING
        self._echo_protection_until = time.time() + len(text) * 0.05 + self._cooldown_sec

        def _do_speak():
            self._tts_engine.say(text)
            self._tts_engine.runAndWait()

        await asyncio.get_event_loop().run_in_executor(None, _do_speak)
        self.state = VoiceState.IDLE
        return True

    async def test_microphone(self) -> dict:
        text = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self._listen_once(timeout=5, phrase_limit=5)
        )
        return {
            "status": "PASS" if text else "FAIL",
            "heard": text or "Ничего не распознано",
        }

    async def test_tts(self) -> dict:
        ok = await self.speak("Привет! Я NOVA. Голос работает.")
        return {"status": "PASS" if ok else "WARNING", "message": "TTS test completed"}

    def get_status(self) -> dict:
        return {
            "state": self.state.value,
            "running": self._running,
            "microphone_available": self._microphone_available,
            "tts_available": self._tts_available,
            "wake_word_enabled": self.config.wake_word_enabled,
            "config": {
                "sensitivity": self.config.sensitivity,
                "microphone": self.config.microphone,
                "voice": self.config.voice,
                "tts_rate": self.config.tts_rate,
                "tts_volume": self.config.tts_volume,
            },
        }


_pipeline: VoicePipeline | None = None


def get_voice_pipeline() -> VoicePipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = VoicePipeline()
    return _pipeline
