"""
Сервис для автоматического сбора данных с сайтов конкурентов через Selenium Chrome.
URL конкурентов задаются в backend/config.py (settings.competitor_urls).
"""
import base64
import asyncio
import re
import time
import logging
from typing import Optional, Tuple, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

from backend.config import settings

logger = logging.getLogger("competitor_monitor.parser")

# Ключевые слова услуг B2B-юрфирм (для отбора ссылок/блоков)
SERVICE_KEYWORDS = (
    "регистрац", "ликвидац", "лиценз", "арбитраж", "ооо", "ип",
    "юрлиц", "компани", "банкрот", "реорганиз", "устав", "договор",
    "консультац", "юридическ", "бизнес",
)


class ParserService:
    """Автосбор контента сайтов конкурентов через Selenium"""

    def __init__(self):
        logger.info("=" * 50)
        logger.info("Инициализация Parser сервиса (Selenium)")
        logger.info(f"  Timeout: {settings.parser_timeout} сек")
        logger.info(f"  Headless: {settings.parser_headless}")
        logger.info(f"  User-Agent: {settings.parser_user_agent[:50]}...")
        logger.info(f"  Конкурентов в config: {len(settings.competitor_urls)}")
        for i, url in enumerate(settings.competitor_urls, 1):
            logger.info(f"    {i}. {url}")

        self.timeout = settings.parser_timeout
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._driver_path: Optional[str] = None

        logger.info("Parser сервис инициализирован OK")
        logger.info("=" * 50)

    def _get_driver_path(self) -> str:
        """Кэш пути к ChromeDriver"""
        if not self._driver_path:
            logger.info("  Загрузка / проверка ChromeDriver...")
            self._driver_path = ChromeDriverManager().install()
        return self._driver_path

    def _create_driver(self) -> webdriver.Chrome:
        """Создать Chrome с антидетект-опциями для автосбора"""
        logger.info("  Создание Chrome драйвера...")
        start_time = time.time()

        options = Options()
        if settings.parser_headless:
            options.add_argument("--headless=new")

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument(
            f"--window-size={settings.parser_window_width},{settings.parser_window_height}"
        )
        options.add_argument(f"--user-agent={settings.parser_user_agent}")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--lang=ru-RU,ru")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--ignore-certificate-errors")
        options.page_load_strategy = "normal"

        options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_experimental_option(
            "prefs",
            {
                "intl.accept_languages": "ru-RU,ru",
                "profile.default_content_setting_values.notifications": 2,
            },
        )

        service = Service(self._get_driver_path())
        driver = webdriver.Chrome(service=service, options=options)

        # Скрыть navigator.webdriver
        try:
            driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {
                    "source": """
                        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                        window.chrome = { runtime: {} };
                    """
                },
            )
        except Exception as e:
            logger.debug(f"  CDP anti-detect не применён: {e}")

        driver.set_page_load_timeout(self.timeout)
        driver.set_script_timeout(self.timeout)
        driver.implicitly_wait(0)

        elapsed = time.time() - start_time
        logger.info(f"  Chrome драйвер создан за {elapsed:.2f} сек")
        return driver

    def _normalize_url(self, url: str) -> str:
        url = (url or "").strip()
        if not url:
            return url
        if not url.startswith(("http://", "https://")):
            return "https://" + url
        return url

    def _dismiss_overlays(self, driver: webdriver.Chrome) -> None:
        """Попытка закрыть cookie/баннеры, мешающие сбору"""
        selectors = [
            "button[id*='cookie' i]",
            "button[class*='cookie' i]",
            "a[id*='cookie' i]",
            "[class*='cookie'] button",
            "[id*='consent'] button",
            "button[class*='accept' i]",
            "button[class*='agree' i]",
            ".fc-cta-consent",
            "#onetrust-accept-btn-handler",
        ]
        for css in selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, css)
                for el in elements[:2]:
                    if el.is_displayed():
                        el.click()
                        time.sleep(0.3)
                        logger.debug(f"  Закрыт overlay: {css}")
                        return
            except Exception:
                continue

        # JS-fallback: спрятать типичные cookie-бары
        try:
            driver.execute_script(
                """
                document.querySelectorAll(
                  '[class*="cookie"],[id*="cookie"],[class*="consent"],[id*="consent"]'
                ).forEach(el => { el.style.display = 'none'; });
                """
            )
        except Exception:
            pass

    def _safe_text(self, el) -> str:
        try:
            return (el.text or "").strip()
        except Exception:
            return ""

    def _extract_meta_description(self, driver: webdriver.Chrome) -> Optional[str]:
        for selector in (
            "meta[name='description']",
            "meta[property='og:description']",
        ):
            try:
                el = driver.find_element(By.CSS_SELECTOR, selector)
                content = (el.get_attribute("content") or "").strip()
                if content:
                    return content[:500]
            except Exception:
                continue
        return None

    def _extract_h1(self, driver: webdriver.Chrome) -> Optional[str]:
        try:
            h1_element = driver.find_element(By.TAG_NAME, "h1")
            text = self._safe_text(h1_element)
            return text or None
        except Exception:
            return None

    def _extract_first_paragraph(self, driver: webdriver.Chrome) -> Optional[str]:
        try:
            paragraphs = driver.find_elements(By.TAG_NAME, "p")
            for p in paragraphs:
                text = self._safe_text(p)
                if len(text) > 50:
                    return text[:500]
        except Exception:
            pass
        return None

    def _extract_service_links(self, driver: webdriver.Chrome, base_url: str) -> List[str]:
        """Ссылки на услуги: регистрация, ликвидация, лицензии, арбитраж"""
        found: List[str] = []
        seen = set()
        try:
            anchors = driver.find_elements(By.CSS_SELECTOR, "a[href]")
            for a in anchors:
                try:
                    href = (a.get_attribute("href") or "").strip()
                    label = self._safe_text(a).lower()
                    href_l = href.lower()
                    if not href or href.startswith(("mailto:", "tel:", "javascript:")):
                        continue
                    blob = f"{label} {href_l}"
                    if not any(k in blob for k in SERVICE_KEYWORDS):
                        continue
                    absolute = urljoin(base_url, href)
                    # Только тот же домен
                    if urlparse(absolute).netloc != urlparse(base_url).netloc:
                        continue
                    key = absolute.rstrip("/")
                    if key in seen:
                        continue
                    seen.add(key)
                    display = self._safe_text(a) or absolute
                    found.append(f"{display} -> {absolute}")
                    if len(found) >= 12:
                        break
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"  Ошибка сбора ссылок услуг: {e}")
        return found

    def _extract_contacts(self, driver: webdriver.Chrome) -> List[str]:
        contacts: List[str] = []
        try:
            page_text = driver.find_element(By.TAG_NAME, "body").text or ""
        except Exception:
            page_text = ""

        phones = re.findall(
            r"(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}",
            page_text,
        )
        for phone in phones:
            normalized = re.sub(r"\s+", " ", phone).strip()
            if normalized not in contacts:
                contacts.append(normalized)
            if len(contacts) >= 5:
                break

        try:
            for a in driver.find_elements(By.CSS_SELECTOR, "a[href^='mailto:']"):
                mail = (a.get_attribute("href") or "").replace("mailto:", "").split("?")[0]
                if mail and mail not in contacts:
                    contacts.append(mail)
                if len(contacts) >= 8:
                    break
        except Exception:
            pass

        return contacts

    def _extract_cta_texts(self, driver: webdriver.Chrome) -> List[str]:
        ctas: List[str] = []
        selectors = (
            "a.btn", "button.btn", ".btn", "[class*='button']",
            "a[class*='cta']", "button",
        )
        keywords = ("консульт", "заявк", "звонок", "расчёт", "заказ", "связ", "оставить")
        try:
            for css in selectors:
                for el in driver.find_elements(By.CSS_SELECTOR, css)[:30]:
                    text = self._safe_text(el)
                    if 2 < len(text) < 80 and any(k in text.lower() for k in keywords):
                        if text not in ctas:
                            ctas.append(text)
                    if len(ctas) >= 8:
                        return ctas
        except Exception:
            pass
        return ctas

    def _parse_with_driver(self, driver: webdriver.Chrome, url: str) -> Dict[str, Any]:
        """Сбор данных с одной страницы уже созданным драйвером"""
        url = self._normalize_url(url)
        result: Dict[str, Any] = {
            "url": url,
            "title": None,
            "h1": None,
            "first_paragraph": None,
            "meta_description": None,
            "service_links": [],
            "contacts": [],
            "cta_texts": [],
            "screenshot_bytes": None,
            "error": None,
        }

        logger.info("=" * 50)
        logger.info(f"ПАРСИНГ САЙТА: {url}")
        total_start = time.time()

        try:
            page_start = time.time()
            driver.get(url)
            logger.info(f"  Страница загружена за {time.time() - page_start:.2f} сек")

            WebDriverWait(driver, self.timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            time.sleep(settings.parser_wait_dynamic)
            self._dismiss_overlays(driver)

            result["title"] = driver.title or None
            result["h1"] = self._extract_h1(driver)
            result["first_paragraph"] = self._extract_first_paragraph(driver)
            result["meta_description"] = self._extract_meta_description(driver)
            result["service_links"] = self._extract_service_links(driver, url)
            result["contacts"] = self._extract_contacts(driver)
            result["cta_texts"] = self._extract_cta_texts(driver)

            logger.info(f"  Title: {(result['title'] or 'N/A')[:60]}")
            logger.info(f"  H1: {(result['h1'] or 'N/A')[:60]}")
            logger.info(f"  Услуг-ссылок: {len(result['service_links'])}")
            logger.info(f"  Контактов: {len(result['contacts'])}")
            logger.info(f"  CTA: {len(result['cta_texts'])}")

            screenshot_bytes = driver.get_screenshot_as_png()
            result["screenshot_bytes"] = screenshot_bytes
            logger.info(f"  Скриншот: {len(screenshot_bytes) / 1024:.1f} KB")
            logger.info(f"  ПАРСИНГ ЗАВЕРШЁН за {time.time() - total_start:.2f} сек")
            logger.info("=" * 50)
            return result

        except TimeoutException:
            result["error"] = "Превышено время ожидания загрузки страницы"
            logger.error(f"  TIMEOUT: {url}")
            return result
        except WebDriverException as e:
            error_msg = str(e)
            logger.error(f"  WebDriver ошибка: {error_msg[:200]}")
            if "net::ERR_NAME_NOT_RESOLVED" in error_msg:
                result["error"] = "Не удалось найти сайт по указанному адресу"
            elif "net::ERR_CONNECTION_REFUSED" in error_msg:
                result["error"] = "Соединение отклонено сервером"
            elif "net::ERR_CONNECTION_TIMED_OUT" in error_msg:
                result["error"] = "Превышено время ожидания соединения"
            else:
                result["error"] = f"Ошибка браузера: {error_msg[:200]}"
            return result
        except Exception as e:
            result["error"] = f"Ошибка при загрузке страницы: {str(e)[:200]}"
            logger.error(f"  Неизвестная ошибка: {e}")
            return result

    def _parse_sync(self, url: str) -> Tuple[
        Optional[str], Optional[str], Optional[str], Optional[bytes], Optional[str]
    ]:
        """Синхронный парсинг одного URL (совместимость с /parse_demo)"""
        driver = None
        try:
            driver = self._create_driver()
            data = self._parse_with_driver(driver, url)
            return (
                data.get("title"),
                data.get("h1"),
                data.get("first_paragraph"),
                data.get("screenshot_bytes"),
                data.get("error"),
            )
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception as e:
                    logger.warning(f"  Ошибка при закрытии драйвера: {e}")

    def _collect_competitors_sync(
        self, urls: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Автоматический сбор данных со всех сайтов из config (или переданного списка).
        Один Chrome-драйвер на весь пакет.
        """
        targets = urls if urls is not None else list(settings.competitor_urls)
        targets = [self._normalize_url(u) for u in targets if u and u.strip()]

        logger.info("=" * 60)
        logger.info(f"АВТОСБОР КОНКУРЕНТОВ: {len(targets)} сайтов")
        for i, u in enumerate(targets, 1):
            logger.info(f"  {i}. {u}")
        logger.info("=" * 60)

        if not targets:
            return [{
                "url": "",
                "title": None,
                "h1": None,
                "first_paragraph": None,
                "meta_description": None,
                "service_links": [],
                "contacts": [],
                "cta_texts": [],
                "screenshot_bytes": None,
                "error": "Список COMPETITOR_URLS пуст — укажите URL в config.py или .env",
            }]

        results: List[Dict[str, Any]] = []
        driver = None
        try:
            driver = self._create_driver()
            for index, url in enumerate(targets):
                data = self._parse_with_driver(driver, url)
                # Не тащим bytes в лог/лишние копии — оставляем в результате для API
                results.append(data)
                if index < len(targets) - 1:
                    time.sleep(settings.parser_delay_between)
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception as e:
                    logger.warning(f"  Ошибка закрытия драйвера: {e}")

        ok = sum(1 for r in results if not r.get("error"))
        logger.info(f"АВТОСБОР ЗАВЕРШЁН: успешно {ok}/{len(results)}")
        return results

    async def parse_url(
        self, url: str
    ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[bytes], Optional[str]]:
        """Асинхронный парсинг одного URL через Chrome"""
        url = self._normalize_url(url)
        logger.info(f"Запуск асинхронного парсинга: {url}")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self._parse_sync, url)

    async def collect_competitors(
        self, urls: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Асинхронный автосбор сайтов конкурентов.
        По умолчанию берёт URL из settings.competitor_urls (config.py / .env).
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._executor,
            self._collect_competitors_sync,
            urls,
        )

    def get_competitor_urls(self) -> List[str]:
        """Список URL из конфигурации"""
        return list(settings.competitor_urls)

    def screenshot_to_base64(self, screenshot_bytes: bytes) -> str:
        """Конвертировать скриншот в base64"""
        return base64.b64encode(screenshot_bytes).decode("utf-8")

    async def close(self):
        """Закрыть executor"""
        logger.info("Закрытие Parser сервиса...")
        self._executor.shutdown(wait=False)
        logger.info("Parser сервис закрыт OK")


logger.info("Создание глобального экземпляра Parser сервиса...")
parser_service = ParserService()
