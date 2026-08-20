"""
Конвертация PDF в изображения для Vision API
"""
import base64
import io
import logging
from typing import List, Optional

import pymupdf
from PIL import Image

logger = logging.getLogger("competitor_monitor.pdf")

# Лимит страниц, чтобы не раздувать запрос к Vision API
MAX_PDF_PAGES = 5
# Масштаб рендера (~144 DPI при zoom=2.0)
PDF_RENDER_ZOOM = 2.0


def pdf_to_png_base64_list(
    pdf_bytes: bytes,
    max_pages: int = MAX_PDF_PAGES,
    zoom: float = PDF_RENDER_ZOOM,
) -> List[str]:
    """
    Рендерит страницы PDF в PNG (base64).
    Возвращает список base64-строк без data-URL префикса.
    """
    if not pdf_bytes:
        raise ValueError("PDF файл пустой")

    logger.info(f"Конвертация PDF: {len(pdf_bytes) / 1024:.1f} KB")

    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        raise ValueError(f"Не удалось открыть PDF: {e}") from e

    if doc.page_count == 0:
        doc.close()
        raise ValueError("PDF не содержит страниц")

    pages_to_render = min(doc.page_count, max_pages)
    logger.info(f"  Страниц в PDF: {doc.page_count}, рендерим: {pages_to_render}")

    images: List[str] = []
    matrix = pymupdf.Matrix(zoom, zoom)

    try:
        for page_index in range(pages_to_render):
            page = doc.load_page(page_index)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            png_bytes = pix.tobytes("png")

            # Нормализуем через Pillow (гарантия валидного PNG)
            with Image.open(io.BytesIO(png_bytes)) as img:
                buf = io.BytesIO()
                img.convert("RGB").save(buf, format="PNG", optimize=True)
                png_bytes = buf.getvalue()

            b64 = base64.b64encode(png_bytes).decode("utf-8")
            images.append(b64)
            logger.info(
                f"  Страница {page_index + 1}/{pages_to_render}: "
                f"{len(png_bytes) / 1024:.1f} KB PNG"
            )
    finally:
        doc.close()

    if not images:
        raise ValueError("Не удалось извлечь изображения из PDF")

    return images


def detect_file_kind(filename: Optional[str], content_type: Optional[str]) -> str:
    """
    Определить тип файла: 'pdf' | 'image' | 'unknown'
    """
    name = (filename or "").lower()
    ctype = (content_type or "").lower()

    if ctype == "application/pdf" or name.endswith(".pdf"):
        return "pdf"

    image_types = {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/gif",
        "image/webp",
    }
    if ctype in image_types or name.endswith(
        (".jpg", ".jpeg", ".png", ".gif", ".webp")
    ):
        return "image"

    return "unknown"
