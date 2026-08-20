# Desktop — автономное приложение

Можно переносить отдельно от корня проекта (внутри есть `backend/`).

```
desktop/
├── main.py, api_client.py, paths.py, styles.py
├── backend/              # копия из ../backend (sync_backend.py)
├── requirements.txt
├── sync_backend.py
├── build.py
└── dist/CompetitorMonitor.exe
```

## Запуск

```bash
cd desktop
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Или `dist/CompetitorMonitor.exe`.

Ключ OpenAI: `.env` / `env` в `desktop/` или `dist/`, либо «Настройки».

Нужен Google Chrome для парсинга сайтов.

## Синхронизация backend

```bash
python sync_backend.py
```

## Сборка exe

```bash
python build.py
```
