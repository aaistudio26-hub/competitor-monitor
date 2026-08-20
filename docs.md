# 📚 Документация API - Мониторинг конкурентов

## Содержание

1. [Структура проекта](#структура-проекта)
2. [Описание API](#описание-api)
3. [Примеры запросов](#примеры-запросов)
4. [Мультимодальные функции](#мультимодальные-функции)
5. [Модели данных](#модели-данных)

---

## Структура проекта

```
competitor-monitor/
│
├── backend/                     # Backend модуль
│   ├── __init__.py
│   ├── main.py                  # Главный файл FastAPI
│   ├── config.py                # Конфигурация приложения
│   │
│   ├── models/                  # Pydantic модели
│   │   ├── __init__.py
│   │   └── schemas.py           # Схемы запросов/ответов
│   │
│   └── services/                # Бизнес-логика
│       ├── __init__.py
│       ├── openai_service.py    # Интеграция с OpenAI
│       ├── parser_service.py    # Парсинг веб-страниц
│       └── history_service.py   # Управление историей
│
├── frontend/                    # Frontend модуль
│   ├── index.html               # Главная HTML страница
│   ├── styles.css               # CSS стили
│   └── app.js                   # JavaScript приложение
│
├── requirements.txt             # Python зависимости
├── env.example.txt              # Пример переменных окружения
├── history.json                 # Файл истории запросов
├── README.md                    # Описание проекта
└── docs.md                      # Эта документация
```

---

## Описание API

### Базовый URL

```
http://localhost:8000
```

### Эндпоинты

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/` | Главная страница (веб-интерфейс) |
| POST | `/analyze_text` | Анализ текста конкурента |
| POST | `/analyze_image` | Анализ изображения или PDF |
| POST | `/parse_demo` | Парсинг и анализ сайта по URL |
| GET | `/competitors` | Список URL конкурентов из config |
| POST | `/collect_competitors` | Автосбор и AI-анализ конкурентов |
| GET | `/history` | Получение истории запросов |
| DELETE | `/history` | Очистка истории запросов |
| GET | `/health` | Проверка работоспособности |
| GET | `/docs` | Swagger UI документация |
| GET | `/redoc` | ReDoc документация |

---

## Примеры запросов

### 1. Анализ текста (`POST /analyze_text`)

**Запрос:**
```bash
curl -X POST "http://localhost:8000/analyze_text" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Наша компания предлагает уникальные решения для бизнеса. Мы работаем на рынке 10 лет и обслуживаем более 1000 клиентов. Наши преимущества: быстрая доставка, гарантия качества, индивидуальный подход к каждому клиенту."
  }'
```

**Ответ:**
```json
{
  "success": true,
  "analysis": {
    "strengths": [
      "Долгий опыт работы на рынке (10 лет)",
      "Большая клиентская база (1000+ клиентов)",
      "Комплексный подход к обслуживанию"
    ],
    "weaknesses": [
      "Отсутствие конкретных цен",
      "Нет упоминания о технологиях",
      "Общие формулировки без специфики"
    ],
    "unique_offers": [
      "Индивидуальный подход к каждому клиенту",
      "Гарантия качества"
    ],
    "recommendations": [
      "Добавить конкретные цифры и кейсы",
      "Указать уникальные технологические преимущества",
      "Включить отзывы клиентов"
    ],
    "summary": "Компания позиционирует себя как надёжного партнёра с опытом, но маркетинговые материалы требуют конкретизации для повышения конверсии."
  },
  "error": null
}
```

### 2. Анализ изображения (`POST /analyze_image`)

**Запрос:**
```bash
curl -X POST "http://localhost:8000/analyze_image" \
  -F "file=@banner.jpg"
```

**Ответ:**
```json
{
  "success": true,
  "analysis": {
    "description": "Рекламный баннер с изображением продукта на синем градиентном фоне. Крупный заголовок белым шрифтом, кнопка CTA оранжевого цвета.",
    "marketing_insights": [
      "Чёткая визуальная иерархия привлекает внимание",
      "Контрастная цветовая схема выделяет CTA",
      "Минималистичный дизайн не перегружает восприятие"
    ],
    "visual_style_score": 7,
    "visual_style_analysis": "Современный корпоративный стиль с хорошим балансом элементов. Типографика читабельна, но можно улучшить отступы.",
    "recommendations": [
      "Добавить социальное доказательство (отзывы, рейтинги)",
      "Увеличить размер CTA кнопки",
      "Рассмотреть A/B тестирование цветов"
    ]
  },
  "error": null
}
```

### 3. Парсинг сайта (`POST /parse_demo`)

**Запрос:**
```bash
curl -X POST "http://localhost:8000/parse_demo" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "example.com"
  }'
```

**Ответ:**
```json
{
  "success": true,
  "data": {
    "url": "https://example.com",
    "title": "Example Domain",
    "h1": "Example Domain",
    "first_paragraph": "This domain is for use in illustrative examples in documents.",
    "analysis": {
      "strengths": ["..."],
      "weaknesses": ["..."],
      "unique_offers": ["..."],
      "recommendations": ["..."],
      "summary": "..."
    }
  },
  "error": null
}
```

### 4. Получение истории (`GET /history`)

**Запрос:**
```bash
curl -X GET "http://localhost:8000/history"
```

**Ответ:**
```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "timestamp": "2024-01-15T10:30:00",
      "request_type": "text",
      "request_summary": "Наша компания предлагает уникальные решения...",
      "response_summary": "Компания позиционирует себя как надёжного партнёра..."
    }
  ],
  "total": 1
}
```

### 5. Очистка истории (`DELETE /history`)

**Запрос:**
```bash
curl -X DELETE "http://localhost:8000/history"
```

**Ответ:**
```json
{
  "success": true,
  "message": "История очищена"
}
```

### 6. Проверка здоровья (`GET /health`)

**Запрос:**
```bash
curl -X GET "http://localhost:8000/health"
```

**Ответ:**
```json
{
  "status": "healthy",
  "service": "Competitor Monitor",
  "version": "1.0.0"
}
```

---

## Мультимодальные функции

### Поддержка текста

Приложение анализирует любой текстовый контент конкурентов:
- Описания продуктов
- Тексты с лендингов
- Рекламные объявления
- Посты в социальных сетях
- Email рассылки

**Минимальная длина текста:** 10 символов

### Поддержка изображений

Поддерживаемые форматы:
- JPEG/JPG
- PNG
- GIF
- WebP

**Что можно анализировать:**
- Рекламные баннеры
- Скриншоты сайтов
- Фотографии упаковки
- Креативы для социальных сетей
- Логотипы и фирменный стиль

**Максимальный размер:** 10MB (рекомендуется до 4MB для быстрой обработки)

### Парсинг веб-страниц

Автоматически извлекаемые элементы:
- `<title>` — заголовок страницы
- `<h1>` — главный заголовок
- Первый значимый `<p>` — первый абзац (минимум 50 символов)

**Особенности:**
- Автоматическое добавление протокола `https://`
- Следование редиректам
- Таймаут: 10 секунд
- User-Agent: Mozilla/5.0 (имитация браузера)

---

## Модели данных

### TextAnalysisRequest
```typescript
{
  text: string  // Минимум 10 символов
}
```

### ParseDemoRequest
```typescript
{
  url: string  // URL сайта для парсинга
}
```

### CompetitorAnalysis
```typescript
{
  strengths: string[]      // Сильные стороны
  weaknesses: string[]     // Слабые стороны
  unique_offers: string[]  // Уникальные предложения
  recommendations: string[] // Рекомендации
  summary: string          // Общее резюме
}
```

### ImageAnalysis
```typescript
{
  description: string           // Описание изображения
  marketing_insights: string[]  // Маркетинговые инсайты
  visual_style_score: number    // Оценка 0-10
  visual_style_analysis: string // Анализ стиля
  recommendations: string[]     // Рекомендации
}
```

### HistoryItem
```typescript
{
  id: string              // UUID записи
  timestamp: datetime     // Время запроса
  request_type: string    // "text" | "image" | "parse"
  request_summary: string // Краткое описание запроса
  response_summary: string // Краткое описание ответа
}
```

---

## Коды ошибок

| Код | Описание |
|-----|----------|
| 200 | Успешный запрос |
| 400 | Некорректный запрос (неверный формат, короткий текст) |
| 422 | Ошибка валидации данных |
| 500 | Внутренняя ошибка сервера |

---

## Конфигурация

### Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `OPENAI_API_KEY` | API ключ [OpenAI](https://platform.openai.com/api-keys) | - |
| `OPENAI_BASE_URL` | Базовый URL API | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | Модель для текста | `gpt-4o-mini` |
| `OPENAI_VISION_MODEL` | Модель для изображений | `gpt-4o-mini` |
| `API_HOST` | Хост сервера | `0.0.0.0` |
| `API_PORT` | Порт сервера | `8000` |

### OpenAI API

Проект использует официальный [OpenAI API](https://platform.openai.com/docs/api-reference).
- Ключ: [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- Документация: [API Reference](https://platform.openai.com/docs/api-reference)

### Настройки истории

- Максимум записей: **10**
- Файл хранения: `history.json`
- Формат: JSON с UTF-8 кодировкой

---

## Безопасность

⚠️ **Важно:**
- Не храните API ключи в коде
- Используйте `.env` файл для секретов
- Добавьте `.env` в `.gitignore`
- В продакшене используйте HTTPS
- Настройте CORS для конкретных доменов

