"""
Главный модуль FastAPI приложения
Мониторинг конкурентов - MVP ассистент
"""
import base64
import time
import logging
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Body
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

from backend.config import settings
from backend.models.schemas import (
    TextAnalysisRequest,
    TextAnalysisResponse,
    ImageAnalysisResponse,
    ParseDemoRequest,
    ParseDemoResponse,
    ParsedContent,
    HistoryResponse,
    CollectCompetitorsRequest,
    CollectCompetitorsResponse,
    CompetitorSiteData,
)
from backend.services.openai_service import openai_service
from backend.services.parser_service import parser_service
from backend.services.history_service import history_service
from backend.services.pdf_service import detect_file_kind, pdf_to_png_base64_list

logger = logging.getLogger("competitor_monitor.api")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"

logger.info("=" * 60)
logger.info("ЗАПУСК ПРИЛОЖЕНИЯ: Мониторинг конкурентов")
logger.info("=" * 60)

app = FastAPI(
    title="Мониторинг конкурентов",
    description="MVP ассистент для анализа конкурентов с поддержкой текста и изображений",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info("CORS middleware добавлен")


# === Middleware для логирования запросов ===

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Логирование всех HTTP запросов"""
    start_time = time.time()
    
    # Логируем входящий запрос
    logger.info(f"➡️  {request.method} {request.url.path}")
    if request.query_params:
        logger.debug(f"    Query params: {dict(request.query_params)}")
    
    # Выполняем запрос
    response = await call_next(request)
    
    # Логируем ответ
    elapsed = time.time() - start_time
    status_emoji = "✅" if response.status_code < 400 else "❌"
    logger.info(f"{status_emoji} {request.method} {request.url.path} -> {response.status_code} ({elapsed:.3f}s)")
    
    return response


# === События жизненного цикла ===

@app.on_event("startup")
async def startup_event():
    """Событие при запуске сервера"""
    logger.info("=" * 60)
    logger.info("🟢 СЕРВЕР ЗАПУЩЕН")
    logger.info(f"  Адрес: http://{settings.api_host}:{settings.api_port}")
    logger.info(f"  Документация: http://localhost:{settings.api_port}/docs")
    logger.info(f"  Модель текста: {settings.openai_model}")
    logger.info(f"  Модель vision: {settings.openai_vision_model}")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """Закрытие ресурсов при остановке сервера"""
    logger.info("=" * 60)
    logger.info("🔴 ОСТАНОВКА СЕРВЕРА")
    logger.info("  Закрытие Parser сервиса...")
    await parser_service.close()
    logger.info("  ✓ Все ресурсы освобождены")
    logger.info("=" * 60)


# === Эндпоинты ===

@app.get("/")
async def root():
    """Главная страница - отдаём фронтенд"""
    index = FRONTEND_DIR / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=404, detail=f"Frontend not found: {index}")
    return FileResponse(index)


@app.post("/analyze_text", response_model=TextAnalysisResponse)
async def analyze_text(request: TextAnalysisRequest):
    """
    Анализ текста конкурента
    """
    logger.info("=" * 50)
    logger.info("📝 API: АНАЛИЗ ТЕКСТА")
    logger.info(f"  Длина текста: {len(request.text)} символов")
    logger.info(f"  Превью: {request.text[:80]}...")
    
    try:
        start_time = time.time()
        
        analysis = await openai_service.analyze_text(request.text)
        
        elapsed = time.time() - start_time
        logger.info(f"  ✓ Анализ завершён за {elapsed:.2f} сек")
        
        # Сохраняем в историю
        logger.info("  💾 Сохранение в историю...")
        history_service.add_entry(
            request_type="text",
            request_summary=request.text[:100] + "..." if len(request.text) > 100 else request.text,
            response_summary=analysis.summary
        )
        
        logger.info("  ✅ УСПЕХ: Анализ текста завершён")
        logger.info("=" * 50)
        
        return TextAnalysisResponse(
            success=True,
            analysis=analysis
        )
    except Exception as e:
        logger.error(f"  ❌ ОШИБКА: {e}")
        logger.error("=" * 50)
        return TextAnalysisResponse(
            success=False,
            error=str(e)
        )


@app.post("/analyze_image", response_model=ImageAnalysisResponse)
async def analyze_image(file: UploadFile = File(...)):
    """
    Анализ изображения или PDF конкурента.
    PDF рендерится в изображения (до 5 первых страниц) и уходит в Vision API.
    """
    logger.info("=" * 50)
    logger.info("🖼️ API: АНАЛИЗ ИЗОБРАЖЕНИЯ / PDF")
    logger.info(f"  Имя файла: {file.filename}")
    logger.info(f"  Тип: {file.content_type}")

    kind = detect_file_kind(file.filename, file.content_type)
    if kind == "unknown":
        logger.warning(f"  ⚠ Неподдерживаемый тип файла: {file.content_type}")
        logger.info("=" * 50)
        raise HTTPException(
            status_code=400,
            detail="Неподдерживаемый тип файла. Разрешены: JPEG, PNG, GIF, WEBP, PDF",
        )

    try:
        start_time = time.time()

        logger.info("  📥 Чтение файла...")
        content = await file.read()
        file_size_kb = len(content) / 1024
        logger.info(f"  Размер файла: {file_size_kb:.1f} KB")

        if kind == "pdf":
            logger.info("  📄 Конвертация PDF → PNG...")
            pages_b64 = pdf_to_png_base64_list(content)
            images = [(b64, "image/png") for b64 in pages_b64]
            history_label = f"PDF: {file.filename} ({len(images)} стр.)"
        else:
            mime = file.content_type or "image/jpeg"
            if mime == "image/jpg":
                mime = "image/jpeg"
            image_base64 = base64.b64encode(content).decode("utf-8")
            images = [(image_base64, mime)]
            history_label = f"Изображение: {file.filename}"

        logger.info("  🔍 Отправка на анализ...")
        analysis = await openai_service.analyze_images(images)

        elapsed = time.time() - start_time
        logger.info(f"  ✓ Анализ завершён за {elapsed:.2f} сек")

        logger.info("  💾 Сохранение в историю...")
        history_service.add_entry(
            request_type="image",
            request_summary=history_label,
            response_summary=(
                analysis.description[:200]
                if analysis.description
                else "Анализ изображения"
            ),
        )

        logger.info("  ✅ УСПЕХ: Анализ завершён")
        logger.info("=" * 50)

        return ImageAnalysisResponse(success=True, analysis=analysis)
    except ValueError as e:
        logger.error(f"  ❌ ОШИБКА PDF/файла: {e}")
        logger.error("=" * 50)
        return ImageAnalysisResponse(success=False, error=str(e))
    except Exception as e:
        logger.error(f"  ❌ ОШИБКА: {e}")
        logger.error("=" * 50)
        return ImageAnalysisResponse(success=False, error=str(e))


@app.post("/parse_demo", response_model=ParseDemoResponse)
async def parse_demo(request: ParseDemoRequest):
    """
    Парсинг и анализ сайта конкурента через Chrome
    """
    logger.info("=" * 50)
    logger.info("🌐 API: ПАРСИНГ САЙТА")
    logger.info(f"  URL: {request.url}")
    
    try:
        total_start = time.time()
        
        # Открываем страницу в Chrome и делаем скриншот
        logger.info("  🔍 Запуск парсинга...")
        parse_start = time.time()
        title, h1, first_paragraph, screenshot_bytes, error = await parser_service.parse_url(request.url)
        parse_elapsed = time.time() - parse_start
        logger.info(f"  ✓ Парсинг завершён за {parse_elapsed:.2f} сек")
        
        if error:
            logger.error(f"  ❌ Ошибка парсинга: {error}")
            logger.info("=" * 50)
            return ParseDemoResponse(
                success=False,
                error=error
            )
        
        logger.info(f"  📌 Title: {title[:50] if title else 'N/A'}...")
        logger.info(f"  📌 H1: {h1[:50] if h1 else 'N/A'}...")
        logger.info(f"  📌 Screenshot: {len(screenshot_bytes) / 1024:.1f} KB" if screenshot_bytes else "  📌 Screenshot: N/A")
        
        # Конвертируем скриншот в base64
        screenshot_base64 = parser_service.screenshot_to_base64(screenshot_bytes) if screenshot_bytes else None
        
        # Анализируем сайт через Vision API (скриншот + контекст)
        logger.info("  🤖 Запуск AI анализа...")
        ai_start = time.time()
        
        if screenshot_base64:
            analysis = await openai_service.analyze_website_screenshot(
                screenshot_base64=screenshot_base64,
                url=request.url,
                title=title,
                h1=h1,
                first_paragraph=first_paragraph
            )
        else:
            logger.warning("  ⚠ Скриншот недоступен, fallback на текстовый анализ")
            analysis = await openai_service.analyze_parsed_content(
                title=title,
                h1=h1,
                paragraph=first_paragraph
            )
        
        ai_elapsed = time.time() - ai_start
        logger.info(f"  ✓ AI анализ завершён за {ai_elapsed:.2f} сек")
        
        parsed_content = ParsedContent(
            url=request.url,
            title=title,
            h1=h1,
            first_paragraph=first_paragraph,
            analysis=analysis
        )
        
        # Сохраняем в историю
        logger.info("  💾 Сохранение в историю...")
        history_service.add_entry(
            request_type="parse",
            request_summary=f"URL: {request.url}",
            response_summary=analysis.summary[:100] if analysis.summary else f"Title: {title or 'N/A'}"
        )
        
        total_elapsed = time.time() - total_start
        logger.info(f"  ✅ УСПЕХ: Парсинг и анализ завершён за {total_elapsed:.2f} сек")
        logger.info(f"    - Парсинг: {parse_elapsed:.2f} сек")
        logger.info(f"    - AI анализ: {ai_elapsed:.2f} сек")
        logger.info("=" * 50)
        
        return ParseDemoResponse(
            success=True,
            data=parsed_content
        )
    except Exception as e:
        logger.error(f"  ❌ ОШИБКА: {e}")
        logger.error("=" * 50)
        return ParseDemoResponse(
            success=False,
            error=str(e)
        )


@app.get("/competitors")
async def list_competitors():
    """Список URL конкурентов из config.py"""
    urls = parser_service.get_competitor_urls()
    return {"competitor_urls": urls, "total": len(urls)}


@app.post("/collect_competitors", response_model=CollectCompetitorsResponse)
async def collect_competitors(
    request: Optional[CollectCompetitorsRequest] = Body(default=None),
):
    """
    Автосбор данных Selenium со всех сайтов из config (COMPETITOR_URLS).
    Опционально — AI-анализ каждого сайта.
    """
    if request is None:
        request = CollectCompetitorsRequest()

    logger.info("=" * 50)
    logger.info("API: АВТОСБОР КОНКУРЕНТОВ")
    urls = request.urls or parser_service.get_competitor_urls()
    logger.info(f"  URL: {len(urls)}, AI: {request.with_ai}")

    try:
        raw_items = await parser_service.collect_competitors(urls)
        items: List[CompetitorSiteData] = []

        for raw in raw_items:
            site = CompetitorSiteData(
                url=raw.get("url") or "",
                title=raw.get("title"),
                h1=raw.get("h1"),
                first_paragraph=raw.get("first_paragraph"),
                meta_description=raw.get("meta_description"),
                service_links=raw.get("service_links") or [],
                contacts=raw.get("contacts") or [],
                cta_texts=raw.get("cta_texts") or [],
                error=raw.get("error"),
            )

            if request.with_ai and not raw.get("error"):
                screenshot_bytes = raw.get("screenshot_bytes")
                screenshot_base64 = (
                    parser_service.screenshot_to_base64(screenshot_bytes)
                    if screenshot_bytes
                    else None
                )
                try:
                    if screenshot_base64:
                        site.analysis = await openai_service.analyze_website_screenshot(
                            screenshot_base64=screenshot_base64,
                            url=site.url,
                            title=site.title,
                            h1=site.h1,
                            first_paragraph=site.first_paragraph,
                        )
                    else:
                        site.analysis = await openai_service.analyze_parsed_content(
                            title=site.title,
                            h1=site.h1,
                            paragraph=site.first_paragraph,
                        )
                except Exception as ai_err:
                    logger.error(f"  AI ошибка для {site.url}: {ai_err}")
                    site.error = f"Сбор OK, AI ошибка: {ai_err}"

                history_service.add_entry(
                    request_type="parse",
                    request_summary=f"Автосбор: {site.url}",
                    response_summary=(
                        site.analysis.summary[:100]
                        if site.analysis and site.analysis.summary
                        else (site.title or site.url)
                    ),
                )

            items.append(site)

        ok = sum(1 for i in items if not i.error)
        logger.info(f"  Успешно: {ok}/{len(items)}")
        logger.info("=" * 50)

        return CollectCompetitorsResponse(
            success=True,
            total=len(items),
            items=items,
            competitor_urls=urls,
        )
    except Exception as e:
        logger.error(f"  ОШИБКА автосбора: {e}")
        logger.error("=" * 50)
        return CollectCompetitorsResponse(
            success=False,
            competitor_urls=urls,
            error=str(e),
        )


@app.get("/history", response_model=HistoryResponse)
async def get_history():
    """
    Получить историю последних 10 запросов
    """
    logger.info("📋 API: Получение истории")
    items = history_service.get_history()
    logger.info(f"  Записей: {len(items)}")
    return HistoryResponse(
        items=items,
        total=len(items)
    )


@app.delete("/history")
async def clear_history():
    """
    Очистить историю запросов
    """
    logger.info("🗑️ API: Очистка истории")
    history_service.clear_history()
    logger.info("  ✓ История очищена")
    return {"success": True, "message": "История очищена"}


@app.get("/health")
async def health_check():
    """Проверка работоспособности сервиса"""
    logger.debug("❤️ Health check")
    return {
        "status": "healthy",
        "service": "Competitor Monitor",
        "version": "1.0.0"
    }


# Статические файлы для фронтенда
if FRONTEND_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
    logger.info(f"Статические файлы: /static -> {FRONTEND_DIR}")
else:
    logger.warning(f"Папка frontend не найдена: {FRONTEND_DIR}")


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )
