"""
Мониторинг конкурентов - автономное Desktop приложение на PyQt6
"""
import sys
import os
from pathlib import Path
from datetime import datetime

# Bootstrap: пути и .env до импорта backend через api_client
from paths import ensure_project_on_path, get_app_dir, get_env_path, find_env_file

ensure_project_on_path()
os.environ["APP_DIR"] = str(get_app_dir())

# Явно подхватить env рядом с exe / desktop (до импорта backend)
_env_file = find_env_file()
if _env_file is not None:
    try:
        from dotenv import load_dotenv

        load_dotenv(_env_file, override=True)
    except Exception:
        pass

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QLineEdit, QFrame, QScrollArea,
    QFileDialog, QStackedWidget, QMessageBox, QProgressBar, QDialog,
    QFormLayout, QDialogButtonBox,
)
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap, QDragEnterEvent, QDropEvent

from styles import DARK_THEME
from api_client import api_client


class SettingsDialog(QDialog):
    """Настройки OpenAI и конкурентов (.env рядом с приложением)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setMinimumWidth(520)
        self.setStyleSheet(DARK_THEME)

        layout = QVBoxLayout(self)

        info = QLabel(
            f"Папка данных:\n{get_app_dir()}\n\n"
            "Файл ключа ищется здесь:\n"
            "• рядом с .exe (папка dist)\n"
            "• или в папке desktop\n"
            f"Имена: .env / env / env.txt\n\n"
            f"Сейчас: {find_env_file() or 'не найден'}\n\n"
            "Ключ в поле ниже не подставляется — введите новый "
            "или положите файл env в dist/desktop."
        )
        info.setWordWrap(True)
        info.setObjectName("cardDescription")
        layout.addWidget(info)

        form = QFormLayout()
        snap = api_client.get_settings_snapshot()
        self._had_api_key = bool(snap.get("has_api_key"))

        # Поле всегда пустое — ключ не показываем и не подставляем
        self.key_input = QLineEdit("")
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        if self._had_api_key:
            self.key_input.setPlaceholderText(
                "ключ уже есть в .env — оставьте пустым, чтобы не менять"
            )
        else:
            self.key_input.setPlaceholderText("sk-... (или положите .env рядом с приложением)")

        self.show_key_btn = QPushButton("Показать")
        self.show_key_btn.setCheckable(True)
        self.show_key_btn.toggled.connect(self._toggle_key)

        key_row = QHBoxLayout()
        key_row.addWidget(self.key_input)
        key_row.addWidget(self.show_key_btn)

        self.model_input = QLineEdit(snap.get("openai_model") or "gpt-4o-mini")
        self.vision_input = QLineEdit(snap.get("openai_vision_model") or "gpt-4o-mini")
        self.base_url_input = QLineEdit(
            snap.get("openai_base_url") or "https://api.openai.com/v1"
        )
        self.urls_input = QTextEdit()
        self.urls_input.setPlaceholderText("https://gestion.ru/\nhttps://example.com/")
        self.urls_input.setMaximumHeight(100)
        self.urls_input.setPlainText("\n".join(snap.get("competitor_urls") or []))

        form.addRow("OpenAI API Key", key_row)
        form.addRow("Модель текста", self.model_input)
        form.addRow("Модель vision", self.vision_input)
        form.addRow("Base URL", self.base_url_input)
        form.addRow("URL конкурентов", self.urls_input)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _toggle_key(self, checked: bool):
        if checked:
            self.key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.show_key_btn.setText("Скрыть")
        else:
            self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.show_key_btn.setText("Показать")

    def _save(self):
        key = self.key_input.text().strip()
        if not key and not self._had_api_key:
            QMessageBox.warning(
                self,
                "Настройки",
                "Укажите OPENAI_API_KEY или положите файл .env с ключом в папку приложения.",
            )
            return
        result = api_client.save_settings(
            openai_api_key=key,
            openai_model=self.model_input.text().strip(),
            openai_vision_model=self.vision_input.text().strip(),
            openai_base_url=self.base_url_input.text().strip(),
            competitor_urls=self.urls_input.toPlainText(),
        )
        if result.get("success"):
            QMessageBox.information(
                self,
                "Сохранено",
                f"Настройки записаны в:\n{result.get('env_path')}",
            )
            self.accept()
        else:
            QMessageBox.critical(self, "Ошибка", result.get("error", "Не удалось сохранить"))


class WorkerThread(QThread):
    """Поток для выполнения API запросов"""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
    
    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class DropZone(QFrame):
    """Зона для drag & drop изображений"""
    fileDropped = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.setObjectName("uploadZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(200)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.icon_label = QLabel("📁")
        self.icon_label.setStyleSheet("font-size: 48px;")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.text_label = QLabel("Перетащите изображение/PDF или нажмите для выбора")
        self.text_label.setStyleSheet("color: #94a3b8; font-size: 14px;")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.hint_label = QLabel("PNG, JPG, GIF, WEBP, PDF до 10MB")
        self.hint_label.setStyleSheet("color: #64748b; font-size: 12px;")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.hide()
        
        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)
        layout.addWidget(self.hint_label)
        layout.addWidget(self.preview_label)
        
        self.selected_file = None
    
    def mousePressEvent(self, event):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите изображение или PDF",
            "",
            "Изображения и PDF (*.png *.jpg *.jpeg *.gif *.webp *.pdf)"
        )
        if file_path:
            self.set_file(file_path)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("QFrame#uploadZone { border-color: #06b6d4; background-color: rgba(6, 182, 212, 0.1); }")
    
    def dragLeaveEvent(self, event):
        self.setStyleSheet("")
    
    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet("")
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.pdf')):
                self.set_file(file_path)
    
    def set_file(self, file_path: str):
        self.selected_file = file_path
        name = Path(file_path).name
        is_pdf = file_path.lower().endswith('.pdf')

        if is_pdf:
            self.preview_label.clear()
            self.preview_label.setText("📄 PDF")
            self.preview_label.setStyleSheet("font-size: 48px; color: #22d3ee;")
            self.preview_label.show()
            self.icon_label.hide()
            self.text_label.setText(name)
            self.hint_label.setText("Нажмите для замены")
        else:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(
                    300, 200,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.preview_label.setStyleSheet("")
                self.preview_label.setPixmap(pixmap)
                self.preview_label.show()
                self.icon_label.hide()
                self.text_label.setText(name)
                self.hint_label.setText("Нажмите для замены")
        
        self.fileDropped.emit(file_path)
    
    def clear(self):
        self.selected_file = None
        self.preview_label.hide()
        self.preview_label.clear()
        self.preview_label.setStyleSheet("")
        self.icon_label.show()
        self.text_label.setText("Перетащите изображение/PDF или нажмите для выбора")
        self.hint_label.setText("PNG, JPG, GIF, WEBP, PDF до 10MB")


class ResultBlock(QFrame):
    """Блок результата анализа"""
    def __init__(self, title: str, items: list, icon: str = "→"):
        super().__init__()
        self.setObjectName("resultBlock")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        
        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        layout.addWidget(title_label)
        
        for item in items:
            item_label = QLabel(f"{icon} {item}")
            item_label.setWordWrap(True)
            item_label.setStyleSheet("color: #94a3b8; margin-left: 8px; line-height: 1.5;")
            layout.addWidget(item_label)


class MainWindow(QMainWindow):
    """Главное окно приложения"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Мониторинг конкурентов | AI Ассистент")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)
        
        # Применяем стили
        self.setStyleSheet(DARK_THEME)
        
        # Главный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Главный layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Sidebar
        self.setup_sidebar(main_layout)
        
        # Content area
        self.setup_content(main_layout)
        
        # Текущий worker
        self.current_worker = None

        # Статус без ключа — не блокируем запуск (проверка после показа окна)
        QTimer.singleShot(0, self.check_server_connection)

    def setup_sidebar(self, parent_layout):
        """Создание боковой панели"""
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(280)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Logo
        logo = QLabel("⚡ CompetitorAI")
        logo.setObjectName("logo")
        layout.addWidget(logo)
        
        # Navigation
        nav_widget = QWidget()
        nav_layout = QVBoxLayout(nav_widget)
        nav_layout.setContentsMargins(12, 16, 12, 16)
        nav_layout.setSpacing(4)
        
        self.nav_buttons = []
        nav_items = [
            ("📝 Анализ текста", 0),
            ("🖼️ Анализ изображений / PDF", 1),
            ("🌐 Парсинг сайта", 2),
            ("📋 История", 3)
        ]
        
        for text, index in nav_items:
            btn = QPushButton(text)
            btn.setObjectName("navButton")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, idx=index: self.switch_tab(idx))
            nav_layout.addWidget(btn)
            self.nav_buttons.append(btn)
        
        self.nav_buttons[0].setChecked(True)
        
        nav_layout.addStretch()

        self.settings_btn = QPushButton("Настройки (OpenAI Key)")
        self.settings_btn.setObjectName("secondaryButton")
        self.settings_btn.clicked.connect(self.open_settings)
        nav_layout.addWidget(self.settings_btn)

        # Status
        self.status_label = QLabel("● Проверка...")
        self.status_label.setStyleSheet("color: #f59e0b; padding: 16px;")
        nav_layout.addWidget(self.status_label)

        layout.addWidget(nav_widget)
        parent_layout.addWidget(sidebar)
    
    def setup_content(self, parent_layout):
        """Создание области контента"""
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(40, 32, 40, 32)
        
        # Header
        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 24)
        
        title = QLabel("Мониторинг конкурентов")
        title.setObjectName("title")
        
        subtitle = QLabel(
            "AI-анализатор юрфирм: регистрация/ликвидация, лицензирование, арбитраж"
        )
        subtitle.setObjectName("subtitle")
        
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        content_layout.addWidget(header)
        
        # Stacked widget для вкладок
        self.stacked_widget = QStackedWidget()
        
        # Добавляем вкладки
        self.stacked_widget.addWidget(self.create_text_tab())
        self.stacked_widget.addWidget(self.create_image_tab())
        self.stacked_widget.addWidget(self.create_parse_tab())
        self.stacked_widget.addWidget(self.create_history_tab())
        
        content_layout.addWidget(self.stacked_widget)
        
        # Results area
        self.results_scroll = QScrollArea()
        self.results_scroll.setWidgetResizable(True)
        self.results_scroll.hide()
        
        self.results_widget = QWidget()
        self.results_layout = QVBoxLayout(self.results_widget)
        self.results_scroll.setWidget(self.results_widget)
        
        content_layout.addWidget(self.results_scroll)
        
        # Loading indicator
        self.loading_widget = QWidget()
        loading_layout = QVBoxLayout(self.loading_widget)
        loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setFixedWidth(300)
        
        self.loading_label = QLabel("Анализирую данные...")
        self.loading_label.setStyleSheet("color: #94a3b8; font-size: 16px;")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        loading_layout.addWidget(self.progress_bar, alignment=Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(self.loading_label)
        
        self.loading_widget.hide()
        content_layout.addWidget(self.loading_widget)
        
        parent_layout.addWidget(content_widget)
    
    def create_text_tab(self) -> QWidget:
        """Вкладка анализа текста"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Card
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        
        title = QLabel("Анализ текста конкурента")
        title.setObjectName("cardTitle")
        
        desc = QLabel("Вставьте текст с сайта конкурента, из рекламы или описания продукта")
        desc.setObjectName("cardDescription")
        
        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("Вставьте текст конкурента для анализа...\n\nНапример: описание продукта, текст с лендинга, рекламное объявление...")
        self.text_input.setMinimumHeight(200)
        
        self.analyze_text_btn = QPushButton("⚡ Проанализировать")
        self.analyze_text_btn.setObjectName("primaryButton")
        self.analyze_text_btn.clicked.connect(self.analyze_text)
        
        card_layout.addWidget(title)
        card_layout.addWidget(desc)
        card_layout.addSpacing(16)
        card_layout.addWidget(self.text_input)
        card_layout.addSpacing(16)
        card_layout.addWidget(self.analyze_text_btn)
        
        layout.addWidget(card)
        layout.addStretch()
        
        return widget
    
    def create_image_tab(self) -> QWidget:
        """Вкладка анализа изображений"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Card
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        
        title = QLabel("Анализ изображений и PDF")
        title.setObjectName("cardTitle")
        
        desc = QLabel(
            "Загрузите скриншот сайта, баннер или PDF (буклет / КП) конкурента"
        )
        desc.setObjectName("cardDescription")
        desc.setWordWrap(True)
        
        self.drop_zone = DropZone()
        
        self.analyze_image_btn = QPushButton("⚡ Проанализировать")
        self.analyze_image_btn.setObjectName("primaryButton")
        self.analyze_image_btn.clicked.connect(self.analyze_image)
        
        card_layout.addWidget(title)
        card_layout.addWidget(desc)
        card_layout.addSpacing(16)
        card_layout.addWidget(self.drop_zone)
        card_layout.addSpacing(16)
        card_layout.addWidget(self.analyze_image_btn)
        
        layout.addWidget(card)
        layout.addStretch()
        
        return widget
    
    def create_parse_tab(self) -> QWidget:
        """Вкладка парсинга сайта + автосбор из config"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Парсинг сайта конкурента")
        title.setObjectName("cardTitle")

        desc = QLabel(
            "Один URL вручную или автосбор всех конкурентов из config "
            "(юрфирмы: регистрация/ликвидация, лицензии, арбитраж)"
        )
        desc.setObjectName("cardDescription")
        desc.setWordWrap(True)

        url_layout = QHBoxLayout()
        prefix = QLabel("https://")
        prefix.setStyleSheet(
            "background-color: #243049; padding: 12px 16px; "
            "border-radius: 8px 0 0 8px; color: #64748b;"
        )
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("example.com")
        self.url_input.setStyleSheet("border-radius: 0 8px 8px 0;")
        self.url_input.returnPressed.connect(self.parse_site)
        url_layout.addWidget(prefix)
        url_layout.addWidget(self.url_input)

        buttons = QHBoxLayout()
        self.parse_btn = QPushButton("Парсить и анализировать")
        self.parse_btn.setObjectName("primaryButton")
        self.parse_btn.clicked.connect(self.parse_site)

        self.collect_btn = QPushButton("Собрать всех из config")
        self.collect_btn.setObjectName("secondaryButton")
        self.collect_btn.clicked.connect(self.collect_competitors)

        buttons.addWidget(self.parse_btn)
        buttons.addWidget(self.collect_btn)

        self.competitors_label = QLabel("Загрузка списка конкурентов...")
        self.competitors_label.setObjectName("cardDescription")
        self.competitors_label.setWordWrap(True)

        card_layout.addWidget(title)
        card_layout.addWidget(desc)
        card_layout.addSpacing(16)
        card_layout.addLayout(url_layout)
        card_layout.addSpacing(12)
        card_layout.addLayout(buttons)
        card_layout.addSpacing(12)
        card_layout.addWidget(self.competitors_label)

        layout.addWidget(card)
        layout.addStretch()

        self.refresh_competitors_list()
        return widget

    def create_history_tab(self) -> QWidget:
        """Вкладка истории"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        header = QHBoxLayout()
        title = QLabel("История запросов")
        title.setObjectName("cardTitle")
        self.clear_history_btn = QPushButton("Очистить")
        self.clear_history_btn.setObjectName("secondaryButton")
        self.clear_history_btn.clicked.connect(self.clear_history)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.clear_history_btn)
        layout.addLayout(header)

        self.history_scroll = QScrollArea()
        self.history_scroll.setWidgetResizable(True)
        self.history_widget = QWidget()
        self.history_layout = QVBoxLayout(self.history_widget)
        self.history_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.history_scroll.setWidget(self.history_widget)
        layout.addWidget(self.history_scroll)
        return widget

    def refresh_competitors_list(self):
        """Показать URL из config на вкладке парсинга"""
        try:
            data = api_client.get_competitors()
        except Exception as e:
            self.competitors_label.setText(
                f"Список конкурентов пока недоступен.\n"
                f"Откройте Настройки и укажите ключ при необходимости.\n({e})"
            )
            return
        urls = data.get("competitor_urls") or []
        if not urls:
            self.competitors_label.setText(
                "Список COMPETITOR_URLS пуст — добавьте URL в config.py или .env"
            )
            return
        lines = "\n".join(f"• {u}" for u in urls)
        self.competitors_label.setText(f"Конкуренты из config ({len(urls)}):\n{lines}")

    def show_loading(self, message: str = "Анализирую данные..."):
        """Показать индикатор загрузки"""
        self.loading_label.setText(message)
        self.loading_widget.show()
        self.results_scroll.hide()

        self.analyze_text_btn.setEnabled(False)
        self.analyze_image_btn.setEnabled(False)
        self.parse_btn.setEnabled(False)
        if hasattr(self, "collect_btn"):
            self.collect_btn.setEnabled(False)

    def hide_loading(self):
        """Скрыть индикатор загрузки"""
        self.loading_widget.hide()

        self.analyze_text_btn.setEnabled(True)
        self.analyze_image_btn.setEnabled(True)
        self.parse_btn.setEnabled(True)
        if hasattr(self, "collect_btn"):
            self.collect_btn.setEnabled(True)

    def show_parsed_meta(self, data: dict):
        """Показать метаданные страницы перед анализом"""
        lines = []
        if data.get("url"):
            lines.append(f"URL: {data['url']}")
        if data.get("title"):
            lines.append(f"Title: {data['title']}")
        if data.get("h1"):
            lines.append(f"H1: {data['h1']}")
        if data.get("first_paragraph"):
            lines.append(f"Абзац: {data['first_paragraph'][:200]}")
        if data.get("meta_description"):
            lines.append(f"Meta: {data['meta_description'][:200]}")
        if data.get("contacts"):
            lines.append("Контакты: " + ", ".join(data["contacts"][:5]))
        if data.get("cta_texts"):
            lines.append("CTA: " + " · ".join(data["cta_texts"][:5]))
        if data.get("service_links"):
            lines.extend(data["service_links"][:8])
        if lines:
            block = ResultBlock("Данные со страницы", lines)
            self.results_layout.addWidget(block)

    def show_collect_results(self, result: dict):
        """Результаты автосбора всех конкурентов"""
        while self.results_layout.count():
            child = self.results_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        title = QLabel("Автосбор конкурентов")
        title.setObjectName("cardTitle")
        title.setStyleSheet("font-size: 18px; margin-bottom: 16px;")
        self.results_layout.addWidget(title)

        urls = result.get("competitor_urls") or []
        header = ResultBlock(
            f"Собрано сайтов: {result.get('total', 0)}",
            urls or ["(список пуст)"],
        )
        self.results_layout.addWidget(header)

        for idx, item in enumerate(result.get("items") or [], 1):
            section = QLabel(f"{idx}. {item.get('url', '')}")
            section.setStyleSheet("color: #22d3ee; font-weight: bold; margin-top: 12px;")
            self.results_layout.addWidget(section)

            if item.get("error"):
                self.results_layout.addWidget(
                    ResultBlock("Ошибка", [item["error"]])
                )
            else:
                self.show_parsed_meta(item)
                if item.get("analysis"):
                    self._append_text_analysis(item["analysis"])

        self.results_layout.addStretch()
        self.results_scroll.show()

    def _append_text_analysis(self, analysis: dict):
        """Блоки текстового/сайт-анализа (без очистки layout)"""
        if analysis.get("strengths"):
            self.results_layout.addWidget(ResultBlock("Сильные стороны", analysis["strengths"]))
        if analysis.get("weaknesses"):
            self.results_layout.addWidget(ResultBlock("Слабые стороны", analysis["weaknesses"]))
        if analysis.get("unique_offers"):
            self.results_layout.addWidget(
                ResultBlock("Уникальные предложения", analysis["unique_offers"])
            )
        if analysis.get("service_focus"):
            self.results_layout.addWidget(ResultBlock("Фокус услуг", analysis["service_focus"]))
        if analysis.get("trust_signals"):
            self.results_layout.addWidget(
                ResultBlock("Сигналы доверия", analysis["trust_signals"])
            )
        if analysis.get("content_gaps"):
            self.results_layout.addWidget(
                ResultBlock("Пробелы для B2B-клиента", analysis["content_gaps"])
            )
        if analysis.get("recommendations"):
            self.results_layout.addWidget(
                ResultBlock("Рекомендации", analysis["recommendations"])
            )

        scores = [
            ("Доверие / экспертность", "trust_score"),
            ("Сила CTA", "cta_score"),
            ("Понятность для бизнеса", "content_clarity_score"),
            ("Покрытие услуг (рег./ликв./лицензии/арбитраж)", "service_coverage_score"),
            ("Прозрачность цен", "pricing_transparency_score"),
            ("Конкурентная угроза", "competitive_threat"),
        ]
        score_lines = [
            f"{label}: {analysis.get(key, 0)}/10"
            for label, key in scores
            if key in analysis
        ]
        if score_lines:
            self.results_layout.addWidget(
                ResultBlock("Оценки конкурента (юруслуги для бизнеса)", score_lines)
            )

        extras = []
        if analysis.get("target_audience"):
            extras.append(f"ЦА: {analysis['target_audience']}")
        if analysis.get("positioning_notes"):
            extras.append(f"Позиционирование: {analysis['positioning_notes']}")
        if extras:
            self.results_layout.addWidget(ResultBlock("Детали", extras))

        if analysis.get("summary"):
            summary_frame = QFrame()
            summary_frame.setObjectName("resultBlock")
            summary_layout = QVBoxLayout(summary_frame)
            summary_title = QLabel("Резюме")
            summary_title.setObjectName("sectionTitle")
            summary_text = QLabel(analysis["summary"])
            summary_text.setWordWrap(True)
            summary_text.setStyleSheet("color: #f1f5f9; font-size: 15px;")
            summary_layout.addWidget(summary_title)
            summary_layout.addWidget(summary_text)
            self.results_layout.addWidget(summary_frame)

    def show_results(self, analysis: dict, result_type: str = "text", meta: dict = None):
        """Отображение результатов анализа"""
        while self.results_layout.count():
            child = self.results_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        title = QLabel("Результаты анализа")
        title.setObjectName("cardTitle")
        title.setStyleSheet("font-size: 18px; margin-bottom: 16px;")
        self.results_layout.addWidget(title)

        if result_type in ("text", "parse"):
            if meta:
                self.show_parsed_meta(meta)
            self._append_text_analysis(analysis)

        elif result_type == "image":
            if analysis.get("description"):
                desc_frame = QFrame()
                desc_frame.setObjectName("resultBlock")
                desc_layout = QVBoxLayout(desc_frame)
                desc_title = QLabel("Описание")
                desc_title.setObjectName("sectionTitle")
                desc_text = QLabel(analysis["description"])
                desc_text.setWordWrap(True)
                desc_text.setStyleSheet("color: #94a3b8;")
                desc_layout.addWidget(desc_title)
                desc_layout.addWidget(desc_text)
                self.results_layout.addWidget(desc_frame)

            score_frame = QFrame()
            score_frame.setObjectName("resultBlock")
            score_layout = QVBoxLayout(score_frame)
            score_title = QLabel("Оценки материала юрфирмы")
            score_title.setObjectName("sectionTitle")
            score_layout.addWidget(score_title)
            score_value = QLabel(
                f"Юрбренд: {analysis.get('legal_branding_fit', 0)}/10 | "
                f"Заметность услуг: {analysis.get('service_visibility_score', 0)}/10 | "
                f"Ясность оффера: {analysis.get('offer_clarity_score', 0)}/10"
            )
            score_value.setStyleSheet("font-size: 16px; font-weight: bold; color: #22d3ee;")
            score_value.setWordWrap(True)
            score_layout.addWidget(score_value)
            if analysis.get("trust_perception"):
                trust = QLabel(f"Доверие: {analysis['trust_perception']}")
                trust.setWordWrap(True)
                trust.setStyleSheet("color: #94a3b8;")
                score_layout.addWidget(trust)
            self.results_layout.addWidget(score_frame)

            if analysis.get("marketing_insights"):
                self.results_layout.addWidget(
                    ResultBlock("Маркетинговые инсайты", analysis["marketing_insights"])
                )
            if analysis.get("recommendations"):
                self.results_layout.addWidget(
                    ResultBlock("Рекомендации", analysis["recommendations"])
                )

        self.results_layout.addStretch()
        self.results_scroll.show()

    def on_parse_complete(self, result: dict):
        """Обработка результата парсинга"""
        self.hide_loading()

        if result.get("success") and result.get("data"):
            data = result["data"]
            if data.get("analysis"):
                self.show_results(data["analysis"], "parse", meta=data)
            else:
                self.show_error(data.get("error") or "Не удалось проанализировать сайт")
        else:
            self.show_error(result.get("error", "Неизвестная ошибка"))

    def collect_competitors(self):
        """Автосбор всех URL из config"""
        self.show_loading("Собираю данные по всем конкурентам из config...")
        self.current_worker = WorkerThread(api_client.collect_competitors, True)
        self.current_worker.finished.connect(self.on_collect_complete)
        self.current_worker.error.connect(lambda e: self.on_error(e))
        self.current_worker.start()

    def on_collect_complete(self, result: dict):
        self.hide_loading()
        if result.get("success"):
            self.show_collect_results(result)
        else:
            self.show_error(result.get("error", "Не удалось выполнить автосбор"))

    def analyze_image(self):
        """Анализ изображения или PDF"""
        if not self.drop_zone.selected_file:
            self.show_error("Выберите изображение или PDF для анализа")
            return

        name = Path(self.drop_zone.selected_file).name.lower()
        msg = "Анализирую PDF..." if name.endswith(".pdf") else "Анализирую изображение..."
        self.show_loading(msg)

        self.current_worker = WorkerThread(api_client.analyze_image, self.drop_zone.selected_file)
        self.current_worker.finished.connect(self.on_image_analysis_complete)
        self.current_worker.error.connect(lambda e: self.on_error(e))
        self.current_worker.start()

    def switch_tab(self, index: int):
        """Переключение вкладок"""
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)

        self.stacked_widget.setCurrentIndex(index)
        self.results_scroll.hide()

        if index == 2:
            self.refresh_competitors_list()
        if index == 3:
            self.load_history()

    def open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec():
            self.check_server_connection()
            if hasattr(self, "competitors_label"):
                self.refresh_competitors_list()

    def check_server_connection(self):
        """Статус автономного режима. Без ключа приложение всё равно работает."""
        try:
            ok = api_client.check_health()
        except Exception:
            ok = False

        if not ok:
            self.status_label.setText("● Ошибка инициализации")
            self.status_label.setStyleSheet("color: #ef4444; padding: 16px;")
            return

        if api_client.has_api_key():
            self.status_label.setText("● Автономный режим")
            self.status_label.setStyleSheet("color: #10b981; padding: 16px;")
        else:
            self.status_label.setText("● Нет ключа — откройте Настройки")
            self.status_label.setStyleSheet("color: #f59e0b; padding: 16px;")
            # Без модального окна: пользователь сам откроет Настройки и впишет ключ

    def show_error(self, message: str):
        QMessageBox.critical(self, "Ошибка", message)

    def analyze_text(self):
        text = self.text_input.toPlainText().strip()
        if len(text) < 10:
            self.show_error("Введите текст минимум 10 символов")
            return
        self.show_loading("Анализирую текст...")
        self.current_worker = WorkerThread(api_client.analyze_text, text)
        self.current_worker.finished.connect(self.on_text_analysis_complete)
        self.current_worker.error.connect(lambda e: self.on_error(e))
        self.current_worker.start()

    def on_text_analysis_complete(self, result: dict):
        self.hide_loading()
        if result.get("success") and result.get("analysis"):
            self.show_results(result["analysis"], "text")
        else:
            self.show_error(result.get("error", "Неизвестная ошибка"))

    def on_image_analysis_complete(self, result: dict):
        self.hide_loading()
        if result.get("success") and result.get("analysis"):
            self.show_results(result["analysis"], "image")
        else:
            self.show_error(result.get("error", "Неизвестная ошибка"))

    def parse_site(self):
        url = self.url_input.text().strip()
        if not url:
            self.show_error("Введите URL сайта")
            return
        self.show_loading("Загружаю и анализирую сайт...")
        self.current_worker = WorkerThread(api_client.parse_demo, url)
        self.current_worker.finished.connect(self.on_parse_complete)
        self.current_worker.error.connect(lambda e: self.on_error(e))
        self.current_worker.start()

    def load_history(self):
        """Загрузка истории"""
        try:
            result = api_client.get_history()
        except Exception as e:
            result = {"items": [], "error": str(e)}

        while self.history_layout.count():
            child = self.history_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        items = result.get("items") or []
        if items:
            for item in items:
                if not isinstance(item, dict):
                    continue
                frame = QFrame()
                frame.setObjectName("historyItem")
                layout = QHBoxLayout(frame)

                icons = {"text": "T", "image": "IMG", "parse": "URL"}
                icon = QLabel(icons.get(item.get("request_type", ""), "#"))
                icon.setStyleSheet("font-size: 14px; font-weight: bold; color: #22d3ee;")

                content = QWidget()
                content_layout = QVBoxLayout(content)
                content_layout.setContentsMargins(0, 0, 0, 0)

                type_labels = {
                    "text": "Анализ текста",
                    "image": "Анализ изображения / PDF",
                    "parse": "Парсинг сайта",
                }
                type_label = QLabel(
                    type_labels.get(item.get("request_type", ""), str(item.get("request_type", "")))
                )
                type_label.setStyleSheet("color: #22d3ee; font-size: 12px; font-weight: bold;")

                summary_text = str(item.get("request_summary", "") or "")
                if len(summary_text) > 60:
                    summary_text = summary_text[:60] + "..."
                summary = QLabel(summary_text)
                summary.setStyleSheet("color: #94a3b8;")
                summary.setWordWrap(True)

                content_layout.addWidget(type_label)
                content_layout.addWidget(summary)

                timestamp = item.get("timestamp", "")
                time_str = ""
                if timestamp:
                    try:
                        if isinstance(timestamp, datetime):
                            time_str = timestamp.strftime("%d.%m %H:%M")
                        else:
                            dt = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
                            time_str = dt.strftime("%d.%m %H:%M")
                    except Exception:
                        time_str = str(timestamp)[:16]

                time_label = QLabel(time_str)
                time_label.setStyleSheet("color: #64748b; font-size: 12px;")

                layout.addWidget(icon)
                layout.addWidget(content, stretch=1)
                layout.addWidget(time_label)
                self.history_layout.addWidget(frame)
        else:
            empty_label = QLabel("История пуста")
            if result.get("error"):
                empty_label = QLabel(f"Не удалось загрузить историю:\n{result['error']}")
            empty_label.setStyleSheet("color: #64748b; font-size: 16px; padding: 40px;")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.history_layout.addWidget(empty_label)

        self.history_layout.addStretch()

    def clear_history(self):
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            "Вы уверены, что хотите очистить историю?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            api_client.clear_history()
            self.load_history()

    def on_error(self, error: str):
        self.hide_loading()
        self.show_error(error)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    # Без API-ключа и без .env окно всё равно открывается —
    # ключ вводится позже в «Настройки»
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

