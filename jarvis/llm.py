from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from jarvis.config import Settings, infer_provider, inferred_base_url, inferred_model
from jarvis.prompts import search_needed, system_prompt
from jarvis.search import format_search_results, search_web, serialize_sources
from jarvis.tools import TOOL_SCHEMAS, ToolContext, execute_tool


class LLMError(RuntimeError):
    pass


def build_client(settings: Settings) -> AsyncOpenAI:
    provider = infer_provider(settings)
    api_key = settings.api_key or "ollama"
    if provider != "ollama" and not settings.api_key:
        raise LLMError(
            "Не задан API-ключ. Откройте настройки JARVIS и укажите ключ OpenRouter, Groq или OpenAI."
        )
    default_headers = {}
    if provider == "openrouter":
        default_headers = {
            "HTTP-Referer": "http://127.0.0.1:8080",
            "X-Title": "JARVIS",
        }
    return AsyncOpenAI(
        api_key=api_key,
        base_url=inferred_base_url(settings),
        default_headers=default_headers or None,
    )


def _message_text(message: Any) -> str:
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("text"):
                parts.append(item["text"])
            else:
                text = getattr(item, "text", None)
                if text:
                    parts.append(text)
        return "".join(parts)
    return str(content or "")


async def _complete(client: AsyncOpenAI, model: str, messages: list[dict[str, Any]], tools: bool) -> Any:
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0.6,
    }
    if tools:
        kwargs["tools"] = TOOL_SCHEMAS
        kwargs["tool_choice"] = "auto"
    return await client.chat.completions.create(**kwargs)


async def chat_once(
    settings: Settings,
    history: list[dict[str, Any]],
    user_text: str,
) -> dict[str, Any]:
    client = build_client(settings)
    model = inferred_model(settings)
    ctx = ToolContext(region=settings.search_region)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt(settings.user_name, settings.assistant_name)},
        *history,
        {"role": "user", "content": user_text},
    ]

    use_tools = True
    reply = ""
    for _ in range(6):
        try:
            response = await _complete(client, model, messages, tools=use_tools)
        except Exception as exc:
            if use_tools:
                use_tools = False
                if search_needed(user_text) and not ctx.sources:
                    results = search_web(user_text, region=settings.search_region)
                    ctx.sources.extend(serialize_sources(results))
                    messages.append(
                        {
                            "role": "system",
                            "content": "Результаты поиска:\n" + format_search_results(results),
                        }
                    )
                continue
            raise LLMError(f"Ошибка модели: {exc}") from exc

        choice = response.choices[0]
        message = choice.message
        tool_calls = getattr(message, "tool_calls", None) or []
        if tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": _message_text(message) or None,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.function.name,
                                "arguments": call.function.arguments or "{}",
                            },
                        }
                        for call in tool_calls
                    ],
                }
            )
            for call in tool_calls:
                result = await execute_tool(
                    ctx,
                    call.function.name,
                    call.function.arguments or "{}",
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": result,
                    }
                )
            continue

        reply = _message_text(message).strip()
        break

    if not reply and search_needed(user_text):
        results = search_web(user_text, region=settings.search_region)
        ctx.sources.extend(serialize_sources(results))
        messages.append(
            {
                "role": "system",
                "content": "Результаты поиска:\n" + format_search_results(results),
            }
        )
        response = await _complete(client, model, messages, tools=False)
        reply = _message_text(response.choices[0].message).strip()

    if not reply:
        reply = "Сэр, модель вернула пустой ответ. Проверьте ключ и выбранную модель в настройках."

    unique_sources = []
    seen = set()
    for src in ctx.sources:
        url = src.get("url")
        if url and url not in seen:
            seen.add(url)
            unique_sources.append(src)

    return {
        "reply": reply,
        "sources": unique_sources,
        "tools": ctx.log,
        "model": model,
        "provider": infer_provider(settings),
    }


async def speakable_chunks(text: str) -> AsyncIterator[str]:
    buf = []
    for char in text:
        buf.append(char)
        if char in ".!?…" and len(buf) > 40:
            yield "".join(buf).strip()
            buf = []
    tail = "".join(buf).strip()
    if tail:
        yield tail


def dump_tool_call(call: Any) -> str:
    return json.dumps(
        {"name": getattr(getattr(call, "function", None), "name", ""), "id": getattr(call, "id", "")},
        ensure_ascii=False,
    )
