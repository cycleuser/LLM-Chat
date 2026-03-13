"""Area setup page for chat/input area detection."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr
from ...core.chat_input import ChatInput
from ...core.area_detector import ChatAreaDetector
from ...core.smart_automation import SmartAutomationManager
from ...models.detection import AreaDetectionResult
from .base_page import BasePage

if TYPE_CHECKING:
    from ..main_window import MainWindow

logger = logging.getLogger(__name__)


class AreaPage(BasePage):
    """Page for area detection and manual selection."""

    area_selection_requested = Signal(str)

    def __init__(self, main_window: MainWindow, parent: QWidget | None = None):
        self._smart_manager: SmartAutomationManager | None = None
        self._chat_input: ChatInput | None = None
        super().__init__(main_window, parent)

    def _build_ui(self) -> None:
        """Build the area setup page UI."""
        self._title = QLabel()
        font = self._title.font()
        font.setPointSize(14)
        font.setBold(True)
        self._title.setFont(font)
        self._layout.addWidget(self._title)

        self._subtitle = QLabel()
        self._subtitle.setWordWrap(True)
        self._layout.addWidget(self._subtitle)

        auto_group = QGroupBox(tr("area.auto_detection"))
        auto_layout = QVBoxLayout(auto_group)

        auto_btn_row = QHBoxLayout()
        self._auto_detect_btn = QPushButton()
        self._auto_detect_btn.clicked.connect(self._on_auto_detect)
        self._auto_detect_btn.setStyleSheet("padding: 10px; font-weight: bold;")
        auto_btn_row.addWidget(self._auto_detect_btn)

        self._status_label = QLabel()
        self._status_label.setStyleSheet("color: gray;")
        auto_btn_row.addWidget(self._status_label)
        auto_btn_row.addStretch()
        auto_layout.addLayout(auto_btn_row)

        self._app_info_label = QLabel()
        self._app_info_label.setStyleSheet("color: #666; font-style: italic;")
        auto_layout.addWidget(self._app_info_label)

        self._layout.addWidget(auto_group)

        manual_group = QGroupBox(tr("area.manual_selection"))
        manual_layout = QVBoxLayout(manual_group)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self._capture_btn = QPushButton()
        self._capture_btn.clicked.connect(self._on_capture)
        btn_layout.addWidget(self._capture_btn)

        self._sel_chat_btn = QPushButton()
        self._sel_chat_btn.clicked.connect(lambda: self._on_area_select("chat"))
        btn_layout.addWidget(self._sel_chat_btn)

        self._sel_input_btn = QPushButton()
        self._sel_input_btn.clicked.connect(lambda: self._on_area_select("input"))
        btn_layout.addWidget(self._sel_input_btn)

        self._sel_send_btn = QPushButton()
        self._sel_send_btn.clicked.connect(lambda: self._on_area_select("send"))
        btn_layout.addWidget(self._sel_send_btn)

        self._clear_btn = QPushButton()
        self._clear_btn.clicked.connect(self._on_clear)
        self._clear_btn.setVisible(False)
        btn_layout.addWidget(self._clear_btn)

        self._test_btn = QPushButton()
        self._test_btn.clicked.connect(self._on_test_send)
        self._test_btn.setVisible(False)
        btn_layout.addWidget(self._test_btn)

        btn_layout.addStretch()
        manual_layout.addLayout(btn_layout)

        self._layout.addWidget(manual_group)

        self._screenshot_label = QLabel()
        self._screenshot_label.setAlignment(Qt.AlignCenter)
        self._screenshot_label.setMinimumHeight(300)
        self._layout.addWidget(self._screenshot_label, 1)

        self._info_label = QLabel()
        self._info_label.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(self._info_label)

        self.update_translations()

    def update_translations(self) -> None:
        """Update all translatable text."""
        self._title.setText(tr("area.title"))
        self._subtitle.setText(tr("area.subtitle"))
        self._capture_btn.setText(tr("area.capture"))
        self._clear_btn.setText(tr("area.clear"))
        self._auto_detect_btn.setText(tr("area.auto_detect"))

        mw = self.main_window
        if mw._manual_chat_rect:
            r = mw._manual_chat_rect
            self._sel_chat_btn.setText(f"{tr('area.select_chat')} ({r[2] - r[0]}x{r[3] - r[1]})")
        else:
            self._sel_chat_btn.setText(tr("area.select_chat"))

        if mw._manual_input_rect:
            r = mw._manual_input_rect
            self._sel_input_btn.setText(f"{tr('area.select_input')} ({r[2] - r[0]}x{r[3] - r[1]})")
        else:
            self._sel_input_btn.setText(tr("area.select_input"))

        if mw._manual_send_btn_pos:
            x, y = mw._manual_send_btn_pos
            self._sel_send_btn.setText(f"{tr('area.select_send')} ({x},{y})")
        else:
            self._sel_send_btn.setText(tr("area.select_send"))

        if mw._selected_window:
            app_type = mw._selected_window.app_type
            self._app_info_label.setText(f"{tr('area.detected_app')}: {app_type}")
        else:
            self._app_info_label.setText(tr("area.no_window"))

        self._test_btn.setText(tr("area.test_send"))

    def is_valid(self) -> bool:
        """Area page is always valid (areas are optional)."""
        return True

    def on_enter(self) -> None:
        """Auto-capture when entering page if window is selected."""
        mw = self.main_window
        if mw._selected_window:
            if not mw._detected_areas:
                self._on_auto_detect()

    def _on_auto_detect(self) -> None:
        """Perform smart auto-detection of all chat elements."""
        mw = self.main_window
        if not mw._selected_window:
            QMessageBox.warning(self, tr("dialog.warning_title"), tr("area.select_window_first"))
            return

        self._status_label.setText(tr("area.detecting"))
        self._status_label.setStyleSheet("color: blue;")
        QApplication.processEvents()

        mw._selected_window = mw._window_manager.refresh_window_info(mw._selected_window)
        if not mw._selected_window:
            self._status_label.setText(tr("area.window_closed"))
            self._status_label.setStyleSheet("color: red;")
            return

        if not self._chat_input:
            self._chat_input = ChatInput()

        areas = self._chat_input.detect_areas(mw._selected_window)

        if areas:
            mw._detected_areas = AreaDetectionResult(
                chat_area_rect=areas.chat_rect,
                input_area_rect=areas.input_rect,
                method=areas.method,
                confidence=areas.confidence,
            )
            mw._manual_send_btn_pos = areas.send_button

            ss = mw._screenshot_reader.capture_window(mw._selected_window)
            if ss:
                self._show_screenshot_with_areas(
                    mw._screenshot_reader.image_to_bytes(ss),
                    mw._detected_areas,
                )

            method_display = "OCR" if areas.method == "ocr" else "启发式"
            self._status_label.setText(
                f"检测完成 ({method_display}, {areas.confidence:.0%})\n"
                f"对话区域: {areas.chat_rect}\n"
                f"输入区域: {areas.input_rect}\n"
                f"发送按钮: {areas.send_button}"
            )
            self._status_label.setStyleSheet("color: green;")
            self._clear_btn.setVisible(True)
            self._test_btn.setVisible(True)
        else:
            self._status_label.setText(tr("area.detection_failed"))
            self._status_label.setStyleSheet("color: red;")

    def _on_capture(self) -> None:
        """Capture screenshot and detect areas."""
        mw = self.main_window
        if not mw._selected_window:
            return

        mw._selected_window = mw._window_manager.refresh_window_info(mw._selected_window)
        if not mw._selected_window:
            return

        if not mw._screenshot_reader.has_ocr():
            self._info_label.setText(tr("area.warning_no_ocr"))

        detector = ChatAreaDetector(mw._screenshot_reader)
        mw._detected_areas = detector.detect_areas(mw._selected_window)

        ss, _ = mw._screenshot_reader.capture_and_extract(mw._selected_window)
        if ss:
            self._show_screenshot_with_areas(
                mw._screenshot_reader.image_to_bytes(ss), mw._detected_areas
            )
            method = mw._detected_areas.method
            conf = f"{mw._detected_areas.confidence:.0%}"
            self._info_label.setText(tr("area.detection.method", method=method, confidence=conf))

    def _on_area_select(self, purpose: str) -> None:
        """Request manual area selection via overlay."""
        self.area_selection_requested.emit(purpose)

    def _on_clear(self) -> None:
        """Clear all manual area selections."""
        mw = self.main_window
        mw._manual_chat_rect = None
        mw._manual_input_rect = None
        mw._manual_send_btn_pos = None
        mw._detected_areas = None
        self._clear_btn.setVisible(False)
        self._status_label.setText("")
        self.update_translations()

        if mw._selected_window:
            ss = mw._screenshot_reader.capture_window(mw._selected_window)
            if ss:
                self._show_screenshot_raw(mw._screenshot_reader.image_to_bytes(ss))

    def on_area_selected(self, purpose: str, rect: tuple[int, int, int, int]) -> None:
        """Handle area selection result from overlay."""
        mw = self.main_window
        left, top, right, bottom = rect

        if purpose == "chat":
            mw._manual_chat_rect = rect
        elif purpose == "input":
            mw._manual_input_rect = rect
        elif purpose == "send":
            cx, cy = (left + right) // 2, (top + bottom) // 2
            mw._manual_send_btn_pos = (cx, cy)

        has_any = bool(mw._manual_chat_rect or mw._manual_input_rect or mw._manual_send_btn_pos)
        self._clear_btn.setVisible(has_any)
        self.update_translations()
        self._refresh_area_display()

    def _refresh_area_display(self) -> None:
        """Refresh screenshot with current area selections."""
        mw = self.main_window
        if not mw._selected_window:
            return

        ss = mw._screenshot_reader.capture_window(mw._selected_window)
        if not ss:
            return

        png = mw._screenshot_reader.image_to_bytes(ss)
        chat_r = mw._manual_chat_rect
        input_r = mw._manual_input_rect

        if chat_r and not input_r:
            input_r = (chat_r[0], chat_r[3], chat_r[2], chat_r[3] + 50)
        elif input_r and not chat_r:
            chat_r = (input_r[0], input_r[1] - 200, input_r[2], input_r[1])

        if chat_r and input_r:
            areas = AreaDetectionResult(
                chat_area_rect=chat_r,
                input_area_rect=input_r,
                method="manual",
                confidence=1.0,
            )
            self._show_screenshot_with_areas(png, areas)
            self._info_label.setText(
                tr("area.detection.method", method="manual", confidence="100%")
            )
        else:
            self._show_screenshot_raw(png)

    def _show_screenshot_with_areas(self, png_data: bytes, areas: AreaDetectionResult) -> None:
        """Display screenshot with area overlays."""
        pixmap = QPixmap()
        pixmap.loadFromData(png_data)

        if pixmap.isNull():
            return

        scaled = pixmap.scaled(
            self._screenshot_label.width() - 20,
            self._screenshot_label.height() - 20,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )

        scale_x = scaled.width() / pixmap.width()
        scale_y = scaled.height() / pixmap.height()

        mw = self.main_window
        win_left = mw._selected_window.rect[0] if mw._selected_window else 0
        win_top = mw._selected_window.rect[1] if mw._selected_window else 0

        painter = QPainter(scaled)
        painter.setRenderHint(QPainter.Antialiasing)

        def draw_rect(rect, color, label):
            if not rect:
                return
            left, t, r, b = rect
            left = int((left - win_left) * scale_x)
            t = int((t - win_top) * scale_y)
            r = int((r - win_left) * scale_x)
            b = int((b - win_top) * scale_y)

            pen = QPen(color, 2)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(left, t, r - left, b - t)

            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawRect(left, t - 18, len(label) * 8 + 10, 18)
            painter.setPen(Qt.white)
            painter.drawText(left + 5, t - 4, label)

        draw_rect(areas.chat_area_rect, QColor(Qt.green), "Chat")
        draw_rect(areas.input_area_rect, QColor(Qt.blue), "Input")

        if mw._manual_send_btn_pos:
            sx, sy = mw._manual_send_btn_pos
            sx = int((sx - win_left) * scale_x)
            sy = int((sy - win_top) * scale_y)
            painter.setPen(QPen(QColor(Qt.red), 3))
            painter.drawLine(sx - 10, sy, sx + 10, sy)
            painter.drawLine(sx, sy - 10, sx, sy + 10)
            painter.drawEllipse(sx - 15, sy - 15, 30, 30)

        painter.end()
        self._screenshot_label.setPixmap(scaled)

    def _show_screenshot_raw(self, png_data: bytes) -> None:
        """Display screenshot without overlays."""
        pixmap = QPixmap()
        pixmap.loadFromData(png_data)

        if pixmap.isNull():
            return

        scaled = pixmap.scaled(
            self._screenshot_label.width() - 20,
            self._screenshot_label.height() - 20,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self._screenshot_label.setPixmap(scaled)

    def _on_test_send(self) -> None:
        """Test send functionality."""
        mw = self.main_window
        if not mw._selected_window:
            QMessageBox.warning(self, tr("dialog.warning_title"), tr("area.select_window_first"))
            return

        if not self._chat_input:
            self._chat_input = ChatInput()

        # 检测区域
        self._status_label.setText("检测区域...")
        QApplication.processEvents()

        areas = self._chat_input.detect_areas(mw._selected_window)

        self._status_label.setText(f"输入区域: {areas.input_rect}")
        QApplication.processEvents()

        # 发送测试消息
        test_msg = "【测试消息】"
        self._status_label.setText(f"发送: {test_msg}")
        QApplication.processEvents()

        success = self._chat_input.send_message(test_msg, mw._selected_window, method="enter")

        if success:
            self._status_label.setText("✅ 发送成功!")
            self._status_label.setStyleSheet("color: green;")
        else:
            self._status_label.setText("❌ 发送失败")
            self._status_label.setStyleSheet("color: red;")
