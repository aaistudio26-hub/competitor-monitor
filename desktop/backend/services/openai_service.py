"""
Сервис OpenAI API — анализ конкурентов на рынке юруслуг для бизнеса:
регистрация и ликвидация компаний, лицензирование, арбитраж.
https://platform.openai.com/docs/api-reference
"""
import json
import re
import time
import logging
from typing import Optional, Any, List, Tuple

from openai import OpenAI

from backend.config import settings
from backend.models.schemas import CompetitorAnalysis, ImageAnalysis

logger = logging.getLogger("competitor_monitor.openai")

MARKET_CONTEXT = """
Ты оцениваешь ТОЛЬКО конкурентов — юридические фирмы / компании юруслуг для бизнеса.
Фокус ниши (обязательно держать в центре анализа):
1) регистрация компаний (ООО, ИП и др.);
2) ликвидация компаний;
3) лицензирование;
4) арбитражные споры / арбитражный суд.

Целевая аудитория конкурентов — собственники, директора, предприниматели (B2B),
не массовые услуги для физлиц (разводы, ДТП и т.п.), если они не связаны с бизнесом.

Не оценивай и не предлагай: анимации, микроинтеракции, «вау-дизайн», геймификацию,
развлекательный UX — это не критерий конкуренции в данной нише.

Оценивай: покрытие услуг, экспертность и доверие, понятность оффера для бизнеса,
прозрачность цен/сроков, силу CTA (консультация, заявка), конкурентную угрозу.
"""


class OpenAIService:
    """Анализ конкурентов-юрфирм через OpenAI API"""

    def __init__(self):
        logger.info("=" * 50)
        logger.info("Инициализация OpenAI сервиса")
        logger.info(f"  Base URL: {settings.openai_base_url}")
        logger.info(f"  Модель текста: {settings.openai_model}")
        logger.info(f"  Модель vision: {settings.openai_vision_model}")
        logger.info(
            f"  API ключ: {'*' * 10}...{settings.openai_api_key[-4:] if settings.openai_api_key else 'НЕ ЗАДАН'}"
        )

        self.client = None
        self.model = settings.openai_model
        self.vision_model = settings.openai_vision_model
        key = (settings.openai_api_key or "").strip()
        if key and not key.startswith("your_"):
            try:
                self.client = OpenAI(
                    api_key=key,
                    base_url=settings.openai_base_url,
                )
                logger.info("OpenAI сервис инициализирован успешно")
            except Exception as e:
                self.client = None
                logger.warning(f"OpenAI клиент не создан: {e}")
        else:
            logger.warning("OPENAI_API_KEY не задан — укажите ключ в настройках")
        logger.info("=" * 50)

    def reconfigure(self) -> None:
        """Перечитать ключ/модели после изменения .env"""
        from backend.config import settings as current

        self.model = current.openai_model
        self.vision_model = current.openai_vision_model
        key = (current.openai_api_key or "").strip()
        if key and not key.startswith("your_"):
            try:
                self.client = OpenAI(
                    api_key=key,
                    base_url=current.openai_base_url,
                )
                logger.info("OpenAI сервис переконфигурирован")
                logger.info(f"  модель={self.model}")
            except Exception as e:
                self.client = None
                logger.warning(f"OpenAI клиент не создан: {e}")
        else:
            self.client = None
            logger.warning("OPENAI_API_KEY не задан")

    def _require_client(self):
        if self.client is None:
            raise RuntimeError(
                "OPENAI_API_KEY не задан. Откройте Настройки и укажите ключ."
            )

    @staticmethod
    def _clamp_score(value: Any, default: int = 0) -> int:
        try:
            score = int(round(float(value)))
        except (TypeError, ValueError):
            return default
        return max(0, min(10, score))

    def _parse_json_response(self, content: str) -> dict:
        logger.debug(f"Парсинг JSON ответа, длина: {len(content)} символов")

        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
        if json_match:
            content = json_match.group(1)

        json_match = re.search(r"\{[\s\S]*\}", content)
        if json_match:
            content = json_match.group(0)

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"Ошибка парсинга JSON: {e}")
            return {}

    def _build_competitor_analysis(self, data: dict) -> CompetitorAnalysis:
        return CompetitorAnalysis(
            strengths=data.get("strengths", []) or [],
            weaknesses=data.get("weaknesses", []) or [],
            unique_offers=data.get("unique_offers", []) or [],
            recommendations=data.get("recommendations", []) or [],
            summary=data.get("summary", "") or "",
            trust_score=self._clamp_score(data.get("trust_score"), 0),
            cta_score=self._clamp_score(data.get("cta_score"), 0),
            content_clarity_score=self._clamp_score(data.get("content_clarity_score"), 0),
            service_coverage_score=self._clamp_score(data.get("service_coverage_score"), 0),
            pricing_transparency_score=self._clamp_score(
                data.get("pricing_transparency_score"), 0
            ),
            competitive_threat=self._clamp_score(data.get("competitive_threat"), 0),
            service_focus=data.get("service_focus", []) or [],
            trust_signals=data.get("trust_signals", []) or [],
            content_gaps=data.get("content_gaps", []) or [],
            target_audience=data.get("target_audience", "") or "",
            positioning_notes=data.get("positioning_notes", "") or "",
        )

    def _build_image_analysis(self, data: dict) -> ImageAnalysis:
        return ImageAnalysis(
            description=data.get("description", "") or "",
            marketing_insights=data.get("marketing_insights", []) or [],
            trust_perception=data.get("trust_perception", "") or "",
            legal_branding_fit=self._clamp_score(data.get("legal_branding_fit"), 0),
            service_visibility_score=self._clamp_score(
                data.get("service_visibility_score"), 0
            ),
            offer_clarity_score=self._clamp_score(data.get("offer_clarity_score"), 0),
            recommendations=data.get("recommendations", []) or [],
        )

    async def analyze_text(self, text: str) -> CompetitorAnalysis:
        """Анализ текста конкурента — юрфирма для бизнеса"""
        logger.info("=" * 50)
        logger.info("АНАЛИЗ ТЕКСТА КОНКУРЕНТА (юруслуги для бизнеса)")
        logger.info(f"  Длина текста: {len(text)} символов")
        logger.info(f"  Модель: {self.model}")

        system_prompt = f"""Ты — эксперт по конкурентному анализу рынка юридических услуг для бизнеса.
{MARKET_CONTEXT}

Проанализируй текст конкурента и верни СТРОГО JSON (без текста вне JSON).

Формат:
{{
    "strengths": ["сильная сторона на рынке B2B-юруслуг", "..."],
    "weaknesses": ["слабая сторона", "..."],
    "unique_offers": ["УТП для бизнеса", "..."],
    "recommendations": ["как конкурировать с этой фирмой", "..."],
    "summary": "Краткое резюме: чем силён конкурент по регистрации/ликвидации/лицензиям/арбитражу и где слаб",
    "trust_score": 7,
    "cta_score": 6,
    "content_clarity_score": 7,
    "service_coverage_score": 6,
    "pricing_transparency_score": 5,
    "competitive_threat": 6,
    "service_focus": ["регистрация ООО", "ликвидация", "лицензирование", "арбитраж"],
    "trust_signals": ["кейсы", "опыт", "отзывы бизнеса", "экспертиза"],
    "content_gaps": ["чего не хватает предпринимателю в тексте"],
    "target_audience": "ИП / ООО / средний бизнес / ...",
    "positioning_notes": "Как фирма позиционирует себя среди юрфирм для бизнеса"
}}

Правила оценок (целые 0–10):
- trust_score — доверие и экспертность юридической фирмы
- cta_score — ясность призыва к действию (консультация, заявка, расчёт стоимости)
- content_clarity_score — понятность сложных юруслуг для предпринимателя
- service_coverage_score — насколько закрыты направления: регистрация, ликвидация, лицензирование, арбитраж
- pricing_transparency_score — прозрачность цен, сроков, состава услуг
- competitive_threat — насколько опасен конкурент на этом рынке

Важно:
- Массивы: 3–6 конкретных пунктов
- service_focus — только реально упомянутые направления
- Не пиши про анимации, дизайн ради дизайна, «трендовый UX»
- Пиши на русском, рекомендации — actionable"""

        start_time = time.time()
        try:
            self._require_client()
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (
                            "Проанализируй текст конкурента — юридической фирмы "
                            "(регистрация/ликвидация компаний, лицензирование, арбитраж):\n\n"
                            f"{text}"
                        ),
                    },
                ],
                temperature=0.7,
                max_tokens=2500,
            )

            elapsed = time.time() - start_time
            logger.info(f"  Ответ получен за {elapsed:.2f} сек")

            content = response.choices[0].message.content
            data = self._parse_json_response(content)
            result = self._build_competitor_analysis(data)

            logger.info(
                f"  threat={result.competitive_threat}/10, "
                f"coverage={result.service_coverage_score}/10"
            )
            logger.info("=" * 50)
            return result

        except Exception as e:
            logger.error(f"  Ошибка API: {e}")
            logger.error("=" * 50)
            raise

    async def analyze_image(
        self, image_base64: str, mime_type: str = "image/jpeg"
    ) -> ImageAnalysis:
        return await self.analyze_images([(image_base64, mime_type)])

    async def analyze_images(
        self, images: List[Tuple[str, str]]
    ) -> ImageAnalysis:
        """Анализ баннера / скриншота / PDF юрфирмы-конкурента"""
        if not images:
            raise ValueError("Нет изображений для анализа")

        logger.info("=" * 50)
        logger.info("АНАЛИЗ ИЗОБРАЖЕНИЯ / PDF (юруслуги для бизнеса)")
        logger.info(f"  Кадров: {len(images)}, модель: {self.vision_model}")

        multi_note = ""
        if len(images) > 1:
            multi_note = (
                f"\nПередано {len(images)} страниц (PDF или серия кадров). "
                "Оцени материал целиком с точки зрения конкуренции на рынке "
                "регистрации/ликвидации, лицензирования и арбитража."
            )

        system_prompt = f"""Ты — эксперт по маркетингу юридических услуг для бизнеса.
{MARKET_CONTEXT}
{multi_note}

Проанализируй визуальные материалы конкурента (баннер, скриншот сайта, PDF-буклет)
и верни СТРОГО JSON.

Формат:
{{
    "description": "Что показано: услуги, офферы, блоки для бизнеса",
    "marketing_insights": ["инсайт для рынка B2B-юруслуг", "..."],
    "trust_perception": "Как материал влияет на доверие предпринимателя к юрфирме",
    "legal_branding_fit": 7,
    "service_visibility_score": 6,
    "offer_clarity_score": 7,
    "recommendations": ["рекомендация по конкуренции", "..."]
}}

Правила оценок (0–10):
- legal_branding_fit — соответствие серьёзному B2B-юридическому бренду
- service_visibility_score — насколько заметны регистрация, ликвидация, лицензии, арбитраж
- offer_clarity_score — ясность коммерческого предложения для бизнеса

Важно:
- Массивы: 3–5 пунктов
- Не оценивай анимации и «креативный UX»
- Фокус: доверие, экспертность, читаемость юрофферов для бизнеса
- Пиши на русском"""

        user_content: list = [
            {
                "type": "text",
                "text": (
                    "Проанализируй материалы конкурента — юридической фирмы "
                    "(регистрация/ликвидация, лицензирование, арбитраж)"
                    + (f" ({len(images)} стр.):" if len(images) > 1 else ":")
                ),
            }
        ]
        for b64, mime in images:
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"},
                }
            )

        start_time = time.time()
        try:
            self._require_client()
            response = self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.7,
                max_tokens=2500,
            )

            elapsed = time.time() - start_time
            logger.info(f"  Ответ получен за {elapsed:.2f} сек")

            data = self._parse_json_response(response.choices[0].message.content)
            result = self._build_image_analysis(data)

            logger.info(
                f"  branding={result.legal_branding_fit}/10, "
                f"services={result.service_visibility_score}/10, "
                f"offer={result.offer_clarity_score}/10"
            )
            logger.info("=" * 50)
            return result

        except Exception as e:
            logger.error(f"  Ошибка Vision API: {e}")
            logger.error("=" * 50)
            raise

    async def analyze_parsed_content(
        self,
        title: Optional[str],
        h1: Optional[str],
        paragraph: Optional[str],
    ) -> CompetitorAnalysis:
        logger.info("Анализ распарсенного контента сайта юрфирмы")

        content_parts = []
        if title:
            content_parts.append(f"Заголовок страницы (title): {title}")
        if h1:
            content_parts.append(f"Главный заголовок (H1): {h1}")
        if paragraph:
            content_parts.append(f"Первый абзац: {paragraph}")

        combined_text = "\n\n".join(content_parts)
        if not combined_text.strip():
            return CompetitorAnalysis(
                summary="Не удалось извлечь контент для анализа"
            )
        return await self.analyze_text(combined_text)

    async def analyze_website_screenshot(
        self,
        screenshot_base64: str,
        url: str,
        title: Optional[str] = None,
        h1: Optional[str] = None,
        first_paragraph: Optional[str] = None,
    ) -> CompetitorAnalysis:
        """Комплексный анализ сайта юрфирмы-конкурента"""
        logger.info("=" * 50)
        logger.info("КОМПЛЕКСНЫЙ АНАЛИЗ САЙТА ЮРФИРМЫ")
        logger.info(f"  URL: {url}")

        context_parts = [f"URL сайта: {url}"]
        if title:
            context_parts.append(f"Title: {title}")
        if h1:
            context_parts.append(f"H1: {h1}")
        if first_paragraph:
            context_parts.append(f"Текст: {first_paragraph[:300]}")
        context = "\n".join(context_parts)

        system_prompt = f"""Ты — эксперт по конкурентному анализу сайтов юридических фирм для бизнеса.
{MARKET_CONTEXT}

Проанализируй скриншот сайта конкурента и верни СТРОГО JSON.

Формат:
{{
    "strengths": ["сильная сторона", "..."],
    "weaknesses": ["слабая сторона", "..."],
    "unique_offers": ["УТП для бизнеса", "..."],
    "recommendations": ["как конкурировать", "..."],
    "summary": "Резюме: позиция по регистрации/ликвидации, лицензиям, арбитражу; доверие; коммерческая сила",
    "trust_score": 7,
    "cta_score": 6,
    "content_clarity_score": 7,
    "service_coverage_score": 6,
    "pricing_transparency_score": 5,
    "competitive_threat": 6,
    "service_focus": ["регистрация компаний", "ликвидация", "лицензирование", "арбитраж"],
    "trust_signals": ["что на сайте усиливает доверие бизнеса"],
    "content_gaps": ["чего не хватает предпринимателю"],
    "target_audience": "Сегмент бизнеса",
    "positioning_notes": "Позиционирование среди юрфирм для бизнеса"
}}

Обязательно оцени:
- Покрытие услуг: регистрация / ликвидация / лицензирование / арбитраж (service_coverage_score)
- Доверие и экспертность (trust_score, trust_signals)
- Понятность оффера для предпринимателя (content_clarity_score)
- CTA: консультация, заявка, расчёт (cta_score)
- Прозрачность цен/сроков (pricing_transparency_score)
- Конкурентную угрозу (competitive_threat)

Не оценивай анимации и декоративный UX.
Массивы: 4–6 пунктов. Scores: целые 0–10. Язык: русский."""

        start_time = time.time()
        try:
            self._require_client()
            response = self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "Комплексный анализ сайта конкурента — "
                                    "юридической фирмы для бизнеса "
                                    "(регистрация/ликвидация, лицензии, арбитраж):\n\n"
                                    f"{context}"
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{screenshot_base64}"
                                },
                            },
                        ],
                    },
                ],
                temperature=0.7,
                max_tokens=3500,
            )

            elapsed = time.time() - start_time
            logger.info(f"  Ответ получен за {elapsed:.2f} сек")

            data = self._parse_json_response(response.choices[0].message.content)
            result = self._build_competitor_analysis(data)

            logger.info(
                f"  coverage={result.service_coverage_score}/10, "
                f"trust={result.trust_score}/10, "
                f"threat={result.competitive_threat}/10"
            )
            logger.info("=" * 50)
            return result

        except Exception as e:
            logger.error(f"  Ошибка Vision API: {e}")
            logger.error("=" * 50)
            raise


logger.info("Создание глобального экземпляра OpenAI сервиса...")
openai_service = OpenAIService()
