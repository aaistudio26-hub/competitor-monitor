"""
Pydantic схемы для API
Анализ конкурентов — юрфирмы для бизнеса
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# === Запросы ===

class TextAnalysisRequest(BaseModel):
    """Запрос на анализ текста"""
    text: str = Field(..., min_length=10, description="Текст для анализа")


class ParseDemoRequest(BaseModel):
    """Запрос на парсинг URL"""
    url: str = Field(..., description="URL для парсинга")


class CollectCompetitorsRequest(BaseModel):
    """Опционально: свой список URL вместо config"""
    urls: Optional[List[str]] = Field(
        None,
        description="Если не задано — берутся COMPETITOR_URLS из config.py",
    )
    with_ai: bool = Field(
        True,
        description="Запускать AI-анализ по каждому собранному сайту",
    )


# === Ответы ===

class CompetitorAnalysis(BaseModel):
    """Анализ конкурента — юрфирма: регистрация/ликвидация, лицензии, арбитраж"""
    strengths: List[str] = Field(default_factory=list, description="Сильные стороны на рынке B2B-юруслуг")
    weaknesses: List[str] = Field(default_factory=list, description="Слабые стороны")
    unique_offers: List[str] = Field(default_factory=list, description="УТП для бизнеса")
    recommendations: List[str] = Field(default_factory=list, description="Как конкурировать с этой фирмой")
    summary: str = Field("", description="Резюме конкурентной позиции")

    # Оценки 0–10 под нишу
    trust_score: int = Field(0, ge=0, le=10, description="Доверие и экспертность юрфирмы")
    cta_score: int = Field(0, ge=0, le=10, description="Сила CTA: консультация / заявка / расчёт")
    content_clarity_score: int = Field(0, ge=0, le=10, description="Понятность юруслуг для предпринимателя")
    service_coverage_score: int = Field(
        0, ge=0, le=10,
        description="Покрытие: регистрация, ликвидация, лицензирование, арбитраж",
    )
    pricing_transparency_score: int = Field(
        0, ge=0, le=10,
        description="Прозрачность цен и условий для бизнеса",
    )
    competitive_threat: int = Field(0, ge=0, le=10, description="Уровень конкурентной угрозы")

    service_focus: List[str] = Field(
        default_factory=list,
        description="Явные направления: регистрация, ликвидация, лицензирование, арбитраж и др.",
    )
    trust_signals: List[str] = Field(
        default_factory=list,
        description="Сигналы доверия: кейсы, опыт, отзывы, команда, членства",
    )
    content_gaps: List[str] = Field(
        default_factory=list,
        description="Чего не хватает для B2B-клиента (регистрация/лицензии/арбитраж)",
    )
    target_audience: str = Field("", description="ЦА: ИП, ООО, средний бизнес и т.п.")
    positioning_notes: str = Field(
        "",
        description="Как фирма позиционирует себя на рынке юруслуг для бизнеса",
    )


class ImageAnalysis(BaseModel):
    """Анализ баннера / скриншота / PDF юрфирмы-конкурента"""
    description: str = Field("", description="Что изображено / какие страницы")
    marketing_insights: List[str] = Field(
        default_factory=list,
        description="Маркетинговые выводы для B2B-юруслуг",
    )
    trust_perception: str = Field(
        "",
        description="Как материал влияет на доверие предпринимателя",
    )
    legal_branding_fit: int = Field(
        0, ge=0, le=10,
        description="Соответствие серьёзному B2B-юридическому бренду",
    )
    service_visibility_score: int = Field(
        0, ge=0, le=10,
        description="Насколько заметны услуги: регистрация, ликвидация, лицензии, арбитраж",
    )
    offer_clarity_score: int = Field(
        0, ge=0, le=10,
        description="Ясность коммерческого оффера для бизнеса",
    )
    recommendations: List[str] = Field(default_factory=list, description="Рекомендации")


class CompetitorSiteData(BaseModel):
    """Сырые данные Selenium с сайта конкурента"""
    url: str
    title: Optional[str] = None
    h1: Optional[str] = None
    first_paragraph: Optional[str] = None
    meta_description: Optional[str] = None
    service_links: List[str] = Field(default_factory=list)
    contacts: List[str] = Field(default_factory=list)
    cta_texts: List[str] = Field(default_factory=list)
    analysis: Optional[CompetitorAnalysis] = None
    error: Optional[str] = None


class CollectCompetitorsResponse(BaseModel):
    """Ответ пакетного автосбора"""
    success: bool
    total: int = 0
    items: List[CompetitorSiteData] = Field(default_factory=list)
    competitor_urls: List[str] = Field(default_factory=list)
    error: Optional[str] = None


class ParsedContent(BaseModel):
    """Результат парсинга страницы"""
    url: str
    title: Optional[str] = None
    h1: Optional[str] = None
    first_paragraph: Optional[str] = None
    analysis: Optional[CompetitorAnalysis] = None
    error: Optional[str] = None


class TextAnalysisResponse(BaseModel):
    """Ответ на анализ текста"""
    success: bool
    analysis: Optional[CompetitorAnalysis] = None
    error: Optional[str] = None


class ImageAnalysisResponse(BaseModel):
    """Ответ на анализ изображения"""
    success: bool
    analysis: Optional[ImageAnalysis] = None
    error: Optional[str] = None


class ParseDemoResponse(BaseModel):
    """Ответ на парсинг"""
    success: bool
    data: Optional[ParsedContent] = None
    error: Optional[str] = None


# === История ===

class HistoryItem(BaseModel):
    """Элемент истории"""
    id: str
    timestamp: datetime
    request_type: str  # "text", "image", "parse"
    request_summary: str
    response_summary: str


class HistoryResponse(BaseModel):
    """Ответ со списком истории"""
    items: List[HistoryItem]
    total: int
