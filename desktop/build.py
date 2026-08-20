"""
Скрипт сборки автономного .exe для Windows
Папка desktop самодостаточна (свой backend/).
"""
import os
import sys
import subprocess
from pathlib import Path


def build_exe():
    print("=" * 60)
    print("DESKTOP BUILD (standalone): CompetitorMonitor.exe")
    print("=" * 60)

    desktop_dir = Path(__file__).parent
    backend_dir = desktop_dir / "backend"
    root_backend = desktop_dir.parent / "backend"

    # Перед сборкой подтянуть актуальный backend из корня (если есть)
    if root_backend.is_dir():
        print("  Syncing backend from project root...")
        sync_script = desktop_dir / "sync_backend.py"
        if sync_script.is_file():
            sync_result = subprocess.run(
                [sys.executable, str(sync_script)],
                cwd=str(desktop_dir),
            )
            if sync_result.returncode != 0:
                print("WARNING: sync_backend failed, using existing desktop/backend")

    if not (backend_dir / "config.py").is_file():
        print("ERROR: desktop/backend not found.")
        print("Run: python sync_backend.py")
        sys.exit(1)

    try:
        import PyInstaller  # noqa: F401
        print("  PyInstaller OK")
    except ImportError:
        print("  Install: pip install pyinstaller")
        sys.exit(1)

    app_name = "CompetitorMonitor"
    sep = os.pathsep

    add_data = [
        f"{backend_dir}{sep}backend",
        f"{desktop_dir / 'styles.py'}{sep}.",
        f"{desktop_dir / 'api_client.py'}{sep}.",
        f"{desktop_dir / 'paths.py'}{sep}.",
    ]

    hidden = [
        "PyQt6",
        "PyQt6.QtCore",
        "PyQt6.QtWidgets",
        "PyQt6.QtGui",
        "openai",
        "httpx",
        "httpcore",
        "pydantic",
        "pydantic_settings",
        "dotenv",
        # Selenium / Chrome — без этих модулей exe падает при парсинге
        "selenium",
        "selenium.webdriver",
        "selenium.webdriver.chrome",
        "selenium.webdriver.chrome.webdriver",
        "selenium.webdriver.chrome.service",
        "selenium.webdriver.chrome.options",
        "selenium.webdriver.chrome.remote_connection",
        "selenium.webdriver.common",
        "selenium.webdriver.common.by",
        "selenium.webdriver.common.options",
        "selenium.webdriver.common.service",
        "selenium.webdriver.common.desired_capabilities",
        "selenium.webdriver.remote",
        "selenium.webdriver.remote.webdriver",
        "selenium.webdriver.remote.remote_connection",
        "selenium.webdriver.support",
        "selenium.webdriver.support.ui",
        "selenium.webdriver.support.expected_conditions",
        "selenium.common",
        "selenium.common.exceptions",
        "webdriver_manager",
        "webdriver_manager.chrome",
        "webdriver_manager.core",
        "webdriver_manager.core.utils",
        "webdriver_manager.core.driver_cache",
        "webdriver_manager.core.os_manager",
        "webdriver_manager.drivers",
        "webdriver_manager.drivers.chrome",
        "certifi",
        "pymupdf",
        "PIL",
        "bs4",
        "lxml",
        "backend",
        "backend.config",
        "backend.models",
        "backend.models.schemas",
        "backend.services",
        "backend.services.openai_service",
        "backend.services.parser_service",
        "backend.services.history_service",
        "backend.services.pdf_service",
    ]

    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        app_name,
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--paths",
        str(desktop_dir),
        "--collect-all",
        "selenium",
        "--collect-all",
        "webdriver_manager",
        "--collect-submodules",
        "selenium",
    ]

    for item in add_data:
        args.extend(["--add-data", item])
    for mod in hidden:
        args.extend(["--hidden-import", mod])

    args.append(str(desktop_dir / "main.py"))

    print(f"\nBuilding: {app_name}.exe")
    print("-" * 60)
    result = subprocess.run(args, cwd=str(desktop_dir))

    if result.returncode != 0:
        print("\nERROR: build failed")
        sys.exit(1)

    exe_path = desktop_dir / "dist" / f"{app_name}.exe"
    if not exe_path.exists():
        print("\nERROR: .exe not found")
        sys.exit(1)

    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print("\n" + "=" * 60)
    print("BUILD SUCCESS (standalone)")
    print("=" * 60)
    print(f"\nFile: {exe_path}")
    print(f"Size: {size_mb:.1f} MB")
    print("\nPortable desktop folder can be moved anywhere.")
    print("Run CompetitorMonitor.exe and set OPENAI_API_KEY in Settings.")


if __name__ == "__main__":
    build_exe()
