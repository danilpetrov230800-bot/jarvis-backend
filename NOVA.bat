@echo off
chcp 65001 > nul
title NOVA — Neural Operational ^& Virtual Assistant
echo =======================================================
echo          NOVA Desktop AI Assistant (Windows)
echo =======================================================
echo.

cd /d "%~dp0"

:: Check if embedded runtime exists
if exist "runtime\python.exe" (
    set "PY_BIN=runtime\python.exe"
) else (
    set "PY_BIN=python"
)

:: Start NOVA server in background
echo Запуск локального ядра NOVA...
start "" /B "%PY_BIN%" server.py

:: Open Desktop UI in default web browser
timeout /t 2 /nobreak > nul
start http://127.0.0.1:8000

echo.
echo NOVA успешно запущена!
echo Адрес интерфейса: http://127.0.0.1:8000
echo.
pause
