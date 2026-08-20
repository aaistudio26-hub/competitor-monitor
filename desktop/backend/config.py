"""
Конфигурация приложения
"""
import os
import logging
import sys
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from dotenv import load_dotenv


def _default_app_dir() -> Path:
    if os.getenv("APP_DIR"):
        return Path(os.getenv("APP_DIR")).resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # backend/config.py -> project root
    return Path(__file__).resolve().parent.parent


APP_DIR = _default_app_dir()


def _find_env_file(directory: Optional[Path] = None) -> Optional[Path]:
    """
    Ищем .env / env / env.txt в каталоге приложения.
    Для desktop/exe дополнительно — в родительской папке (desktop/, если exe в dist/).
    """
    names = (".env", "env", ".env.txt", "env.txt")
    primary = Path(directory) if directory else APP_DIR
    primary = primary.resolve()
    candidates = [primary]

    # desktop/dist/*.exe → также desktop/; не поднимаемся из корня web-проекта
    if getattr(sys, "frozen", False) or primary.name.lower() == "dist":
        parent = primary.parent
        if parent.is_dir():
            candidates.append(parent)
        if getattr(sys, "frozen", False):
            exe_dir = Path(sys.executable).resolve().parent
            candidates.append(exe_dir)
            candidates.append(exe_dir.parent)

    seen = set()
    for folder in candidates:
        key = str(folder).lower()
        if key in seen or not folder.is_dir():
            continue
        seen.add(key)
        for name in names:
            path = folder / name
            if path.is_file():
                return path
    return None


def _load_env_files(app_dir: Optional[Path] = None) -> Path:
    """Загрузить env из dist (рядом с exe) или из папки desktop."""
    global APP_DIR
    APP_DIR = Path(app_dir) if app_dir else _default_app_dir()
    env_path = _find_env_file(APP_DIR)
    if env_path is not None:
        load_dotenv(env_path, override=True)
    else:
        # Нет локального env — не берём ключ из чужого cwd / системного окружения
        os.environ.pop("OPENAI_API_KEY", None)
    os.environ.setdefault("APP_DIR", str(APP_DIR))
    return APP_DIR


_load_env_files()


def setup_logging():
    """Настройка логирования для всего приложения"""
    log_format = "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            datefmt=date_format,
            handlers=[logging.StreamHandler(sys.stdout)],
        )

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("selenium").setLevel(logging.WARNING)
    logging.getLogger("WDM").setLevel(logging.WARNING)

    return logging.getLogger("competitor_monitor")


logger = setup_logging()

DEFAULT_COMPETITOR_URLS = [
    "https://gestion.ru/",
    "https://www.regberry.ru/",
    "https://www.e-kontur.ru/",
]


class Settings(BaseSettings):
    """Настройки приложения"""

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    openai_vision_model: str = "gpt-4o-mini"

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    history_file: str = "history.json"
    max_history_items: int = 10

    parser_timeout: int = 25
    parser_wait_dynamic: float = 2.5
    parser_headless: bool = True
    parser_window_width: int = 1920
    parser_window_height: int = 1080
    parser_user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
    parser_delay_between: float = 1.5

    competitor_urls: List[str] = Field(default_factory=lambda: list(DEFAULT_COMPETITOR_URLS))

    @field_validator("competitor_urls", mode="before")
    @classmethod
    def parse_competitor_urls(cls, value):
        if value is None or value == "":
            return list(DEFAULT_COMPETITOR_URLS)
        if isinstance(value, str):
            urls = [u.strip() for u in value.split(",") if u.strip()]
            return urls or list(DEFAULT_COMPETITOR_URLS)
        if isinstance(value, list):
            return value
        return list(DEFAULT_COMPETITOR_URLS)

    @property
    def history_path(self) -> Path:
        path = Path(self.history_file)
        if path.is_absolute():
            return path
        return APP_DIR / path

    class Config:
        # .env читаем только через _load_env_files(APP_DIR/.env), не из cwd
        extra = "ignore"


settings = Settings()
# Абсолютный путь истории в каталоге приложения
if not Path(settings.history_file).is_absolute():
    settings.history_file = str(settings.history_path)


def reload_settings(app_dir: Optional[Path] = None) -> Settings:
    """Перечитать .env и обновить глобальный settings."""
    global settings
    _load_env_files(app_dir)
    settings = Settings()
    if not Path(settings.history_file).is_absolute():
        settings.history_file = str(APP_DIR / settings.history_file)
    return settings


def save_env_values(values: dict, app_dir: Optional[Path] = None) -> Path:
    """
    Записать/обновить ключи в .env рядом с приложением.
    values: { "OPENAI_API_KEY": "...", ... }
    """
    directory = Path(app_dir) if app_dir else APP_DIR
    directory.mkdir(parents=True, exist_ok=True)
    env_path = directory / ".env"

    existing = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, val = stripped.split("=", 1)
            existing[key.strip()] = val.strip()

    for key, val in values.items():
        if val is None:
            continue
        existing[str(key)] = str(val)

    lines = [f"{k}={v}" for k, v in existing.items()]
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    reload_settings(directory)
    return env_path
