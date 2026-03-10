"""Knowledge Base settings page."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr

if TYPE_CHECKING:
    from ..main_window import MainWindow

logger = logging.getLogger(__name__)


class KBSettingsPage(QWidget):
    """Knowledge Base configuration and management widget.

    Can be used standalone inside a QDialog or embedded in other layouts.
    """

    kb_config_changed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._kb_enabled = False
        self._chroma_dir = ""
        self._embedding_model = "nomic-embed-text"
        self._ollama_url = "http://localhost:11434"
        self._strict_mode = False
        self._selected_kbs: list[str] = []
        self._available_kbs: list[dict] = []

        self._build_ui()

    # ── UI Construction ───────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Enable KB
        self._enable_kb_checkbox = QCheckBox(tr("kb.enable_kb"))
        self._enable_kb_checkbox.stateChanged.connect(self._on_enable_kb_changed)
        layout.addWidget(self._enable_kb_checkbox)

        # Connection settings
        layout.addWidget(self._create_connection_group())

        # KB selection
        layout.addWidget(self._create_kb_selection_group())

        # Strict mode
        layout.addWidget(self._create_strict_mode_group())

        # Action buttons
        layout.addLayout(self._create_action_buttons())

        layout.addStretch()

    def _create_connection_group(self) -> QGroupBox:
        group = QGroupBox(tr("kb.connection_settings"))
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # ChromaDB directory
        row = QHBoxLayout()
        row.addWidget(QLabel(tr("kb.chroma_dir_label")))
        self._chroma_dir_edit = QLineEdit()
        self._chroma_dir_edit.setPlaceholderText("~/GangDan/data/chroma")
        self._chroma_dir_edit.textChanged.connect(self._on_chroma_dir_changed)
        row.addWidget(self._chroma_dir_edit, 1)
        browse_btn = QPushButton(tr("kb.browse"))
        browse_btn.clicked.connect(self._browse_chroma_dir)
        row.addWidget(browse_btn)
        layout.addLayout(row)

        # Embedding model
        row2 = QHBoxLayout()
        row2.addWidget(QLabel(tr("kb.embedding_model")))
        self._embedding_model_combo = QComboBox()
        self._embedding_model_combo.addItems([
            "nomic-embed-text",
            "mxbai-embed-large",
            "all-minilm",
            "snowflake-arctic-embed",
        ])
        self._embedding_model_combo.currentTextChanged.connect(
            self._on_embedding_model_changed
        )
        row2.addWidget(self._embedding_model_combo, 1)
        layout.addLayout(row2)

        # Ollama URL
        row3 = QHBoxLayout()
        row3.addWidget(QLabel(tr("kb.ollama_url")))
        self._ollama_url_edit = QLineEdit("http://localhost:11434")
        self._ollama_url_edit.textChanged.connect(self._on_ollama_url_changed)
        row3.addWidget(self._ollama_url_edit, 1)
        layout.addLayout(row3)

        group.setLayout(layout)
        return group

    def _create_kb_selection_group(self) -> QGroupBox:
        group = QGroupBox(tr("kb.select_kbs"))
        layout = QVBoxLayout()

        self._kb_list_widget = QListWidget()
        self._kb_list_widget.setSelectionMode(
            QListWidget.SelectionMode.MultiSelection
        )
        self._kb_list_widget.itemSelectionChanged.connect(
            self._on_kb_selection_changed
        )
        self._kb_list_widget.setMinimumHeight(150)
        layout.addWidget(self._kb_list_widget)

        btn_row = QHBoxLayout()
        self._refresh_kb_btn = QPushButton(tr("kb.refresh_kbs"))
        self._refresh_kb_btn.clicked.connect(self._refresh_kb_list)
        btn_row.addWidget(self._refresh_kb_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        group.setLayout(layout)
        return group

    def _create_strict_mode_group(self) -> QGroupBox:
        group = QGroupBox(tr("kb.strict_mode_settings"))
        layout = QVBoxLayout()

        self._strict_mode_checkbox = QCheckBox(tr("kb.enable_strict_mode"))
        self._strict_mode_checkbox.stateChanged.connect(
            self._on_strict_mode_changed
        )
        layout.addWidget(self._strict_mode_checkbox)

        desc = QLabel(tr("kb.strict_mode_description"))
        desc.setWordWrap(True)
        desc.setStyleSheet("color: gray; font-size: 12px;")
        layout.addWidget(desc)

        group.setLayout(layout)
        return group

    def _create_action_buttons(self) -> QHBoxLayout:
        layout = QHBoxLayout()

        self._test_btn = QPushButton(tr("kb.test_connection"))
        self._test_btn.clicked.connect(self._test_connection)
        layout.addWidget(self._test_btn)

        self._import_btn = QPushButton(tr("kb.import_from_gangdan"))
        self._import_btn.clicked.connect(self._import_from_gangdan)
        layout.addWidget(self._import_btn)

        layout.addStretch()
        return layout

    # ── Slots ─────────────────────────────────────────────────────────

    def _on_enable_kb_changed(self, state: int) -> None:
        self._kb_enabled = state == Qt.CheckState.Checked.value
        self.kb_config_changed.emit()

    def _on_chroma_dir_changed(self, text: str) -> None:
        self._chroma_dir = text
        self.kb_config_changed.emit()

    def _on_embedding_model_changed(self, text: str) -> None:
        self._embedding_model = text
        self.kb_config_changed.emit()

    def _on_ollama_url_changed(self, text: str) -> None:
        self._ollama_url = text
        self.kb_config_changed.emit()

    def _on_kb_selection_changed(self) -> None:
        items = self._kb_list_widget.selectedItems()
        self._selected_kbs = [item.text().split(" (")[0] for item in items]
        self.kb_config_changed.emit()

    def _on_strict_mode_changed(self, state: int) -> None:
        self._strict_mode = state == Qt.CheckState.Checked.value
        self.kb_config_changed.emit()

    # ── Actions ───────────────────────────────────────────────────────

    def _browse_chroma_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(
            self, tr("kb.select_chroma_dir"), str(Path.home())
        )
        if d:
            self._chroma_dir_edit.setText(d)

    def _refresh_kb_list(self) -> None:
        logger.info("Refreshing KB list...")

    def _test_connection(self) -> None:
        logger.info("Testing ChromaDB connection...")

    def _import_from_gangdan(self) -> None:
        default = Path.home() / "GangDan" / "data" / "chroma"
        if default.exists():
            self._chroma_dir_edit.setText(str(default))
            self._refresh_kb_list()

    # ── Public API ────────────────────────────────────────────────────

    def get_kb_config(self) -> dict:
        return {
            "enabled": self._kb_enabled,
            "chroma_dir": self._chroma_dir or str(
                Path.home() / ".liao" / "kb" / "chroma"
            ),
            "embedding_model": self._embedding_model,
            "ollama_url": self._ollama_url,
            "strict_mode": self._strict_mode,
            "kb_scope": self._selected_kbs,
        }

    def set_kb_config(self, config: dict) -> None:
        self._kb_enabled = config.get("enabled", False)
        self._enable_kb_checkbox.setChecked(self._kb_enabled)
        self._chroma_dir = config.get("chroma_dir", "")
        self._chroma_dir_edit.setText(self._chroma_dir)
        self._embedding_model = config.get("embedding_model", "nomic-embed-text")
        self._embedding_model_combo.setCurrentText(self._embedding_model)
        self._ollama_url = config.get("ollama_url", "http://localhost:11434")
        self._ollama_url_edit.setText(self._ollama_url)
        self._strict_mode = config.get("strict_mode", False)
        self._strict_mode_checkbox.setChecked(self._strict_mode)
        self._selected_kbs = config.get("kb_scope", [])

    def populate_kb_list(self, kbs: list[dict]) -> None:
        self._kb_list_widget.clear()
        self._available_kbs = kbs
        for kb in kbs:
            doc_count = kb.get("doc_count", "?")
            text = f"{kb['name']} ({doc_count} docs)"
            item = QListWidgetItem(text)
            self._kb_list_widget.addItem(item)
            if kb["name"] in self._selected_kbs:
                item.setSelected(True)
