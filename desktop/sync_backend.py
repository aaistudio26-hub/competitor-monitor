"""
Синхронизация backend из корня проекта в desktop/backend.
Нужно, если правите код в корневом backend/ и хотите обновить portable desktop.
"""
import shutil
import sys
from pathlib import Path


def main() -> int:
    desktop = Path(__file__).resolve().parent
    src = desktop.parent / "backend"
    dst = desktop / "backend"

    if not src.is_dir():
        print(f"Source not found: {src}")
        print("If desktop is already standalone, backend/ should already be inside desktop.")
        return 1

    if dst.exists():
        shutil.rmtree(dst)

    def ignore(directory, names):
        return {n for n in names if n in ("__pycache__", ".pyc") or n.endswith(".pyc")}

    shutil.copytree(src, dst, ignore=ignore)
    print(f"Synced: {src} -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
