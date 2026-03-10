"""Knowledge Base selector widget."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr

logger = logging.getLogger(__name__)


class KBSelectorWidget(QWidget):
    """Compact KB selector for embedding in other pages."""

    kb_selection_changed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._kb_enabled = False
        self._selected_kbs: list[str] = []
        self._available_kbs: list[dict] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._enable_checkbox = QCheckBox(tr("kb.use_kb"))
        self._enable_checkbox.stateChanged.connect(self._on_enable_changed)
        layout.addWidget(self._enable_checkbox)

        self._kb_combo = QComboBox()
        self._kb_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents
        )
        self._kb_combo.setEnabled(False)
        self._kb_combo.currentTextChanged.connect(self._on_kb_selected)
        layout.addWidget(self._kb_combo)

        self._more_btn = QPushButton(tr("kb.more_options"))
        self._more_btn.clicked.connect(self._show_more_options)
        layout.addWidget(self._more_btn)

        self._status_label = QLabel()
        self._status_label.setStyleSheet("color: gray; font-size: 12px;")
        layout.addWidget(self._status_label, 1)

        self.setLayout(layout)
        self._update_status()

    def _on_enable_changed(self, state: int) -> None:
        self._kb_enabled = state == Qt.CheckState.Checked.value
        self._kb_combo.setEnabled(self._kb_enabled)
        self.kb_selection_changed.emit(
            self._selected_kbs if self._kb_enabled else []
        )
        self._update_status()

    def _on_kb_selected(self, text: str) -> None:
        if text == "All KBs":
            self._selected_kbs = []
        else:
            self._selected_kbs = [text.split(" (")[0]]
        self.kb_selection_changed.emit(
            self._selected_kbs if self._kb_enabled else []
        )

    def _show_more_options(self) -> None:
        dialog = KBMultiSelectDialog(
            self._available_kbs, self._selected_kbs, self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._selected_kbs = dialog.get_selected_kbs()
            self.kb_selection_changed.emit(
                self._selected_kbs if self._kb_enabled else []
            )
            self._update_status()

    def _update_status(self) -> None:
        if not self._kb_enabled:
            self._status_label.setText(tr("kb.disabled"))
        elif not self._selected_kbs:
            self._status_label.setText(tr("kb.searching_all"))
        else:
            self._status_label.setText(
                f"{len(self._selected_kbs)} KB(s) selected"
            )

    def set_available_kbs(self, kbs: list[dict]) -> None:
        self._available_kbs = kbs
        self._kb_combo.clear()
        self._kb_combo.addItem("All KBs")
        for kb in kbs:
            self._kb_combo.addItem(
                f"{kb['name']} ({kb.get('doc_count', '?')})"
            )

    def get_selected_kbs(self) -> list[str]:
        return self._selected_kbs if self._kb_enabled else []

    def is_kb_enabled(self) -> bool:
        return self._kb_enabled


class KBMultiSelectDialog(QDialog):
    """Dialog for selecting multiple KBs."""

    def __init__(self, kbs: list[dict], selected: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("kb.select_kbs"))
        self.setModal(True)
        self.setMinimumWidth(400)
        self._available_kbs = kbs
        self._initial_selected = selected
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        label = QLabel(tr("kb.select_multiple_instructions"))
        label.setWordWrap(True)
        layout.addWidget(label)

        self._list_widget = QListWidget()
        self._list_widget.setSelectionMode(
            QListWidget.SelectionMode.MultiSelection
        )
        for kb in self._available_kbs:
            doc_count = kb.get("doc_count", "?")
            text = f"{kb['name']} ({doc_count} docs)"
            item = QListWidgetItem(text)
            if kb["name"] in self._initial_selected:
                item.setSelected(True)
            self._list_widget.addItem(item)
        layout.addWidget(self._list_widget)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_selected_kbs(self) -> list[str]:
        return [
            item.text().split(" (")[0]
            for item in self._list_widget.selectedItems()
        ]
