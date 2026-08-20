#!/usr/bin/env bash
# Ждём локальный ИИ (Ollama), затем запускаем веб-сервер Nova.
set -u

MODEL="${NOVA_LOCAL_MODEL:-qwen2.5:3b}"

echo "[nova] Жду запуска Ollama…"
for i in $(seq 1 30); do
  curl -sf http://127.0.0.1:11434/api/version >/dev/null 2>&1 && break
  sleep 1
done

# Убеждаемся, что модель на месте (быстрый no-op, если уже скачана).
if command -v ollama >/dev/null 2>&1; then
  ollama pull "${MODEL}" >/dev/null 2>&1 || true
fi

echo "[nova] Запускаю веб-сервер на http://0.0.0.0:8000"
exec python3 -m uvicorn api.index:app --host 0.0.0.0 --port 8000
