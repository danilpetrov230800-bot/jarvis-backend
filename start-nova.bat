@echo off
REM Запуск Nova на Windows. Дважды кликните по этому файлу.
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
  py run.py
  goto end
)

where python >nul 2>nul
if %errorlevel%==0 (
  python run.py
  goto end
)

echo Не найден Python. Установите его (отметьте "Add Python to PATH"): https://www.python.org/downloads/windows/
start https://www.python.org/downloads/windows/

:end
echo.
pause
