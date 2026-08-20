# Тестирование NOVA

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Покрыто:

- запуск без API-ключа
- текст, память, навыки, агенты
- подтверждение опасных действий
- отказ в разрешении
- wake word и защита от эха
- офлайн-режим
- диагностика
- backup
- path traversal / zip slip / подмена калькулятора
- стресс: 100+ сообщений, много навыков и памяти

Сборка Windows:

GitHub Actions `windows-release` ставит пакет, запускает установленный `NOVA.exe`, затем удаляет его.
