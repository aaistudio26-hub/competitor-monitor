"""
Локальный backend для автономного desktop-приложения.
Вызывает сервисы напрямую — без HTTP-сервера.
"""
from __future__ import annotations

import asyncio
import base64
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("competitor_monitor.desktop")


def _run(coro):
    """Запуск async-корутины из sync WorkerThread."""
    return asyncio.run(coro)


class LocalAPIClient:
    """Полный аналог HTTP API, но локально."""

    def __init__(self):
        self._core_ready = False
        self._openai_ready = False

    def _ensure_core(self):
        """Парсер/история/config — без OpenAI (нужно для старта UI)."""
        if self._core_ready:
            return
        from backend.config import settings  # noqa: F401
        from backend.services.parser_service import parser_service
        from backend.services.history_service import history_service
        from backend.services.pdf_service import detect_file_kind, pdf_to_png_base64_list

        self.parser_service = parser_service
        self.history_service = history_service
        self.detect_file_kind = detect_file_kind
        self.pdf_to_png_base64_list = pdf_to_png_base64_list
        self._core_ready = True

    def _ensure_openai(self):
        """OpenAI только когда реально нужен анализ."""
        self._ensure_core()
        if self._openai_ready:
            return
        from backend.services.openai_service import openai_service

        self.openai_service = openai_service
        self._openai_ready = True

    def _ensure_imports(self):
        """Полная инициализация (для AI-методов)."""
        self._ensure_openai()

    def reconfigure(self) -> None:
        from backend.config import reload_settings

        reload_settings()
        self._ensure_core()
        if self._openai_ready:
            self.openai_service.reconfigure()
        # обновить путь истории
        from backend.config import settings
        from pathlib import Path as P

        self.history_service.history_file = P(settings.history_file)
        self.history_service._ensure_file_exists()

    def check_health(self) -> bool:
        """Для standalone: ядро загружено (ключ может отсутствовать)."""
        try:
            self._ensure_core()
            return True
        except Exception as e:
            logger.error(f"Init error: {e}")
            return False

    def has_api_key(self) -> bool:
        self._ensure_core()
        from backend.config import settings

        return bool(settings.openai_api_key and settings.openai_api_key.strip()
                    and not settings.openai_api_key.startswith("your_"))

    def get_settings_snapshot(self) -> Dict[str, Any]:
        self._ensure_core()
        from backend.config import settings, APP_DIR, _find_env_file

        found = _find_env_file(APP_DIR)
        return {
            "has_api_key": self.has_api_key(),
            "openai_base_url": settings.openai_base_url,
            "openai_model": settings.openai_model,
            "openai_vision_model": settings.openai_vision_model,
            "competitor_urls": list(settings.competitor_urls),
            "app_dir": str(APP_DIR),
            "env_path": str(found) if found else str(APP_DIR / ".env"),
            "env_found": found is not None,
        }

    def save_settings(
        self,
        openai_api_key: str = "",
        openai_model: str = "gpt-4o-mini",
        openai_vision_model: str = "gpt-4o-mini",
        openai_base_url: str = "https://api.openai.com/v1",
        competitor_urls: str = "",
    ) -> Dict[str, Any]:
        from backend.config import save_env_values, APP_DIR

        key = openai_api_key.strip()
        if not key and not self.has_api_key():
            return {
                "success": False,
                "error": "Укажите OPENAI_API_KEY или положите .env с ключом в папку приложения",
            }

        values = {
            "OPENAI_MODEL": openai_model.strip() or "gpt-4o-mini",
            "OPENAI_VISION_MODEL": openai_vision_model.strip() or "gpt-4o-mini",
            "OPENAI_BASE_URL": openai_base_url.strip() or "https://api.openai.com/v1",
        }
        # Пустое поле = не трогаем уже существующий ключ в .env
        if key:
            values["OPENAI_API_KEY"] = key

        if competitor_urls.strip():
            urls = [
                u.strip()
                for u in competitor_urls.replace("\n", ",").split(",")
                if u.strip()
            ]
            values["COMPETITOR_URLS"] = ",".join(urls)

        env_path = save_env_values(values, APP_DIR)
        self.reconfigure()
        return {"success": True, "env_path": str(env_path)}

    def analyze_text(self, text: str) -> Dict[str, Any]:
        self._ensure_imports()
        if not self.has_api_key():
            return {"success": False, "error": "Задайте OPENAI_API_KEY в Настройках"}
        try:
            analysis = _run(self.openai_service.analyze_text(text))
            self.history_service.add_entry(
                request_type="text",
                request_summary=text[:100] + ("..." if len(text) > 100 else ""),
                response_summary=analysis.summary or "Анализ текста",
            )
            return {"success": True, "analysis": analysis.model_dump()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def analyze_image(self, image_path: str) -> Dict[str, Any]:
        self._ensure_imports()
        if not self.has_api_key():
            return {"success": False, "error": "Задайте OPENAI_API_KEY в Настройках"}
        try:
            path = Path(image_path)
            content = path.read_bytes()
            kind = self.detect_file_kind(path.name, None)

            if kind == "pdf":
                pages = self.pdf_to_png_base64_list(content)
                images = [(b64, "image/png") for b64 in pages]
                label = f"PDF: {path.name} ({len(images)} стр.)"
            elif kind == "image":
                suffix = path.suffix.lower()
                mime = {
                    ".png": "image/png",
                    ".gif": "image/gif",
                    ".webp": "image/webp",
                }.get(suffix, "image/jpeg")
                b64 = base64.b64encode(content).decode("utf-8")
                images = [(b64, mime)]
                label = f"Изображение: {path.name}"
            else:
                return {
                    "success": False,
                    "error": "Поддерживаются JPEG, PNG, GIF, WEBP, PDF",
                }

            analysis = _run(self.openai_service.analyze_images(images))
            self.history_service.add_entry(
                request_type="image",
                request_summary=label,
                response_summary=(analysis.description or "")[:200] or "Анализ файла",
            )
            return {"success": True, "analysis": analysis.model_dump()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def parse_demo(self, url: str) -> Dict[str, Any]:
        self._ensure_imports()
        if not self.has_api_key():
            return {"success": False, "error": "Задайте OPENAI_API_KEY в Настройках"}
        try:
            if not url.startswith(("http://", "https://")):
                url = "https://" + url

            title, h1, first_paragraph, screenshot_bytes, error = _run(
                self.parser_service.parse_url(url)
            )
            if error:
                return {"success": False, "error": error}

            if screenshot_bytes:
                screenshot_b64 = self.parser_service.screenshot_to_base64(screenshot_bytes)
                analysis = _run(
                    self.openai_service.analyze_website_screenshot(
                        screenshot_base64=screenshot_b64,
                        url=url,
                        title=title,
                        h1=h1,
                        first_paragraph=first_paragraph,
                    )
                )
            else:
                analysis = _run(
                    self.openai_service.analyze_parsed_content(
                        title=title, h1=h1, paragraph=first_paragraph
                    )
                )

            self.history_service.add_entry(
                request_type="parse",
                request_summary=f"URL: {url}",
                response_summary=(analysis.summary or title or url)[:100],
            )
            return {
                "success": True,
                "data": {
                    "url": url,
                    "title": title,
                    "h1": h1,
                    "first_paragraph": first_paragraph,
                    "analysis": analysis.model_dump(),
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_competitors(self) -> Dict[str, Any]:
        self._ensure_core()
        urls = self.parser_service.get_competitor_urls()
        return {"competitor_urls": urls, "total": len(urls)}

    def collect_competitors(
        self, with_ai: bool = True, urls: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        self._ensure_imports()
        if with_ai and not self.has_api_key():
            return {"success": False, "error": "Задайте OPENAI_API_KEY в Настройках"}
        try:
            target_urls = urls or self.parser_service.get_competitor_urls()
            raw_items = _run(self.parser_service.collect_competitors(target_urls))
            items = []
            for raw in raw_items:
                item = {
                    "url": raw.get("url") or "",
                    "title": raw.get("title"),
                    "h1": raw.get("h1"),
                    "first_paragraph": raw.get("first_paragraph"),
                    "meta_description": raw.get("meta_description"),
                    "service_links": raw.get("service_links") or [],
                    "contacts": raw.get("contacts") or [],
                    "cta_texts": raw.get("cta_texts") or [],
                    "error": raw.get("error"),
                    "analysis": None,
                }
                if with_ai and not raw.get("error"):
                    try:
                        shot = raw.get("screenshot_bytes")
                        if shot:
                            b64 = self.parser_service.screenshot_to_base64(shot)
                            analysis = _run(
                                self.openai_service.analyze_website_screenshot(
                                    screenshot_base64=b64,
                                    url=item["url"],
                                    title=item["title"],
                                    h1=item["h1"],
                                    first_paragraph=item["first_paragraph"],
                                )
                            )
                        else:
                            analysis = _run(
                                self.openai_service.analyze_parsed_content(
                                    title=item["title"],
                                    h1=item["h1"],
                                    paragraph=item["first_paragraph"],
                                )
                            )
                        item["analysis"] = analysis.model_dump()
                        self.history_service.add_entry(
                            request_type="parse",
                            request_summary=f"Автосбор: {item['url']}",
                            response_summary=(analysis.summary or item["url"])[:100],
                        )
                    except Exception as ai_err:
                        item["error"] = f"Сбор OK, AI ошибка: {ai_err}"
                items.append(item)

            return {
                "success": True,
                "total": len(items),
                "items": items,
                "competitor_urls": target_urls,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_history(self) -> Dict[str, Any]:
        self._ensure_core()
        try:
            items = self.history_service.get_history()
            serialized = []
            for i in items:
                if hasattr(i, "model_dump"):
                    serialized.append(i.model_dump(mode="json"))
                elif isinstance(i, dict):
                    serialized.append(i)
            return {"items": serialized, "total": len(serialized)}
        except Exception as e:
            logger.error(f"get_history failed: {e}")
            return {"items": [], "total": 0, "error": str(e)}

    def clear_history(self) -> Dict[str, Any]:
        self._ensure_core()
        self.history_service.clear_history()
        return {"success": True, "message": "История очищена"}


api_client = LocalAPIClient()
