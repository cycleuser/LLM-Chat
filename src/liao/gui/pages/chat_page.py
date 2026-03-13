"""Chat page - main automation workspace."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr
from ..workers import AutoChatWorker
from .base_page import BasePage

if TYPE_CHECKING:
    from ..main_window import MainWindow


class ChatPage(BasePage):
    """Main automation workspace page."""

    automation_started = Signal()
    automation_stopped = Signal()

    def __init__(self, main_window: "MainWindow", parent: QWidget | None = None):
        super().__init__(main_window, parent)
        self._layout.setContentsMargins(20, 10, 20, 10)

    def _build_ui(self) -> None:
        """Build the chat page UI."""
        # Title row
        title_row = QHBoxLayout()
        self._title = QLabel()
        font = self._title.font()
        font.setPointSize(12)
        font.setBold(True)
        self._title.setFont(font)
        title_row.addWidget(self._title)
        title_row.addStretch()

        self._target_label = QLabel()
        title_row.addWidget(self._target_label)
        self._layout.addLayout(title_row)

        # Prompt section
        self._prompt_label = QLabel()
        self._layout.addWidget(self._prompt_label)

        self._prompt_edit = QPlainTextEdit()
        self._prompt_edit.setPlainText(tr("chat.prompt_default"))
        self._prompt_edit.setMaximumHeight(60)
        self._prompt_user_modified = False
        self._prompt_edit.textChanged.connect(self._on_prompt_changed)
        self._layout.addWidget(self._prompt_edit)

        # Settings section - two rows for better organization
        settings_layout = QVBoxLayout()
        settings_layout.setSpacing(8)

        # Row 1: Automation settings
        row1 = QHBoxLayout()
        row1.setSpacing(12)

        # Unlimited rounds checkbox
        self._unlimited_check = QCheckBox()
        self._unlimited_check.stateChanged.connect(self._on_unlimited_changed)
        row1.addWidget(self._unlimited_check)

        self._rounds_label = QLabel()
        row1.addWidget(self._rounds_label)
        self._rounds_spin = QSpinBox()
        self._rounds_spin.setRange(1, 100)
        self._rounds_spin.setValue(5)
        row1.addWidget(self._rounds_spin)

        self._max_wait_label = QLabel()
        row1.addWidget(self._max_wait_label)
        self._max_wait_spin = QSpinBox()
        self._max_wait_spin.setRange(5, 300)
        self._max_wait_spin.setValue(10)
        row1.addWidget(self._max_wait_spin)

        row1.addStretch()
        settings_layout.addLayout(row1)

        # Row 2: KB settings and action buttons
        row2 = QHBoxLayout()
        row2.setSpacing(12)

        # KB selector widget (if available)
        try:
            from ..widgets import KBSelectorWidget

            self._kb_selector = KBSelectorWidget()
            self._kb_selector.kb_selection_changed.connect(self._on_kb_selection_changed)
            row2.addWidget(self._kb_selector)
        except ImportError:
            self._kb_selector = None

        # Strict KB mode checkbox
        self._strict_mode_check = QCheckBox()
        self._strict_mode_check.setVisible(False)
        row2.addWidget(self._strict_mode_check)

        row2.addStretch()

        # Action buttons
        self._start_btn = QPushButton()
        self._start_btn.setMinimumWidth(100)
        self._start_btn.clicked.connect(self._on_start)
        row2.addWidget(self._start_btn)

        self._stop_btn = QPushButton()
        self._stop_btn.setEnabled(False)
        self._stop_btn.setMinimumWidth(100)
        self._stop_btn.clicked.connect(self._on_stop)
        row2.addWidget(self._stop_btn)

        settings_layout.addLayout(row2)
        self._layout.addLayout(settings_layout)

        # Warning label for missing tools (hidden by default)
        self._warning_label = QLabel()
        self._warning_label.setStyleSheet(
            "QLabel { color: #b45309; background: #fef3c7; "
            "border: 1px solid #f59e0b; border-radius: 4px; padding: 6px; }"
        )
        self._warning_label.setWordWrap(True)
        self._warning_label.setVisible(False)
        self._layout.addWidget(self._warning_label)

        # Splitter for conversation and logs
        splitter = QSplitter(Qt.Vertical)

        # Conversation display
        conv_widget = QWidget()
        conv_layout = QVBoxLayout(conv_widget)
        conv_layout.setContentsMargins(0, 5, 0, 0)

        self._conv_label = QLabel()
        conv_layout.addWidget(self._conv_label)

        self._conv_display = QTextEdit()
        self._conv_display.setReadOnly(True)
        conv_layout.addWidget(self._conv_display)
        splitter.addWidget(conv_widget)

        # Log display
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 5, 0, 0)

        self._log_label = QLabel()
        log_layout.addWidget(self._log_label)

        self._log_display = QTextEdit()
        self._log_display.setReadOnly(True)
        self._log_display.setMinimumHeight(120)
        log_layout.addWidget(self._log_display)
        splitter.addWidget(log_widget)

        # Default split: 70% conversation, 30% logs
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)
        self._layout.addWidget(splitter, 1)

        # Manual send section
        manual_layout = QHBoxLayout()
        manual_layout.setSpacing(10)

        self._manual_label = QLabel()
        manual_layout.addWidget(self._manual_label)

        self._manual_edit = QLineEdit()
        self._manual_edit.returnPressed.connect(self._on_manual_send)
        manual_layout.addWidget(self._manual_edit, 1)

        self._send_btn = QPushButton()
        self._send_btn.clicked.connect(self._on_manual_send)
        manual_layout.addWidget(self._send_btn)

        self._layout.addLayout(manual_layout)

        self.update_translations()

    def update_translations(self) -> None:
        """Update all translatable text."""
        self._title.setText(tr("chat.title"))
        self._prompt_label.setText(tr("chat.prompt_label"))
        self._prompt_edit.setPlaceholderText(tr("chat.prompt_placeholder"))
        # Update prompt text only if user hasn't customized it
        if not self._prompt_user_modified:
            self._prompt_edit.blockSignals(True)
            self._prompt_edit.setPlainText(tr("chat.prompt_default"))
            self._prompt_edit.blockSignals(False)
        self._unlimited_check.setText(tr("chat.unlimited"))
        self._rounds_label.setText(tr("chat.rounds"))
        self._max_wait_label.setText(tr("chat.max_wait"))
        self._start_btn.setText(tr("chat.start"))
        self._stop_btn.setText(tr("chat.stop"))
        self._strict_mode_check.setText(tr("chat.strict_mode"))
        self._conv_label.setText(tr("chat.conversation"))
        self._log_label.setText(tr("chat.log"))
        self._manual_label.setText(tr("manual.title"))
        self._manual_edit.setPlaceholderText(tr("manual.input_placeholder"))
        self._send_btn.setText(tr("manual.send"))

        mw = self.main_window
        if mw._selected_window:
            self._target_label.setText(f"Target: {mw._selected_window.title[:30]}")

    def _on_kb_selection_changed(self, selected_kbs: list[str]) -> None:
        """Handle KB selection change."""
        self._selected_kbs = selected_kbs

    def on_enter(self) -> None:
        """Update target label when entering page."""
        mw = self.main_window
        if mw._selected_window:
            self._target_label.setText(f"Target: {mw._selected_window.title[:30]}")

        can_start = mw._llm_client is not None and mw._selected_window is not None
        self._start_btn.setEnabled(can_start)

        # Populate KB selector from KB page config
        kb_config = mw._kb_config
        if self._kb_selector is not None and kb_config and kb_config.get("enabled"):
            self._strict_mode_check.setVisible(True)
            if kb_config.get("strict_mode"):
                self._strict_mode_check.setChecked(True)
            try:
                from liao.knowledge.kb_config import KBConfig
                from liao.knowledge.kb_manager import KBManager

                cfg = KBConfig(
                    chroma_dir=kb_config.get("chroma_dir", ""),
                    embedding_model=kb_config.get("embedding_model", "nomic-embed-text"),
                    ollama_url=kb_config.get("ollama_url", "http://localhost:11434"),
                )
                mgr = KBManager(cfg)
                kbs = mgr.list_kbs()
                if kbs:
                    self._kb_selector.set_available_kbs(kbs)
            except Exception:
                pass
        else:
            self._strict_mode_check.setVisible(False)

        # Show warnings for missing tools on Linux
        warnings = []
        if sys.platform == "linux":
            if not mw._screenshot_reader.has_ocr():
                warnings.append(tr("chat.warning_no_ocr"))
            from ...core.input_simulator import InputSimulator

            sim = InputSimulator()
            if not sim.is_available():
                warnings.append(tr("chat.warning_no_input"))
        if warnings:
            self._warning_label.setText("\n\n".join(warnings))
            self._warning_label.setVisible(True)
        else:
            self._warning_label.setVisible(False)

    def _on_start(self) -> None:
        """Start auto chat automation."""
        mw = self.main_window

        prompt = self._prompt_edit.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, tr("dialog.warning_title"), tr("dialog.no_prompt"))
            return

        if not mw._llm_client or not mw._selected_window:
            return

        mw._selected_window = mw._window_manager.refresh_window_info(mw._selected_window)
        if not mw._selected_window:
            QMessageBox.warning(self, tr("dialog.warning_title"), tr("dialog.window_closed"))
            return

        self._conv_display.clear()
        self._log_display.clear()

        # 完全依赖自动检测，忽略手动选择（手动选择坐标有问题）
        print(f"\n=== 启动自动化 ===")
        print(f"窗口位置: {mw._selected_window.rect}")
        print(f"使用自动检测区域")

        mw._auto_worker = AutoChatWorker(
            llm_client=mw._llm_client,
            window_manager=mw._window_manager,
            screenshot_reader=mw._screenshot_reader,
            window_info=mw._selected_window,
            prompt=prompt,
            rounds=999999 if self._unlimited_check.isChecked() else self._rounds_spin.value(),
            max_wait_seconds=self._max_wait_spin.value(),
            manual_chat_rect=None,  # 让 workflow 自动检测
            manual_input_rect=None,
            manual_send_btn_pos=None,
            kb_config=mw._kb_config,
            selected_kbs=getattr(self, "_selected_kbs", None),
            strict_mode=self._strict_mode_check.isChecked(),
        )

        worker = mw._auto_worker
        worker.message_generated.connect(lambda m: self._log(f"[Generated] {m}"))
        worker.message_sent.connect(lambda m: self._log(f"[Sent] {m}"))
        worker.token_streaming.connect(lambda t: self._log(f"[...] {t[-50:]}"))
        worker.reply_detected.connect(lambda t: self._log(f"[Reply] {t[:80]}..."))
        worker.status_update.connect(lambda m: self._log(f"[Status] {m}"))
        worker.error_occurred.connect(lambda m: self._log(f"[Error] {m}"))
        worker.round_completed.connect(lambda n: self._log(f"--- Round {n} completed ---"))
        worker.kb_status.connect(lambda m: self._log(f"[KB] {m}"))
        worker.conversation_log.connect(self._on_conv_log)
        worker.finished.connect(self._on_finished)

        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._prompt_edit.setEnabled(False)

        worker.start()
        self._log("[Status] Automation started")
        self.automation_started.emit()

    def _on_stop(self) -> None:
        """Stop auto chat automation."""
        mw = self.main_window
        if mw._auto_worker:
            mw._auto_worker.stop()
            self._log("[Status] Stopping...")
        self._stop_btn.setEnabled(False)

    def _on_finished(self) -> None:
        """Handle worker finished."""
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._prompt_edit.setEnabled(True)
        self._log("[Status] Automation finished")
        self.automation_stopped.emit()

    def _on_conv_log(self, html: str) -> None:
        """Update conversation display."""
        self._conv_display.setHtml(html)
        scrollbar = self._conv_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _log(self, text: str) -> None:
        """Add text to log display."""
        self._log_display.append(text)
        scrollbar = self._log_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_prompt_changed(self) -> None:
        """Track when user manually edits the prompt."""
        self._prompt_user_modified = True

    def _on_unlimited_changed(self, state: int) -> None:
        """Handle unlimited checkbox state change."""
        is_unlimited = state == Qt.Checked.value
        self._rounds_spin.setEnabled(not is_unlimited)
        self._rounds_label.setEnabled(not is_unlimited)

    def _on_manual_send(self) -> None:
        """Send manual message."""
        mw = self.main_window
        text = self._manual_edit.text().strip()
        if not text or not mw._selected_window:
            return

        self._manual_edit.clear()

        import time as _time
        from ...core.input_simulator import InputSimulator

        input_rect = mw._manual_input_rect
        if not input_rect and mw._detected_areas:
            input_rect = mw._detected_areas.input_area_rect

        if not input_rect:
            w = mw._selected_window
            cx = (w.rect[0] + w.rect[2]) // 2
            cy = w.rect[3] - 100
            input_rect = (cx - 100, cy - 20, cx + 100, cy + 20)

        hwnd = mw._selected_window.hwnd
        win_rect = mw._selected_window.rect
        sim = InputSimulator()

        cx = (input_rect[0] + input_rect[2]) // 2
        cy = (input_rect[1] + input_rect[3]) // 2
        sim.click_and_type(cx, cy, text, hwnd=hwnd, win_rect=win_rect)

        # Re-focus target window (Liao GUI updates may steal focus)
        _time.sleep(0.2)
        sim.focus_window(hwnd)
        _time.sleep(0.3)

        if mw._manual_send_btn_pos:
            bx, by = mw._manual_send_btn_pos
            sim.click_in_window(hwnd, win_rect[0], win_rect[1], bx, by)
        else:
            # Click estimated send button (bottom-right of input area)
            bx = input_rect[2] - 45
            by = input_rect[3] - 15
            sim.click_in_window(hwnd, win_rect[0], win_rect[1], bx, by)
            _time.sleep(0.3)
            # Also try Enter and Ctrl+Enter as fallbacks
            sim.click_in_window(hwnd, win_rect[0], win_rect[1], cx, cy)
            _time.sleep(0.1)
            sim.press_key("enter")
            _time.sleep(0.3)
            sim.hotkey("ctrl", "enter")

        self._log(f"[Manual] Sent: {text}")
