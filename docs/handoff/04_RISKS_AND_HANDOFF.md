# Risks and Handoff

## Три главных риска

| Риск по коду или входу | Как проявляется | Действие при передаче |
| --- | --- | --- |
| Недостоверные или пустые выводы | Внешний текст и кадры могут содержать инструкции для модели. Выводы могут добавлять факты, а ошибка разбора JSON маскироваться дефолтами. | До использования сверять цены, сроки, услуги и кейсы с источником. Включить пустой JSON, повреждённый JSON, конфликтную инструкцию и короткий текст в проверку. Предложение: добавить строгую валидацию и явный статус ошибки. |
| Неполный сбор материалов | Selenium зависит от Chrome, сети и доступности страницы. Анализируется один снимок окна, сайт может показать заглушку или антибот-страницу. PDF ограничен пятью первыми страницами. | Сверить заголовок и видимую часть сайта, сначала прогнать сбор с `with_ai:false`. Для важных сведений после страницы 5 подготовить отдельный PDF. При сбое проверить ChromeDriver, логи парсера и ошибки по каждому URL. |
| Утечка материала или доступ к локальному API | В API нет прикладной аутентификации, CORS настроен широко, привязка по умолчанию `0.0.0.0`. Материал уходит провайдеру модели, в логах веб-анализа есть превью текста, история хранится локально. | Для запуска ниже указать `API_HOST=127.0.0.1`. Тестировать на синтетических или разрешённых материалах. Перед сетевым развёртыванием согласовать аутентификацию, ограничения исходящих URL/редиректов, обработку загрузок и хранение данных. Ключ, историю и входные материалы держать вне Git. |

## Запуск веб-версии

Нужны Git и Python 3.10+ (для первого запуска используйте 3.11 или 3.12), доступ к PyPI и к настроенному провайдеру модели. Для парсинга нужны Chrome и совместимый ChromeDriver. При первом парсинге `webdriver-manager` может скачать драйвер. [requirements.txt](../../requirements.txt) содержит минимальные версии FastAPI, Uvicorn, OpenAI SDK, Pydantic, python-dotenv, python-multipart, PyMuPDF, Pillow, Selenium и webdriver-manager. Для воспроизводимости запишите версию Python и вывод `pip freeze` после успешного запуска.

PowerShell, в новом каталоге клона. Если репозиторий уже скачан, начните с создания окружения и сохраните существующую конфигурацию.

```powershell
git clone https://github.com/aaistudio26-hub/competitor-monitor.git
Set-Location competitor-monitor
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item env.example.txt .env }
git check-ignore .env
```

В локальном `.env` укажите `OPENAI_API_KEY` с доступом к выбранным моделям и `API_HOST=127.0.0.1`. [config.py](../../backend/config.py) загружает локальный файл с приоритетом над окружением и удаляет `OPENAI_API_KEY` из окружения, если локальный файл не найден. `OPENAI_MODEL` и `OPENAI_VISION_MODEL` по умолчанию равны `gpt-4o-mini`. При использовании другого `OPENAI_BASE_URL` проверьте доступ к обеим моделям. `COMPETITOR_URLS` переопределяет встроенный список. Если настройки падают на разборе `COMPETITOR_URLS`, закомментируйте строку, чтобы использовать значения по умолчанию, и проверьте `GET /competitors`. Для разового списка используйте поле `urls` запроса.

```powershell
.\.venv\Scripts\python.exe run.py
```

Веб-интерфейс — [localhost:8000](http://localhost:8000/), Swagger UI — [localhost:8000/docs](http://localhost:8000/docs). На Linux/macOS используйте `.venv/bin/python` и `cp env.example.txt .env` при первичной настройке.

## Запуск desktop и синхронизация

Из корня репозитория в PowerShell:

```powershell
Set-Location desktop
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Desktop использует собственную копию backend и зависимости из [desktop/requirements.txt](../../desktop/requirements.txt), включая PyQt6 и PyInstaller. Ключ задаётся через «Настройки» либо локальный `.env` в `desktop/` или рядом с EXE. После правок в корневом backend выполните `.\.venv\Scripts\python.exe sync_backend.py` из `desktop/` и проверьте разницу через `git diff -- backend` в этом каталоге. Скрипт заменяет каталог `desktop/backend` целиком. Для сборки Windows выполните `.\.venv\Scripts\python.exe build.py`; проверьте результат в `desktop/dist/CompetitorMonitor.exe` и сообщение о синхронизации. При ошибке синхронизации сборка может использовать прежнюю копию.

## Быстрые проверки

В отдельном окне PowerShell после запуска веб-сервера:

```powershell
$monitorApi = 'http://127.0.0.1:8000'
Invoke-RestMethod "$monitorApi/health"
Invoke-RestMethod "$monitorApi/competitors"

$monitorText = @{
  text = 'Регистрируем ООО за 5 рабочих дней. Стоимость от 20 000 рублей. Оставьте заявку на консультацию.'
} | ConvertTo-Json -Compress
Invoke-RestMethod "$monitorApi/analyze_text" -Method Post -ContentType 'application/json; charset=utf-8' -Body $monitorText |
  ConvertTo-Json -Depth 8

# Подготовьте banner.png с читаемым оффером и sample.pdf с тем же оффером.
curl.exe -sS -F 'file=@banner.png;type=image/png' "$monitorApi/analyze_image"
curl.exe -sS -F 'file=@sample.pdf;type=application/pdf' "$monitorApi/analyze_image"

$monitorCollect = @{ urls = @('https://example.com/'); with_ai = $false } | ConvertTo-Json -Compress
Invoke-RestMethod "$monitorApi/collect_competitors" -Method Post -ContentType 'application/json' -Body $monitorCollect |
  ConvertTo-Json -Depth 8
Invoke-RestMethod "$monitorApi/history" | ConvertTo-Json -Depth 8
```

| Проверка | Что считать прохождением |
| --- | --- |
| Запуск и текст | `health.status=healthy`. Текстовый ответ содержит `success:true`, непустой `summary`, регистрацию ООО в `service_focus` и не приписывает другие услуги. |
| Кадр и PDF | `success:true`, непустой `description`, три целочисленные оценки в диапазоне 0–10. Сверьте оффер с изображением. Для контрольного PDF из шести страниц поместите отдельный оффер на шестой странице и убедитесь по логам, что передано пять кадров. |
| Chrome и сайт | В сборе без ИИ у доступного URL нет `items[0].error`, получен title. Затем в Swagger вызовите `/parse_demo` для доступной тестовой страницы B2B-юрфирмы и проверьте `data.analysis.summary`. |
| Ошибки и история | В Swagger отправьте `{"text":"abc"}` и получите HTTP 422. Отправьте файл `.txt` с `text/plain` и получите HTTP 400. Временно выберите несуществующее имя модели в тестовой конфигурации и перезапустите сервер. Проверьте `success:false` с `error` при анализе, верните настройку и перезапустите. История после успешных анализов содержит краткие записи. |
| Desktop | Запустите окно отдельно от веб-сервера, задайте ключ локально, повторите текст, изображение/PDF и проверку истории через UI. |

Подсказка интерфейса и `docs.md` упоминают 10 MB. В обработчике загрузки нет явной проверки этого лимита. Также в `docs.md` приведены прежние поля визуальной оценки. Для диагностики используйте [фактические схемы](../../backend/models/schemas.py) и локальный Swagger. В проверенном снимке нет выделенного набора автотестов проекта, поэтому эта таблица служит стартовым ручным прогоном.

## Чек-лист передачи и первый день

- [ ] Получить доступ к репозиторию и тестовой учётной записи провайдера модели, записать SHA исходной версии.
- [ ] Настроить локальное окружение, сверить имена моделей и выполнить проверки таблицы. Записать окружение, входы и результаты без секретов.
- [ ] Найти оба промпта и карту полей по [руководству](02_PROMPT_ENGINEERING_GUIDE.md), проверить запасной текстовый путь и самостоятельный промпт сайта.
- [ ] Собрать регрессионную выборку, разметить факты, выполнить базовый прогон A и согласовать пороги с владельцем проекта по [метрикам](03_SUCCESS_METRICS.md).
- [ ] Первую правку оформить отдельным коммитом с гипотезой и результатами повторного прогона. Для desktop синхронизировать backend и проверить UI. При провале контрольных критериев вернуться к базовому коммиту в тестовой ветке.
