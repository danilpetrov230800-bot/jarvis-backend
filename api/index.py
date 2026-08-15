from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI
import os

app = FastAPI()

class Message(BaseModel):
    text: str

@app.get("/api")
def home():
    return {"status": "JARVIS online"}

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.post("/api/chat")
def chat(message: Message):
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    response = client.responses.create(
        model="gpt-5",
        instructions=(
            "Ты JARVIS — персональный AI-ассистент Данилы. "
            "Отвечай естественно, уверенно и кратко. "
            "Говори по-русски, если пользователь говорит по-русски."
        ),
        input=message.text
    )

    return {
        "reply": response.output_text
    }
