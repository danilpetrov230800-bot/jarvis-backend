# NOVA Installation Guide

## Для пользователей

### Установка

1. Скачайте `NOVA-Setup.exe`
2. Дважды кликните для запуска
3. Выберите папку установки (по умолчанию `C:\Users\<user>\AppData\Local\Programs\NOVA`)
4. Нажмите **Install**
5. Запустите NOVA

### Первый запуск

При первом запуске NOVA покажет wizard:
- Welcome
- Choose AI provider
- Voice setup
- Permissions
- Done

NOVA работает без API key в локальном режиме.

### Удаление

Settings → Apps → NOVA → Uninstall, или через меню Пуск → NOVA → Uninstall.

## Для разработчиков

### Требования

- Node.js 20+
- Python 3.11+
- npm

### Dev запуск

```bash
cd nova/backend
pip install -r requirements.txt
cd ../frontend
npm install
npm run dev
```

### Production build (Windows)

```bash
cd nova/scripts
./build-windows.sh
```

Или на Windows:

```powershell
.\build-windows.ps1
```

Результат: `nova/release/NOVA-Setup.exe`
