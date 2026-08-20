@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
if exist "%~dp0NOVA.exe" (
  start "" "%~dp0NOVA.exe"
  exit /b 0
)
where py >nul 2>nul && (
  start "" pyw -3 run.py
  exit /b 0
)
where pythonw >nul 2>nul && (
  start "" pythonw run.py
  exit /b 0
)
echo NOVA runtime was not found.
pause
