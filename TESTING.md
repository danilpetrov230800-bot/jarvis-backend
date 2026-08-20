# Тестирование NOVA

Локальная проверка:

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q
```

Windows production pipeline в GitHub Actions собирает приложение PyInstaller, создаёт `NOVA-Setup.exe` Inno Setup и публикует `release/` как artifact.

Перед выпуском проверяются API, сохранение памяти, skills, tasks, permissions, backup/restore, упаковка и запуск нативного окна. Установщик должен дополнительно проверяться на чистом Windows 10/11 x64: install, launch, relaunch, shortcut и uninstall.
