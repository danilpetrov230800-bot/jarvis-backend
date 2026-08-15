from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI
import os

app = FastAPI()

class Message(BaseModel):
    text: str

@app.get("/")
def root():
    return {"status": "JARVIS online"}

@app.post("/")
def chat(message: Message):
    api_key = os.environ.get("OPENAI_API_KEY")

    if not api_key:
        return {"error": "OPENAI_API_KEY не найден"}

    client = OpenAI(api_key=api_key)

    response = client.responses.create(
        model="gpt-5",
        instructions=(
            "Ты JARVIS — персональный AI-ассистент Данилы. "
            "Отвечай на русском языке, естественно, уверенно и кратко."
        ),
        input=message.text
    )

    return {
        "reply": response.output_text
    }
