"""Абстракция провайдера языковой модели для Nova.

Порядок выбора (авто): OpenAI (если есть ключ) → локальный Ollama →
демо-режим. Благодаря локальному Ollama пользователю НЕ нужно вводить
никакие API-ключи.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from typing import Iterator, List

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
LOCAL_MODEL = os.getenv("NOVA_LOCAL_MODEL", "qwen2.5:3b")
OPENAI_MODEL = os.getenv("NOVA_MODEL", "gpt-5")
MAX_HISTORY = 20

SYSTEM_PROMPT = (
    "Ты — Nova, персональный ИИ-ассистент в духе J.A.R.V.I.S. Стиль: уверенный, "
    "тёплый, с лёгким юмором, но по делу. Отвечай прямо и честно, без лишних "
    "оговорок и морализаторства. Помогай с чем угодно: код, идеи, планы, расчёты, "
    "быт. По умолчанию отвечай на русском, кратко и структурно. Обращайся на «ты». "
    "Если тебе дали данные инструментов — опирайся на них и не выдумывай факты."
)


def _ollama_url(path: str) -> str:
    base = OLLAMA_HOST if OLLAMA_HOST.startswith("http") else f"http://{OLLAMA_HOST}"
    return base.rstrip("/") + path


def ollama_ready() -> bool:
    try:
        req = urllib.request.Request(_ollama_url("/api/tags"))
        with urllib.request.urlopen(req, timeout=2) as r:
            tags = json.loads(r.read().decode("utf-8", "replace"))
        names = [m.get("name", "") for m in tags.get("models", [])]
        return any(n == LOCAL_MODEL or n.split(":")[0] == LOCAL_MODEL.split(":")[0] for n in names)
    except Exception:
        return False


def current_provider() -> str:
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if ollama_ready():
        return "ollama"
    return "demo"


def provider_info() -> dict:
    p = current_provider()
    model = {"openai": OPENAI_MODEL, "ollama": LOCAL_MODEL, "demo": "—"}[p]
    label = {"openai": "OpenAI", "ollama": "локальный ИИ", "demo": "демо-режим"}[p]
    return {"provider": p, "model": model, "label": label}


def _system(tool_context: str) -> str:
    if tool_context:
        return (
            SYSTEM_PROMPT
            + "\n\nДанные инструментов (актуальные, используй их):\n"
            + tool_context
        )
    return SYSTEM_PROMPT


# --------------------------------------------------------------------------
# Провайдеры
# --------------------------------------------------------------------------
def _stream_ollama(messages: List[dict], tool_context: str) -> Iterator[str]:
    body = json.dumps({
        "model": LOCAL_MODEL,
        "messages": [{"role": "system", "content": _system(tool_context)}] + messages[-MAX_HISTORY:],
        "stream": True,
        "options": {"temperature": 0.6, "num_predict": 320},
    }).encode()
    req = urllib.request.Request(
        _ollama_url("/api/chat"), data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        for line in r:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            chunk = obj.get("message", {}).get("content", "")
            if chunk:
                yield chunk
            if obj.get("done"):
                break


def _stream_openai(messages: List[dict], tool_context: str) -> Iterator[str]:
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    convo = [{"role": m["role"], "content": m["content"]} for m in messages[-MAX_HISTORY:]]
    try:
        stream = client.responses.create(
            model=OPENAI_MODEL,
            instructions=_system(tool_context),
            input=convo,
            temperature=0.7,
            stream=True,
        )
        for event in stream:
            if getattr(event, "type", "") == "response.output_text.delta":
                delta = getattr(event, "delta", "") or ""
                if delta:
                    yield delta
        return
    except TypeError:
        pass
    resp = client.responses.create(
        model=OPENAI_MODEL, instructions=_system(tool_context), input=convo, temperature=0.7
    )
    yield getattr(resp, "output_text", "") or ""


def _stream_demo(messages: List[dict], tool_context: str, direct_text: str) -> Iterator[str]:
    if direct_text:
        text = direct_text
    else:
        last = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        text = (
            f"На связи, Nova. Записала: «{last}». Сейчас нет ни ключа OpenAI, ни "
            "локальной модели, поэтому отвечаю коротко. Инструменты (погода, поиск, "
            "курсы, время, маршруты, управление ПК) при этом работают."
        )
    for token in text.split(" "):
        yield token + " "
        time.sleep(0.015)


def stream_reply(messages: List[dict], tool_context: str = "", direct_text: str = "") -> Iterator[str]:
    provider = current_provider()
    if provider == "openai":
        yield from _stream_openai(messages, tool_context)
    elif provider == "ollama":
        yield from _stream_ollama(messages, tool_context)
    else:
        yield from _stream_demo(messages, tool_context, direct_text)
