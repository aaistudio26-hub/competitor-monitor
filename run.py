"""
Скрипт запуска веб-приложения «Мониторинг конкурентов»
"""
import uvicorn
import logging
from backend.config import settings, logger

logging.getLogger("competitor_monitor").setLevel(logging.INFO)

if __name__ == "__main__":
    print()
    print("=" * 60)
    print("МОНИТОРИНГ КОНКУРЕНТОВ - AI Ассистент")
    print("=" * 60)
    print()
    print(f"Ве-интерфейс:  http://localhost:{settings.api_port}")
    print(f"Документация:   http://localhost:{settings.api_port}/docs")
    print()
    print(f"Модель текста:  {settings.openai_model}")
    print(f"Модель vision:  {settings.openai_vision_model}")
    print(f"API ключ:       {'OK' if settings.openai_api_key else 'НЕ ЗАДАН'}")
    print()
    print("-" * 60)
    print()

    uvicorn.run(
        "backend.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level="info",
    )
