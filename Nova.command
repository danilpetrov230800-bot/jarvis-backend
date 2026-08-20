#!/usr/bin/env bash
# Запуск Nova на macOS. Дважды кликните по этому файлу.
cd "$(dirname "$0")" || exit 1

if command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  echo "Не найден Python 3. Установите его: https://www.python.org/downloads/macos/"
  read -r -p "Нажмите Enter для выхода…" _
  exit 1
fi

"$PY" run.py
read -r -p "Nova остановлена. Нажмите Enter, чтобы закрыть…" _
