"""Area selection overlay widget."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

from .i18n import tr


class AreaSelectionOverlay(QWidget):
    """Transparent full-screen overlay for manual area selection.
    
    Allows users to draw rectangles to select chat area, input area,
    or click to select send button position.
    
    Signals:
        area_selected: Emitted when area is selected (tuple: left, top, right, bottom)
        selection_cancelled: Emitted when selection is cancelled
    """

    area_selected = Signal(tuple)
    selection_cancelled = Signal()

    def __init__(
        self,
        target_window_rect: tuple[int, int, int, int] | None = None,
        purpose: str = "chat",
        existing_rects: dict[str, tuple[int, int, int, int] | None] | None = None,
        parent: QWidget | None = None,
    ):
        """Initialize overlay.
        
        Args:
            target_window_rect: Target window bounds to highlight
            purpose: Selection purpose ("chat", "input", or "send")
            existing_rects: Previously selected rects to display
            parent: Parent widget
        """
        super().__init__(parent)
        self._start_global: QPoint | None = None
        self._current_global: QPoint | None = None
        self._is_selecting = False
        self._target_rect = target_window_rect
        self._purpose = purpose
        self._existing_rects = existing_rects or {}
        
        # Get DPI scale factor
        screen = QApplication.primaryScreen()
        self._dpr = screen.devicePixelRatio() if screen else 1.0
        
        # Setup window
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setCursor(QCursor(Qt.CrossCursor))
        
        if screen:
            self.setGeometry(screen.geometry())

    def paintEvent(self, event):
        """Paint the overlay."""
        painter = QPainter(self)
        
        # Semi-transparent background
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        dpr = self._dpr

        # Draw target window outline
        if self._target_rect:
            t_left, t_top, t_right, t_bottom = self._target_rect
            wp = self.mapFromGlobal(QPoint(int(t_left / dpr), int(t_top / dpr)))
            painter.setPen(QPen(QColor(255, 255, 0), 2, Qt.DashLine))
            painter.drawRect(QRect(
                wp.x(), wp.y(),
                int((t_right - t_left) / dpr), int((t_bottom - t_top) / dpr)
            ))

        # Draw existing selections
        for name, rect in self._existing_rects.items():
            if rect is None:
                continue
            rl, rt, rr, rb = rect
            p1 = self.mapFromGlobal(QPoint(int(rl / dpr), int(rt / dpr)))
            r = QRect(p1.x(), p1.y(), int((rr - rl) / dpr), int((rb - rt) / dpr))
            
            color_map = {
                "chat": QColor(0, 200, 0),
                "input": QColor(0, 150, 255),
                "send": QColor(255, 165, 0),
            }
            color = color_map.get(name, QColor(200, 200, 200))
            painter.setPen(QPen(color, 2, Qt.DashLine))
            painter.drawRect(r)

        # Draw current selection
        if self._start_global and self._current_global:
            sl = self.mapFromGlobal(self._start_global)
            cl = self.mapFromGlobal(self._current_global)
            r = QRect(sl, cl).normalized()
            
            # Clear selection area
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(r, Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            
            # Draw selection border
            color_map = {
                "chat": QColor(0, 200, 0),
                "input": QColor(0, 150, 255),
            }
            color = color_map.get(self._purpose, QColor(255, 165, 0))
            painter.setPen(QPen(color, 3, Qt.SolidLine))
            painter.drawRect(r)
            
            # Draw size label
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(
                r.bottomRight() + QPoint(-80, 20),
                f"{r.width()} x {r.height()}"
            )

        # Draw hint text
        painter.setPen(QColor(255, 255, 255))
        hint_key = {
            "chat": "overlay.chat_hint",
            "input": "overlay.input_hint",
            "send": "overlay.send_hint",
        }.get(self._purpose, "overlay.chat_hint")
        painter.drawText(20, 30, tr(hint_key))
        
        painter.end()

    def mousePressEvent(self, event):
        """Handle mouse press."""
        if event.button() == Qt.LeftButton:
            self._start_global = event.globalPosition().toPoint()
            self._current_global = self._start_global
            self._is_selecting = True
            self.update()

    def mouseMoveEvent(self, event):
        """Handle mouse move."""
        if self._is_selecting:
            self._current_global = event.globalPosition().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        """Handle mouse release."""
        if event.button() == Qt.LeftButton and self._is_selecting:
            self._is_selecting = False
            
            if self._start_global and self._current_global:
                left = min(self._start_global.x(), self._current_global.x())
                top = min(self._start_global.y(), self._current_global.y())
                right = max(self._start_global.x(), self._current_global.x())
                bottom = max(self._start_global.y(), self._current_global.y())
                
                # Minimum size check
                if (right - left) > 30 and (bottom - top) > 30:
                    dpr = self._dpr
                    self.area_selected.emit((
                        int(left * dpr),
                        int(top * dpr),
                        int(right * dpr),
                        int(bottom * dpr)
                    ))
                    self.close()
                else:
                    # Too small, reset
                    self._start_global = self._current_global = None
                    self.update()

    def keyPressEvent(self, event):
        """Handle key press."""
        if event.key() == Qt.Key_Escape:
            self.selection_cancelled.emit()
            self.close()
