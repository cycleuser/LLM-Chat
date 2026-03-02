"""Base page class for wizard pages."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout

if TYPE_CHECKING:
    from ..main_window import MainWindow


class BasePage(QWidget):
    """Abstract base class for wizard pages.
    
    All page widgets inherit from this class and implement:
    - _build_ui(): Create the page's UI elements
    - update_translations(): Update all translatable text
    - is_valid(): Check if navigation to next page is allowed
    """
    
    # Signal emitted when page validity changes
    validity_changed = Signal(bool)
    
    def __init__(self, main_window: "MainWindow", parent: QWidget | None = None):
        super().__init__(parent)
        self._main_window = main_window
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(40, 20, 40, 20)
        self._layout.setSpacing(16)
        self._build_ui()
    
    @property
    def main_window(self) -> "MainWindow":
        """Access to main window for shared state."""
        return self._main_window
    
    @abstractmethod
    def _build_ui(self) -> None:
        """Build the page's UI. Must be implemented by subclasses."""
        pass
    
    @abstractmethod
    def update_translations(self) -> None:
        """Update all translatable text. Must be implemented by subclasses."""
        pass
    
    def is_valid(self) -> bool:
        """Check if this page allows navigation to next page.
        
        Override in subclasses that need validation.
        Default returns True (no validation required).
        """
        return True
    
    def on_enter(self) -> None:
        """Called when user navigates to this page.
        
        Override to perform actions when page becomes visible.
        """
        pass
    
    def on_leave(self) -> None:
        """Called when user navigates away from this page.
        
        Override to perform cleanup or save state.
        """
        pass
    
    def _emit_validity_changed(self) -> None:
        """Emit validity_changed signal with current validity state."""
        self.validity_changed.emit(self.is_valid())
