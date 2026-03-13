"""Main application window with multi-page wizard interface."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

from PySide6.QtCore import Slot, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..core.window_manager import WindowManager
from ..core.screenshot import ScreenshotReader
from ..llm.base import BaseLLMClient
from ..models.window import WindowInfo
from ..models.detection import AreaDetectionResult
from .overlay import AreaSelectionOverlay
from .workers import AutoChatWorker
from .i18n import tr, set_locale
from .pages import ConnectionPage, WindowPage, AreaPage, KBPage, OpenCodePage, ChatPage
from .widgets import ProgressIndicator

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

IS_LINUX = sys.platform == "linux"


class MainWindow(QMainWindow):
    """Main application window with multi-page wizard interface."""

    def __init__(self):
        super().__init__()

        # State
        self._llm_client: BaseLLMClient | None = None
        self._window_manager = WindowManager()
        self._screenshot_reader = ScreenshotReader()
        self._selected_window: WindowInfo | None = None
        self._window_list: list[WindowInfo] = []
        self._auto_worker: AutoChatWorker | None = None
        self._detected_areas: AreaDetectionResult | None = None
        self._manual_chat_rect: tuple[int, int, int, int] | None = None
        self._manual_input_rect: tuple[int, int, int, int] | None = None
        self._manual_send_btn_pos: tuple[int, int] | None = None
        self._overlay: AreaSelectionOverlay | None = None
        self._selecting_purpose = ""
        self._kb_config: dict | None = None

        self._current_page = 0

        self._build_ui()
        self._build_menu()
        self._update_ui_text()
        self._update_navigation()

        # Request screen permission on Linux after window is shown
        if IS_LINUX:
            QTimer.singleShot(500, self._request_screen_permission)

    def _request_screen_permission(self) -> None:
        """Request screen capture permission on Linux/Wayland."""
        if self._screenshot_reader.has_screen_permission():
            logger.info("Screen capture permission already granted")
            return

        # Show info dialog before permission request
        QMessageBox.information(
            self,
            tr("dialog.screen_permission_title"),
            tr("dialog.screen_permission_text"),
        )

        # Request permission (this triggers the Wayland portal dialog)
        if self._screenshot_reader.request_screen_permission():
            logger.info("Screen capture permission granted")
        else:
            logger.warning("Screen capture permission denied or failed")
            QMessageBox.warning(
                self,
                tr("dialog.screen_permission_title"),
                tr("dialog.screen_permission_failed"),
            )

    def _build_menu(self) -> None:
        """Build menu bar."""
        menubar = self.menuBar()
        menubar.clear()

        file_menu = menubar.addMenu(tr("menu.file"))
        exit_action = QAction(tr("menu.exit"), self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        lang_menu = menubar.addMenu(tr("menu.language"))
        en_action = QAction("English", self)
        en_action.triggered.connect(lambda: self._change_language("en_US"))
        lang_menu.addAction(en_action)
        zh_action = QAction("中文", self)
        zh_action.triggered.connect(lambda: self._change_language("zh_CN"))
        lang_menu.addAction(zh_action)

        help_menu = menubar.addMenu(tr("menu.help"))
        about_action = QAction(tr("menu.about"), self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _update_ui_text(self) -> None:
        """Update all UI text with current translations."""
        self.setWindowTitle(tr("app.title"))
        self._back_btn.setText(tr("navigation.back"))
        self._next_btn.setText(tr("navigation.next"))
        self._progress.update_translations()
        self._connection_page.update_translations()
        self._window_page.update_translations()
        self._area_page.update_translations()
        self._kb_page.update_translations()
        self._opencode_page.update_translations()
        self._chat_page.update_translations()

    def _build_ui(self) -> None:
        """Build the main UI with stacked pages."""
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(10)
        root.setContentsMargins(15, 10, 15, 10)

        # Progress indicator
        self._progress = ProgressIndicator()
        self._progress.setFixedHeight(100)
        root.addWidget(self._progress)

        # Stacked widget for pages
        self._stack = QStackedWidget()

        self._connection_page = ConnectionPage(self)
        self._window_page = WindowPage(self)
        self._area_page = AreaPage(self)
        self._kb_page = KBPage(self)
        self._opencode_page = OpenCodePage(self)
        self._chat_page = ChatPage(self)

        self._stack.addWidget(self._connection_page)
        self._stack.addWidget(self._window_page)
        self._stack.addWidget(self._area_page)
        self._stack.addWidget(self._kb_page)
        self._stack.addWidget(self._opencode_page)
        self._stack.addWidget(self._chat_page)

        root.addWidget(self._stack, 1)

        # Connect signals
        self._connection_page.connection_changed.connect(self._on_connection_changed)
        self._window_page.window_selected.connect(self._on_window_selected)
        self._area_page.area_selection_requested.connect(self._on_area_select)

        # Navigation footer
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(15)

        self._back_btn = QPushButton()
        self._back_btn.clicked.connect(self._on_back)
        nav_layout.addWidget(self._back_btn)

        nav_layout.addStretch()

        self._status_label = QLabel()
        nav_layout.addWidget(self._status_label)

        nav_layout.addStretch()

        self._next_btn = QPushButton()
        self._next_btn.clicked.connect(self._on_next)
        nav_layout.addWidget(self._next_btn)

        root.addLayout(nav_layout)

        self.resize(700, 900)
        self.setMinimumSize(700, 800)

    def _go_to_page(self, index: int) -> None:
        """Navigate to a specific page."""
        if index < 0 or index > 5:
            return

        current_widget = self._stack.currentWidget()
        if hasattr(current_widget, "on_leave"):
            current_widget.on_leave()

        self._current_page = index
        self._stack.setCurrentIndex(index)
        self._progress.set_current_step(index)

        new_widget = self._stack.currentWidget()
        if hasattr(new_widget, "on_enter"):
            new_widget.on_enter()

        self._update_navigation()

    def _on_back(self) -> None:
        """Navigate to previous page."""
        if self._current_page > 0:
            self._go_to_page(self._current_page - 1)

    def _on_next(self) -> None:
        """Navigate to next page."""
        current_widget = self._stack.currentWidget()
        if hasattr(current_widget, "is_valid") and not current_widget.is_valid():
            return
        if self._current_page < 5:
            self._go_to_page(self._current_page + 1)

    def _update_navigation(self) -> None:
        """Update navigation button states."""
        self._back_btn.setEnabled(self._current_page > 0)

        current_widget = self._stack.currentWidget()
        is_valid = True
        if hasattr(current_widget, "is_valid"):
            is_valid = current_widget.is_valid()

        self._next_btn.setVisible(self._current_page < 5)
        self._next_btn.setEnabled(is_valid)
        self._status_label.setText(tr("status.ready"))

    @Slot(bool)
    def _on_connection_changed(self, connected: bool) -> None:
        """Handle LLM connection state change."""
        self._update_navigation()
        if connected:
            self._status_label.setText(tr("connection.status.connected", count=0))
        else:
            self._status_label.setText(tr("connection.status.disconnected"))

    @Slot(object)
    def _on_window_selected(self, window: WindowInfo) -> None:
        """Handle window selection."""
        self._selected_window = window
        self._detected_areas = None
        self._manual_chat_rect = None
        self._manual_input_rect = None
        self._manual_send_btn_pos = None
        self._update_navigation()

    def _on_area_select(self, purpose: str) -> None:
        """Start area selection overlay."""
        if not self._selected_window:
            return

        if self._overlay:
            self._overlay.close()

        self._selecting_purpose = purpose

        existing = {}
        if self._manual_chat_rect:
            existing["chat"] = self._manual_chat_rect
        if self._manual_input_rect:
            existing["input"] = self._manual_input_rect
        if self._manual_send_btn_pos:
            sx, sy = self._manual_send_btn_pos
            existing["send"] = (sx - 20, sy - 10, sx + 20, sy + 10)

        self._overlay = AreaSelectionOverlay(
            target_window_rect=self._selected_window.rect,
            purpose=purpose,
            existing_rects=existing,
        )
        self._overlay.area_selected.connect(self._on_area_selected)
        self._overlay.selection_cancelled.connect(lambda: setattr(self, "_overlay", None))
        self._overlay.show()

    @Slot(tuple)
    def _on_area_selected(self, rect: tuple[int, int, int, int]) -> None:
        """Handle area selection result."""
        self._overlay = None
        p = self._selecting_purpose

        if p == "chat":
            self._manual_chat_rect = rect
        elif p == "input":
            self._manual_input_rect = rect
        elif p == "send":
            cx, cy = (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2
            self._manual_send_btn_pos = (cx, cy)

        self._area_page.on_area_selected(p, rect)

    def _show_about(self) -> None:
        """Show about dialog."""
        QMessageBox.about(
            self, tr("dialog.about_title"), tr("dialog.about_text", version=__version__)
        )

    def _change_language(self, locale_code: str) -> None:
        """Switch UI language."""
        set_locale(locale_code)
        self._build_menu()
        self._update_ui_text()
