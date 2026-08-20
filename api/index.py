"""Hosted compatibility endpoint. The full product is the Windows desktop app."""

from __future__ import annotations

import os

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="NOVA hosted", version="1.0.0", docs_url=None, redoc_url=None)


class Message(BaseModel):
    text: str


@app.get("/")
@app.get("/health")
@app.get("/api/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "product": "NOVA",
        "note": "Install NOVA-Setup.exe for the desktop assistant.",
    }


@app.post("/chat")
@app.post("/api/chat")
def chat(message: Message) -> dict[str, str]:
    key = (os.getenv("NOVA_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        return {
            "reply": "Это только online-заглушка. Скачайте NOVA-Setup.exe, установите и запустите NOVA на компьютере."
        }
    try:
        from openai import OpenAI

        client = OpenAI(api_key=key)
        response = client.chat.completions.create(
            model=os.getenv("NOVA_MODEL", "gpt-4.1-mini"),
            messages=[
                {
                    "role": "system",
                    "content": "Ты NOVA — персональный ассистент. Отвечай по-русски, кратко и по делу.",
                },
                {"role": "user", "content": message.text},
            ],
        )
        return {"reply": (response.choices[0].message.content or "").strip()}
    except Exception:
        return {"reply": "Не удалось получить ответ модели."}
