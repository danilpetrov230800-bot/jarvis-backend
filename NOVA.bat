@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHONPATH=%~dp0"
title NOVA
if not exist "%~dp0data" mkdir "%~dp0data"
echo.
echo  NOVA
echo  Keep this window open.
echo  First start may take 1-3 minutes.
echo  If install fails, copy this folder to C:\NOVA
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\bootstrap.ps1"
set ERR=%ERRORLEVEL%
echo.
if not "%ERR%"=="0" (
  echo  Start failed, code %ERR%
  echo  Log: "%~dp0data\nova.log"
  echo  If the file came from the internet:
  echo  Right-click NOVA.bat, Properties, Unblock, OK.
)
echo.
echo  If the window did not open, go to:
echo    http://127.0.0.1:8080
echo  Press any key to close this console.
pause >nul
