@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title JARVIS
echo.
echo  ========================================
echo   JARVIS
echo   Первый запуск может занять 1–3 минуты
echo   (ставится Python, если его нет).
echo  ========================================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\bootstrap.ps1"
if errorlevel 1 (
  echo.
  echo  Не удалось запустить. Если файл скачан из интернета:
  echo  ПКМ по JARVIS.bat → Свойства → Разблокировать → ОК.
  echo.
  pause
)
