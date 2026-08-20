from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from threading import Lock
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"
OLLAMA_URL = os.getenv("NOVA_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
DEFAULT_MODEL = os.getenv("NOVA_MODEL", "qwen2.5:7b")
MAX_OUTPUT = 40_000
PROPOSAL_TTL = 15 * 60

SYSTEM_PROMPT = """Ты Nova — локальный персональный AI-ассистент.
Отвечай на языке пользователя, уверенно, естественно и по делу.
Уважай приватность: данные остаются на устройстве, не утверждай, что сделал то,
чего не делал. Когда для задачи нужна команда терминала, предложи ровно одну
команду в тегах <nova_command>команда</nova_command> и кратко объясни её.
Команда будет показана пользователю и запущена только после подтверждения.
Не добавляй эти теги, если команда не нужна."""


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20_000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=30)
    model: str = Field(default=DEFAULT_MODEL, min_length=1, max_length=120)


class PrepareCommandRequest(BaseModel):
    command: str = Field(min_length=1, max_length=8_000)
    cwd: str | None = Field(default=None, max_length=2_000)


class ExecuteCommandRequest(BaseModel):
    proposal_id: str
    confirmed: bool = False
    timeout: int = Field(default=60, ge=1, le=300)


class CommandProposal(BaseModel):
    proposal_id: str
    command: str
    cwd: str
    risk: Literal["normal", "elevated", "critical"]
    reason: str
    created_at: float


app = FastAPI(title="Nova", version="1.0.0", docs_url="/api/docs")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_proposals: dict[str, CommandProposal] = {}
_proposal_lock = Lock()


def classify_command(command: str) -> tuple[str, str]:
    normalized = command.lower().strip()
    critical_patterns = (
        r"(^|\s)(rm\s+(-\w*[rf]\w*\s+)?/(\s|$)|mkfs(\.|\s)|dd\s+.*of=/dev/)",
        r"(^|\s)(shutdown|reboot|poweroff|halt)(\s|$)",
        r"(^|\s)(git\s+push\s+.*--force|git\s+reset\s+--hard)(\s|$)",
        r"(^|\s)(curl|wget).*\|\s*(sh|bash)(\s|$)",
    )
    elevated_patterns = (
        r"(^|\s)(sudo|su)(\s|$)",
        r"(^|\s)(rm|mv|chmod|chown|kill|pkill)(\s|$)",
        r"(^|\s)(pip|npm|pnpm|yarn|apt|dnf|brew)\s+(install|remove|uninstall)",
        r"[>|]\s*[^|]",
    )
    if any(re.search(pattern, normalized) for pattern in critical_patterns):
        return "critical", "Команда может необратимо изменить систему или данные."
    if any(re.search(pattern, normalized) for pattern in elevated_patterns):
        return "elevated", "Команда изменяет файлы, процессы или пакеты."
    return "normal", "Команда будет выполнена локально в указанной папке."


def prepare_command(command: str, cwd: str | None = None) -> CommandProposal:
    resolved_cwd = Path(cwd or os.getcwd()).expanduser().resolve()
    if not resolved_cwd.is_dir():
        raise HTTPException(status_code=400, detail="Рабочая папка не существует.")

    risk, reason = classify_command(command)
    proposal = CommandProposal(
        proposal_id=secrets.token_urlsafe(24),
        command=command.strip(),
        cwd=str(resolved_cwd),
        risk=risk,
        reason=reason,
        created_at=time.time(),
    )
    with _proposal_lock:
        now = time.time()
        expired = [
            key
            for key, value in _proposals.items()
            if now - value.created_at > PROPOSAL_TTL
        ]
        for key in expired:
            _proposals.pop(key, None)
        _proposals[proposal.proposal_id] = proposal
    return proposal


def parse_assistant_reply(text: str) -> tuple[str, str | None]:
    match = re.search(r"<nova_command>(.*?)</nova_command>", text, flags=re.DOTALL)
    if not match:
        return text.strip(), None
    command = match.group(1).strip()
    clean = (text[: match.start()] + text[match.end() :]).strip()
    return clean, command or None


def ollama_chat(request: ChatRequest) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(message.model_dump() for message in request.history[-20:])
    messages.append({"role": "user", "content": request.message})
    payload = json.dumps(
        {"model": request.model, "messages": messages, "stream": False}
    ).encode()
    http_request = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(http_request, timeout=180) as response:
            data = json.loads(response.read())
    except urllib.error.URLError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Ollama недоступна. Запустите `ollama serve` и установите модель "
                f"`ollama pull {request.model}`."
            ),
        ) from exc
    try:
        return data["message"]["content"]
    except (KeyError, TypeError) as exc:
        raise HTTPException(status_code=502, detail="Некорректный ответ Ollama.") from exc


@app.get("/")
def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/status")
def status() -> dict[str, object]:
    models: list[str] = []
    online = False
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=2) as response:
            payload = json.loads(response.read())
            models = [item["name"] for item in payload.get("models", [])]
            online = True
    except (urllib.error.URLError, json.JSONDecodeError, KeyError):
        pass
    return {
        "name": "Nova",
        "online": online,
        "provider": "Ollama",
        "default_model": DEFAULT_MODEL,
        "models": models,
    }


@app.post("/api/chat")
def chat(request: ChatRequest) -> dict[str, object]:
    raw_reply = ollama_chat(request)
    reply, command = parse_assistant_reply(raw_reply)
    proposal = prepare_command(command) if command else None
    return {"reply": reply, "command": proposal.model_dump() if proposal else None}


@app.post("/api/commands/prepare")
def command_prepare(request: PrepareCommandRequest) -> CommandProposal:
    return prepare_command(request.command, request.cwd)


@app.post("/api/commands/execute")
def command_execute(request: ExecuteCommandRequest) -> dict[str, object]:
    if not request.confirmed:
        raise HTTPException(status_code=400, detail="Требуется явное подтверждение.")
    with _proposal_lock:
        proposal = _proposals.pop(request.proposal_id, None)
    if proposal is None or time.time() - proposal.created_at > PROPOSAL_TTL:
        raise HTTPException(status_code=404, detail="Предложение устарело или не найдено.")

    started = time.monotonic()
    try:
        result = subprocess.run(
            proposal.command,
            cwd=proposal.cwd,
            shell=True,
            executable=os.getenv("SHELL", "/bin/bash"),
            capture_output=True,
            text=True,
            timeout=request.timeout,
            env=os.environ.copy(),
        )
        output = (result.stdout + result.stderr).strip()
        truncated = len(output) > MAX_OUTPUT
        return {
            "command": proposal.command,
            "exit_code": result.returncode,
            "output": output[:MAX_OUTPUT],
            "truncated": truncated,
            "duration_ms": round((time.monotonic() - started) * 1000),
        }
    except subprocess.TimeoutExpired as exc:
        partial = ((exc.stdout or "") + (exc.stderr or ""))
        raise HTTPException(
            status_code=408,
            detail=f"Команда остановлена по тайм-ауту.\n{partial[:MAX_OUTPUT]}",
        ) from exc
