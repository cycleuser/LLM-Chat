"""Knowledge Base setup wizard page."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
)

from ..i18n import tr
from .base_page import BasePage
from .kb_settings_page import KBSettingsPage

if TYPE_CHECKING:
    from ..main_window import MainWindow

logger = logging.getLogger(__name__)


class KBPage(BasePage):
    """Wizard page for Knowledge Base configuration.

    Allows users to:
    - Configure ChromaDB connection (local or GangDan-compatible)
    - Select embedding model
    - Browse and select available knowledge bases
    - Upload markdown/text files to build new KBs
    - Toggle strict KB mode

    This page is optional -- users can skip it and proceed to Chat.
    """

    def __init__(self, main_window: "MainWindow"):
        super().__init__(main_window)

    def _build_ui(self) -> None:
        # Title
        self._title_label = QLabel(tr("kb_page.title"))
        font = self._title_label.font()
        font.setPointSize(16)
        font.setBold(True)
        self._title_label.setFont(font)
        self._layout.addWidget(self._title_label)

        # Subtitle
        self._subtitle_label = QLabel(tr("kb_page.subtitle"))
        self._subtitle_label.setWordWrap(True)
        self._subtitle_label.setStyleSheet("color: gray;")
        self._layout.addWidget(self._subtitle_label)

        # Embedded KB settings widget
        self._kb_settings = KBSettingsPage()
        self._layout.addWidget(self._kb_settings, 1)

        # Upload documents button row
        btn_row = QHBoxLayout()
        self._upload_btn = QPushButton(tr("kb_page.upload_documents"))
        self._upload_btn.clicked.connect(self._on_upload_documents)
        btn_row.addWidget(self._upload_btn)
        btn_row.addStretch()
        self._layout.addLayout(btn_row)

    def update_translations(self) -> None:
        self._title_label.setText(tr("kb_page.title"))
        self._subtitle_label.setText(tr("kb_page.subtitle"))
        self._upload_btn.setText(tr("kb_page.upload_documents"))

    def is_valid(self) -> bool:
        return True

    def on_enter(self) -> None:
        # Restore config from main window if previously saved
        if self._main_window._kb_config is not None:
            self._kb_settings.set_kb_config(self._main_window._kb_config)

        # Try to populate KB list
        self._try_populate_kb_list()

    def on_leave(self) -> None:
        # Persist config to main window state
        self._main_window._kb_config = self._kb_settings.get_kb_config()

    def _try_populate_kb_list(self) -> None:
        """Attempt to list available KBs from ChromaDB."""
        config = self._kb_settings.get_kb_config()
        chroma_dir = config.get("chroma_dir", "")
        if not chroma_dir:
            return

        try:
            from liao.knowledge.kb_config import KBConfig
            from liao.knowledge.kb_manager import KBManager

            kb_config = KBConfig(
                chroma_dir=chroma_dir,
                embedding_model=config.get("embedding_model", "nomic-embed-text"),
                ollama_url=config.get("ollama_url", "http://localhost:11434"),
            )
            manager = KBManager(kb_config)
            kbs = manager.list_kbs()
            if kbs:
                self._kb_settings.populate_kb_list(kbs)
        except Exception as e:
            logger.debug(f"Could not populate KB list: {e}")

    def _on_upload_documents(self) -> None:
        """Open the upload dialog."""
        try:
            from ..widgets.kb_upload_dialog import KBUploadDialog

            dialog = KBUploadDialog(self)
            if dialog.exec():
                # Refresh KB list after upload
                self._try_populate_kb_list()
        except Exception as e:
            logger.error(f"Failed to open upload dialog: {e}")
