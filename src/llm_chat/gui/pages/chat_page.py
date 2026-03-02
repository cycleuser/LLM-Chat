"""Chat page - main automation workspace."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
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
        self._prompt_edit.setPlainText(
            "You are a friendly assistant. Respond naturally and briefly (1-3 sentences), "
            "like a real conversation. Match the other person's tone and style."
        )
        self._prompt_edit.setMaximumHeight(60)
        self._layout.addWidget(self._prompt_edit)
        
        # Settings row
        settings = QHBoxLayout()
        settings.setSpacing(15)
        
        self._rounds_label = QLabel()
        settings.addWidget(self._rounds_label)
        self._rounds_spin = QSpinBox()
        self._rounds_spin.setRange(1, 100)
        self._rounds_spin.setValue(5)
        settings.addWidget(self._rounds_spin)
        
        self._max_wait_label = QLabel()
        settings.addWidget(self._max_wait_label)
        self._max_wait_spin = QSpinBox()
        self._max_wait_spin.setRange(5, 300)
        self._max_wait_spin.setValue(60)
        settings.addWidget(self._max_wait_spin)
        
        settings.addStretch()
        
        # Action buttons
        self._start_btn = QPushButton()
        self._start_btn.clicked.connect(self._on_start)
        settings.addWidget(self._start_btn)
        
        self._stop_btn = QPushButton()
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._on_stop)
        settings.addWidget(self._stop_btn)
        
        self._layout.addLayout(settings)
        
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
        self._log_display.setMaximumHeight(100)
        log_layout.addWidget(self._log_display)
        splitter.addWidget(log_widget)
        
        splitter.setSizes([300, 100])
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
        self._rounds_label.setText(tr("chat.rounds"))
        self._max_wait_label.setText(tr("chat.max_wait"))
        self._start_btn.setText(tr("chat.start"))
        self._stop_btn.setText(tr("chat.stop"))
        self._conv_label.setText(tr("chat.conversation"))
        self._log_label.setText(tr("chat.log"))
        self._manual_label.setText(tr("manual.title"))
        self._manual_edit.setPlaceholderText(tr("manual.input_placeholder"))
        self._send_btn.setText(tr("manual.send"))
        
        mw = self.main_window
        if mw._selected_window:
            self._target_label.setText(f"Target: {mw._selected_window.title[:30]}")
    
    def on_enter(self) -> None:
        """Update target label when entering page."""
        mw = self.main_window
        if mw._selected_window:
            self._target_label.setText(f"Target: {mw._selected_window.title[:30]}")
        
        can_start = mw._llm_client is not None and mw._selected_window is not None
        self._start_btn.setEnabled(can_start)
    
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
        
        mw._auto_worker = AutoChatWorker(
            llm_client=mw._llm_client,
            window_manager=mw._window_manager,
            screenshot_reader=mw._screenshot_reader,
            window_info=mw._selected_window,
            prompt=prompt,
            rounds=self._rounds_spin.value(),
            max_wait_seconds=self._max_wait_spin.value(),
            manual_chat_rect=mw._manual_chat_rect,
            manual_input_rect=mw._manual_input_rect,
            manual_send_btn_pos=mw._manual_send_btn_pos,
        )
        
        worker = mw._auto_worker
        worker.message_generated.connect(lambda m: self._log(f"[Generated] {m}"))
        worker.message_sent.connect(lambda m: self._log(f"[Sent] {m}"))
        worker.token_streaming.connect(lambda t: self._log(f"[...] {t[-50:]}"))
        worker.reply_detected.connect(lambda t: self._log(f"[Reply] {t[:80]}..."))
        worker.status_update.connect(lambda m: self._log(f"[Status] {m}"))
        worker.error_occurred.connect(lambda m: self._log(f"[Error] {m}"))
        worker.round_completed.connect(lambda n: self._log(f"--- Round {n} completed ---"))
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
    
    def _on_manual_send(self) -> None:
        """Send manual message."""
        mw = self.main_window
        text = self._manual_edit.text().strip()
        if not text or not mw._selected_window:
            return
        
        self._manual_edit.clear()
        
        from ...core.input_simulator import click_and_type, send_enter, focus_window_hard
        
        input_rect = mw._manual_input_rect
        if not input_rect and mw._detected_areas:
            input_rect = mw._detected_areas.input_area_rect
        
        if not input_rect:
            w = mw._selected_window
            cx = (w.rect[0] + w.rect[2]) // 2
            cy = w.rect[3] - 100
            input_rect = (cx - 100, cy - 20, cx + 100, cy + 20)
        
        focus_window_hard(mw._selected_window.hwnd)
        cx = (input_rect[0] + input_rect[2]) // 2
        cy = (input_rect[1] + input_rect[3]) // 2
        click_and_type(cx, cy, text)
        send_enter()
        
        self._log(f"[Manual] Sent: {text}")
