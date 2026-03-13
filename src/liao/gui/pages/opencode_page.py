"""OpenCode integration page."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .base_page import BasePage
from ..i18n import tr
from ...opencode import OpenCodeClient
from ...opencode.client import get_opencode_info

if TYPE_CHECKING:
    from ..main_window import MainWindow

logger = logging.getLogger(__name__)


class OpenCodePage(BasePage):
    """Page for OpenCode integration."""

    session_selected = Signal(str)

    def __init__(self, main_window: MainWindow, parent: QWidget | None = None):
        self._client: OpenCodeClient | None = None
        self._sessions: list = []
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._refresh_sessions)
        super().__init__(main_window, parent)

    def _build_ui(self) -> None:
        root = self._layout

        # Status section
        self._status_group = QGroupBox()
        root.addWidget(self._status_group)
        status_layout = QVBoxLayout(self._status_group)

        self._status_label = QLabel()
        self._status_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        status_layout.addWidget(self._status_label)

        self._cli_info_label = QLabel()
        self._cli_info_label.setStyleSheet("color: gray; font-size: 11px;")
        status_layout.addWidget(self._cli_info_label)

        # Main content
        content = QWidget()
        root.addWidget(content, 1)
        content_layout = QHBoxLayout(content)

        # Left: Sessions
        sessions_group = QGroupBox()
        sessions_layout = QVBoxLayout(sessions_group)
        content_layout.addWidget(sessions_group)

        header = QHBoxLayout()
        self._refresh_btn = QPushButton(tr("opencode.refresh"))
        self._refresh_btn.clicked.connect(self._refresh_sessions)
        header.addWidget(self._refresh_btn)
        header.addStretch()
        sessions_layout.addLayout(header)

        self._session_list = QListWidget()
        self._session_list.itemClicked.connect(self._on_session_clicked)
        sessions_layout.addWidget(self._session_list)

        self._session_count_label = QLabel()
        self._session_count_label.setAlignment(Qt.AlignCenter)
        sessions_layout.addWidget(self._session_count_label)

        # Right: Details
        details_group = QGroupBox()
        details_layout = QVBoxLayout(details_group)
        content_layout.addWidget(details_group, 1)

        self._details_text = QTextEdit()
        self._details_text.setReadOnly(True)
        self._details_text.setFont(QFont("Courier", 10))
        details_layout.addWidget(self._details_text)

        self._update_status()

    def update_translations(self) -> None:
        self._status_group.setTitle(tr("opencode.connection"))
        self._refresh_btn.setText(tr("opencode.refresh"))

    def on_enter(self) -> None:
        self._update_status()
        if self._client and self._client.is_available():
            self._refresh_sessions()

    def on_leave(self) -> None:
        self._refresh_timer.stop()

    def _update_status(self) -> None:
        """Update status display."""
        info = get_opencode_info()

        if info["available"]:
            self._status_label.setText(tr("opencode.status.connected"))
            self._status_label.setStyleSheet("color: green; font-size: 14px; font-weight: bold;")

            server = (
                tr("opencode.server_running")
                if info["server_running"]
                else tr("opencode.server_not_running")
            )
            port = f" (port {info['server_port']})" if info["server_port"] else ""
            version = f" v{info['version']}" if info.get("version") else ""

            self._cli_info_label.setText(f"{info['cli_path']}{version}\n{server}{port}")
            self._refresh_btn.setEnabled(True)

            if not self._client:
                self._client = OpenCodeClient()
        else:
            self._status_label.setText(tr("opencode.not_installed"))
            self._status_label.setStyleSheet("color: orange; font-size: 14px; font-weight: bold;")
            self._cli_info_label.setText(tr("opencode.install_hint"))
            self._refresh_btn.setEnabled(False)

    def _refresh_sessions(self) -> None:
        """Refresh session list."""
        if not self._client or not self._client.is_available():
            return

        try:
            self._sessions = self._client.list_sessions()
            self._session_list.clear()

            for session in self._sessions:
                title = getattr(session, "title", None) or "Untitled"
                item = QListWidgetItem(title)
                item.setData(Qt.ItemDataRole.UserRole, session.id)
                self._session_list.addItem(item)

            count = len(self._sessions)
            self._session_count_label.setText(tr("opencode.sessions_found").format(count=count))

        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            self._session_count_label.setText(tr("opencode.refresh_failed"))

    def _on_session_clicked(self, item: QListWidgetItem) -> None:
        """Show session details."""
        session_id = item.data(Qt.ItemDataRole.UserRole)
        self._show_session_details(session_id)

    def _show_session_details(self, session_id: str) -> None:
        """Display session details."""
        if not self._client:
            return

        try:
            data = self._client.export_session(session_id)
            if data:
                self._details_text.setPlainText(json.dumps(data, indent=2, ensure_ascii=False))
            else:
                self._details_text.setPlainText(tr("opencode.export_failed"))
        except Exception as e:
            self._details_text.setPlainText(str(e))

    def is_valid(self) -> bool:
        return True
