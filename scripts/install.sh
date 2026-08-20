#!/usr/bin/env bash
# Идемпотентная установка зависимостей Nova + локального ИИ (Ollama).
set -u

MODEL="${NOVA_LOCAL_MODEL:-qwen2.5:3b}"

echo "[nova] Устанавливаю Python-зависимости…"
pip3 install --user -r requirements.txt

# --- Локальный ИИ (Ollama) — чтобы пользователю не нужны были API-ключи ---
if ! command -v ollama >/dev/null 2>&1; then
  echo "[nova] Устанавливаю Ollama…"
  if ! command -v zstd >/dev/null 2>&1; then
    sudo apt-get update -y >/dev/null 2>&1 && sudo apt-get install -y zstd >/dev/null 2>&1 || true
  fi
  curl -fsSL https://ollama.com/install.sh | sh || echo "[nova] Ollama не установлен (продолжаю без него)."
fi

# --- Скачиваю модель (через временный сервер) ---
if command -v ollama >/dev/null 2>&1; then
  if ! curl -sf http://127.0.0.1:11434/api/version >/dev/null 2>&1; then
    (ollama serve >/tmp/nova_ollama_install.log 2>&1 &)
    for i in $(seq 1 20); do curl -sf http://127.0.0.1:11434/api/version >/dev/null 2>&1 && break; sleep 1; done
  fi
  echo "[nova] Загружаю модель ${MODEL}…"
  ollama pull "${MODEL}" || echo "[nova] Модель не загружена (Nova перейдёт в демо-режим)."
fi

echo "[nova] Готово."
