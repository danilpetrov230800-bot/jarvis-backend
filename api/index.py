from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI
import os

app = FastAPI()


class Message(BaseModel):
    text: str


@app.get("/")
def home():
    return {"status": "JARVIS online"}


@app.post("/chat")
def chat(message: Message):
    key = os.getenv("OPENAI_API_KEY")

    if not key:
        return {"error": "OPENAI_API_KEY not configured"}

    client = OpenAI(api_key=key)

    response = client.responses.create(
        model="gpt-5",
        instructions=(
            "Ты JARVIS — персональный AI-ассистент Данилы. "
            "Отвечай по-русски, естественно, кратко и уверенно."
        ),
        input=message.text
    )

    return {
        "reply": response.output_text
    }
