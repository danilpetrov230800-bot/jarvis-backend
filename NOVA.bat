@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title NOVA
echo.
echo  NOVA
echo  First start may take 1-3 minutes.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\bootstrap.ps1"
if errorlevel 1 (
  echo.
  echo  Start failed.
  echo  Right-click NOVA.bat, Properties, Unblock, OK.
  echo.
  pause
)
