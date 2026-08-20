@echo off
chcp 65001 > nul
title Установка и настройка NOVA
echo =======================================================
echo          Установщик NOVA Desktop Assistant
echo =======================================================
echo.

cd /d "%~dp0"

echo [1/3] Проверка компонентов...
if not exist "runtime" mkdir "runtime"

echo [2/3] Установка библиотек...
pip install -r requirements.txt --no-warn-script-location

echo [3/3] Создание ярлыков на рабочем столе...
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\NOVA.lnk'); $s.TargetPath = '%~dp0NOVA.bat'; $s.WorkingDirectory = '%~dp0'; $s.IconLocation = '%~dp0static\favicon.svg'; $s.Save()"

echo.
echo =======================================================
echo          Установка успешно завершена!
echo =======================================================
echo Ярлык "NOVA" создан на рабочем столе.
echo.
pause
