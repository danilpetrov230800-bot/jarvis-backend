from __future__ import annotations

APP_NAME = "NOVA"
APP_TITLE = "NOVA — Neural Operational & Virtual Assistant"
APP_VERSION = "1.0.0"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
WAKE_WORDS = ("нова", "nova", "нёва")
MAX_AGENT_STEPS = 12
AGENT_TIMEOUT_SEC = 120
AGENT_RETRY_LIMIT = 2
TOOL_TIMEOUT_SEC = 30
TTS_TIMEOUT_SEC = 25
STT_TIMEOUT_SEC = 20
WAKE_LISTEN_TIMEOUT_SEC = 8
ECHO_GUARD_MS = 900
MAX_TTS_CHARS = 420
MAX_HISTORY = 40
MAX_LOG_BYTES = 8_000_000
CONFIRMATION_TTL_SEC = 120

DANGEROUS_PERMISSIONS = frozenset(
    {
        "DELETE_FILES",
        "SYSTEM_SETTINGS",
        "SCREEN_CONTROL",
        "RUN_APPLICATIONS",
        "NETWORK",
        "RESEARCH",
    }
)

DEFAULT_PERMISSIONS: dict[str, bool] = {
    "READ_FILES": True,
    "WRITE_FILES": True,
    "DELETE_FILES": False,
    "RUN_APPLICATIONS": True,
    "SYSTEM_SETTINGS": True,
    "NETWORK": True,
    "SCREEN_CONTROL": True,
    "MICROPHONE": True,
    "CAMERA": False,
    "CLIPBOARD": True,
    "RESEARCH": False,
}

MEMORY_KINDS = (
    "short_term",
    "long_term",
    "preference",
    "episodic",
    "semantic",
    "skill",
)

AGENT_ROLES = (
    "research",
    "coding",
    "file",
    "system",
    "creative",
    "testing",
    "automation",
    "general",
)
