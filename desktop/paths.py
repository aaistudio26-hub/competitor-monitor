"""
Пути приложения (dev / frozen .exe / перенесённая папка desktop)
"""
import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def get_desktop_dir() -> Path:
    """Папка desktop (где лежат main.py и локальный backend/)."""
    return Path(__file__).resolve().parent


def get_app_dir() -> Path:
    """
    Каталог данных (.env, history.json).
    - frozen: рядом с .exe
    - иначе: папка desktop (можно переносить отдельно от проекта)
    """
    env_override = os.getenv("APP_DIR")
    if env_override:
        return Path(env_override).resolve()

    if is_frozen():
        return Path(sys.executable).resolve().parent

    return get_desktop_dir()


def _backend_root_candidates() -> list:
    """Где искать пакет backend."""
    desktop = get_desktop_dir()
    candidates = []

    if is_frozen() and hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS))

    # 1) Самодостаточная папка desktop/backend
    candidates.append(desktop)
    # 2) Fallback: корень монорепозитория (если desktop ещё внутри проекта)
    candidates.append(desktop.parent)

    return candidates


def find_backend_root() -> Path:
    """Корень, в котором есть пакет backend/."""
    for root in _backend_root_candidates():
        cfg = root / "backend" / "config.py"
        if cfg.is_file():
            return root
    raise RuntimeError(
        "Не найден пакет backend.\n"
        "В папке desktop должна быть подпапка backend/ "
        "(скопируйте её вместе с desktop или выполните: python sync_backend.py)."
    )


def ensure_project_on_path() -> Path:
    """Добавить корень с backend в sys.path."""
    root = find_backend_root()
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root


ENV_FILENAMES = (".env", "env", ".env.txt", "env.txt")


def get_env_path() -> Path:
    """Путь для записи настроек (всегда .env в каталоге данных приложения)."""
    return get_app_dir() / ".env"


def env_search_dirs(app_dir: Path | None = None) -> list:
    """
    Где искать env:
    1) каталог данных (рядом с exe / папка desktop при запуске из исходников)
    2) папка desktop — если путь/exe в desktop/dist/
    """
    dirs = []
    primary = Path(app_dir) if app_dir else get_app_dir()
    primary = primary.resolve()
    dirs.append(primary)

    # desktop/dist/ → также desktop/ (и для python, и для exe)
    if primary.name.lower() == "dist":
        dirs.append(primary.parent.resolve())

    if is_frozen():
        exe_dir = Path(sys.executable).resolve().parent
        dirs.append(exe_dir)
        if exe_dir.name.lower() == "dist":
            dirs.append(exe_dir.parent.resolve())
    else:
        desktop = get_desktop_dir().resolve()
        dirs.append(desktop)

    unique = []
    seen = set()
    for d in dirs:
        key = str(d).lower()
        if key in seen or not d.is_dir():
            continue
        seen.add(key)
        unique.append(d)
    return unique


def find_env_file(app_dir: Path | None = None) -> Path | None:
    """
    Найти файл окружения в dist (рядом с exe) или в папке desktop.
    Windows часто создаёт env / env.txt вместо .env.
    """
    for directory in env_search_dirs(app_dir):
        for name in ENV_FILENAMES:
            path = directory / name
            if path.is_file():
                return path
    return None


def get_history_path() -> Path:
    return get_app_dir() / "history.json"
