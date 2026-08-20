#!/usr/bin/env bash
# Запуск Nova на Linux. Дважды кликните или выполните: bash start-nova.sh
cd "$(dirname "$0")" || exit 1

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "Не найден Python 3. Установите его: https://www.python.org/downloads/"
  read -r -p "Нажмите Enter для выхода…" _
  exit 1
fi

"$PY" run.py
read -r -p "Nova остановлена. Нажмите Enter, чтобы закрыть…" _
