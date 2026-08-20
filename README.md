# Мониторинг конкурентов — AI-ассистент для B2B юруслуг

Инструмент для анализа конкурентов на рынке юридических услуг для бизнеса:  
**регистрация и ликвидация компаний, лицензирование, арбитраж**.

Помогает быстро понять, как конкуренты подают оффер, насколько прозрачны цены и сроки, где сильнее доверие и CTA, и что можно усилить в своей позиции.

---

## Зачем нужна программа

Юридическим фирмам и маркетологам в нише B2B часто нужно:

- сравнить сайты и материалы конкурентов без ручного «простынного» разбора;
- оценить тексты, лендинги, коммерческие предложения;
- разобрать скриншоты и PDF (презентации, КП, буклеты);
- собрать контент с сайтов конкурентов и сразу получить AI-выводы;
- сохранить историю разборов для повторного просмотра.

Программа заточена под **деловую юридическую нишу**, а не под массовые услуги для физлиц и не оценивает «вау-дизайн» / анимации как главный критерий. В фокусе:

- покрытие услуг (регистрация, ликвидация, лицензии, арбитраж);
- экспертность и доверие;
- понятность оффера для собственников и директоров;
- прозрачность цен и сроков;
- сила призыва к действию (консультация, заявка);
- конкурентная угроза и пробелы в контенте.

---

## Что умеет

| Функция | Описание |
|--------|----------|
| Анализ текста | Вставьте текст с сайта / КП — получите структурированный разбор и оценки |
| Анализ изображений и PDF | Скриншоты, баннеры, PDF (страницы → Vision) |
| Парсинг сайта | Selenium + Chrome: загрузка страницы, текст, скриншот, AI-анализ |
| Автосбор конкурентов | Список URL из конфига (`.env` / `COMPETITOR_URLS`) |
| История | Последние запросы сохраняются локально |
| Два интерфейса | Веб (браузер) и desktop-приложение (PyQt6 / `.exe`) |

---

## Требования

- Python **3.10+** (рекомендуется 3.11–3.13)
- Ключ [OpenAI API](https://platform.openai.com/api-keys)
- Для парсинга сайтов — установленный **Google Chrome**
- Windows — для сборки и запуска desktop `.exe` (веб работает и на других ОС)

---

## Быстрый старт (веб)

```bash
git clone <URL-вашего-репозитория>
cd DZ_M4L8   # или имя папки после clone

python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
# source venv/bin/activate

pip install -r requirements.txt
copy env.example.txt .env          # Windows
# cp env.example.txt .env          # Linux / macOS
```

Откройте `.env` и укажите:

```env
OPENAI_API_KEY=sk-ваш_ключ
```

Запуск:

```bash
python run.py
```

Откройте в браузере: http://localhost:8000  
Документация API: http://localhost:8000/docs  

Подробное описание эндпоинтов — в [`docs.md`](docs.md).

---

## Desktop-приложение

Папка [`desktop/`](desktop/) самодостаточна: внутри своя копия `backend/`, её можно переносить отдельно.

### Запуск из исходников

```bash
cd desktop
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### Ключ OpenAI

Один из вариантов:

1. Файл `.env` или `env` в папке `desktop/` (или рядом с `.exe` в `dist/`)
2. Кнопка **«Настройки»** в приложении — ключ сохранится в локальный `.env`

Без ключа приложение **запускается**; анализ станет доступен после указания ключа.

### Сборка `.exe` (Windows)

```bash
cd desktop
pip install -r requirements.txt
python build.py
```

Готовый файл: `desktop/dist/CompetitorMonitor.exe`  
Перед сборкой скрипт синхронизирует `../backend` → `desktop/backend`.

Подробнее: [`desktop/README.md`](desktop/README.md).

---

## Структура репозитория

```
├── backend/              # FastAPI + сервисы (источник правды)
│   ├── main.py           # HTTP API
│   ├── config.py         # настройки и .env
│   ├── models/           # Pydantic-схемы
│   └── services/         # OpenAI, Selenium-парсер, PDF, история
├── frontend/             # веб-интерфейс (HTML/CSS/JS)
├── desktop/              # PyQt6 UI + копия backend + сборка exe
├── run.py                # запуск веб-сервера
├── requirements.txt      # зависимости веб-режима
├── env.example.txt       # пример переменных окружения
├── docs.md               # описание API
└── README.md
```

После правок в корневом `backend/` для desktop:

```bash
cd desktop
python sync_backend.py
```

---

## Переменные окружения

Скопируйте `env.example.txt` → `.env` (файл `.env` **не** попадает в Git).

| Переменная | Назначение |
|------------|------------|
| `OPENAI_API_KEY` | Ключ OpenAI (**обязательно** для анализа) |
| `OPENAI_MODEL` | Модель текста (по умолчанию `gpt-4o-mini`) |
| `OPENAI_VISION_MODEL` | Модель vision |
| `OPENAI_BASE_URL` | Базовый URL API (по умолчанию официальный OpenAI) |
| `COMPETITOR_URLS` | URL конкурентов через запятую |
| `API_HOST` / `API_PORT` | Хост и порт веб-сервера |

---

## Безопасность

- Не коммитьте файл `.env` и не публикуйте API-ключи
- Если ключ когда-либо попал в чат, скриншот или репозиторий — **перевыпустите** его на platform.openai.com
- История запросов (`history.json`) хранится локально и игнорируется Git

---

## Стек

- **Backend:** FastAPI, Pydantic, OpenAI API, Selenium, PyMuPDF  
- **Frontend:** HTML / CSS / JavaScript  
- **Desktop:** PyQt6, PyInstaller  

---

## Лицензия

Учебный / демонстрационный проект. См. [LICENSE](LICENSE).

---

## Как загрузить на GitHub

На этом компьютере Git может быть ещё не установлен. Установите [Git for Windows](https://git-scm.com/download/win), затем в папке проекта:

```bash
git init
git add .
git status
# Убедитесь, что в списке НЕТ файла .env
git commit -m "Initial commit: competitor monitor for B2B legal services"
```

На GitHub создайте пустой репозиторий (без README), затем:

```bash
git branch -M main
git remote add origin https://github.com/<ваш-логин>/<имя-репо>.git
git push -u origin main
```

Либо через GitHub Desktop: File → Add local repository → Publish repository.

**Перед push проверьте:** в коммит не попал `.env` с настоящим ключом.
