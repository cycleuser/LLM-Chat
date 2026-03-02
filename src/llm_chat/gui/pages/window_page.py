"""Window selection page."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
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
from ...models.window import WindowInfo
from .base_page import BasePage

if TYPE_CHECKING:
    from ..main_window import MainWindow


class WindowPage(BasePage):
    """Page for selecting target window."""
    
    window_selected = Signal(object)
    
    def __init__(self, main_window: "MainWindow", parent: QWidget | None = None):
        self._window_list: list[WindowInfo] = []
        super().__init__(main_window, parent)
    
    def _build_ui(self) -> None:
        """Build the window selection page UI."""
        content = QWidget()
        content.setMaximumWidth(600)
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(16)
        
        # Title
        self._title = QLabel()
        font = self._title.font()
        font.setPointSize(14)
        font.setBold(True)
        self._title.setFont(font)
        content_layout.addWidget(self._title)
        
        # Subtitle
        self._subtitle = QLabel()
        content_layout.addWidget(self._subtitle)
        
        # Controls row
        controls = QHBoxLayout()
        self._refresh_btn = QPushButton()
        self._refresh_btn.clicked.connect(self._refresh_windows)
        controls.addWidget(self._refresh_btn)
        
        self._filter_edit = QLineEdit()
        self._filter_edit.textChanged.connect(self._filter_windows)
        controls.addWidget(self._filter_edit)
        content_layout.addLayout(controls)
        
        # Window list
        self._window_list_widget = QListWidget()
        self._window_list_widget.setMinimumHeight(250)
        self._window_list_widget.itemDoubleClicked.connect(self._on_window_selected)
        content_layout.addWidget(self._window_list_widget)
        
        # Selected window indicator
        self._selected_label = QLabel()
        content_layout.addWidget(self._selected_label)
        
        # Center content
        self._layout.addStretch()
        center_layout = QHBoxLayout()
        center_layout.addStretch()
        center_layout.addWidget(content)
        center_layout.addStretch()
        self._layout.addLayout(center_layout)
        self._layout.addStretch()
        
        self.update_translations()
    
    def update_translations(self) -> None:
        """Update all translatable text."""
        self._title.setText(tr("window.title"))
        self._subtitle.setText(tr("window.subtitle"))
        self._refresh_btn.setText(tr("window.refresh"))
        self._filter_edit.setPlaceholderText(tr("window.filter"))
        
        if self.main_window._selected_window:
            self._selected_label.setText(
                tr("window.selected", name=self.main_window._selected_window.title)
            )
        else:
            self._selected_label.setText(tr("window.none_selected"))
    
    def is_valid(self) -> bool:
        """Window page is valid when a window is selected."""
        return self.main_window._selected_window is not None
    
    def on_enter(self) -> None:
        """Refresh windows when entering page."""
        if not self._window_list:
            self._refresh_windows()
    
    def _refresh_windows(self) -> None:
        """Refresh the window list."""
        self._window_list = self.main_window._window_manager.get_all_visible_windows()
        self._show_windows()
    
    def _show_windows(self, filter_text: str = "") -> None:
        """Display windows in the list widget."""
        self._window_list_widget.clear()
        f = filter_text.lower()
        
        for w in self._window_list:
            if f and f not in w.title.lower():
                continue
            tag = f"[{w.app_type}] " if w.app_type != "other" else ""
            item = QListWidgetItem(f"{tag}{w.title}")
            item.setData(Qt.UserRole, w.hwnd)
            self._window_list_widget.addItem(item)
    
    def _filter_windows(self, text: str) -> None:
        """Filter the window list by text."""
        self._show_windows(text)
    
    def _on_window_selected(self, item: QListWidgetItem) -> None:
        """Handle window selection."""
        hwnd = item.data(Qt.UserRole)
        for w in self._window_list:
            if w.hwnd == hwnd:
                self.main_window._selected_window = w
                self.main_window._detected_areas = None
                self.main_window._manual_chat_rect = None
                self.main_window._manual_input_rect = None
                self.main_window._manual_send_btn_pos = None
                break
        
        if self.main_window._selected_window:
            self._selected_label.setText(
                tr("window.selected", name=self.main_window._selected_window.title)
            )
            self._emit_validity_changed()
            self.window_selected.emit(self.main_window._selected_window)
