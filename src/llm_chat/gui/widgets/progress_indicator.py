"""Progress indicator widget showing wizard steps."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QPen, QPalette
from PySide6.QtWidgets import QWidget, QApplication

from ..i18n import tr


class ProgressIndicator(QWidget):
    """Horizontal step progress indicator using system colors."""
    
    step_clicked = Signal(int)
    
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._current_step = 0
        self._step_labels = [
            tr("progress.step_connection"),
            tr("progress.step_window"),
            tr("progress.step_area"),
            tr("progress.step_chat"),
        ]
        self.setMinimumHeight(60)
        self.setMaximumHeight(70)
    
    def set_current_step(self, step: int) -> None:
        """Set the current active step (0-3)."""
        if 0 <= step <= 3:
            self._current_step = step
            self.update()
    
    def current_step(self) -> int:
        """Get current step index."""
        return self._current_step
    
    def update_translations(self) -> None:
        """Update step labels with current translations."""
        self._step_labels = [
            tr("progress.step_connection"),
            tr("progress.step_window"),
            tr("progress.step_area"),
            tr("progress.step_chat"),
        ]
        self.update()
    
    def paintEvent(self, event) -> None:
        """Paint the progress indicator using system colors."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Get system colors from palette
        palette = QApplication.palette()
        color_highlight = palette.color(QPalette.Highlight)
        color_text = palette.color(QPalette.WindowText)
        color_disabled = palette.color(QPalette.Disabled, QPalette.WindowText)
        color_button = palette.color(QPalette.Button)
        color_button_text = palette.color(QPalette.ButtonText)
        
        width = self.width()
        height = self.height()
        
        n_steps = 4
        margin = 80
        available_width = width - 2 * margin
        step_width = available_width / (n_steps - 1)
        
        circle_radius = 12
        circle_y = height // 2 - 5
        text_y = circle_y + circle_radius + 18
        
        # Draw connecting lines
        for i in range(n_steps - 1):
            x1 = margin + i * step_width + circle_radius
            x2 = margin + (i + 1) * step_width - circle_radius
            
            if i < self._current_step:
                pen = QPen(color_highlight, 3)
            else:
                pen = QPen(color_disabled, 2)
            
            painter.setPen(pen)
            painter.drawLine(int(x1), circle_y, int(x2), circle_y)
        
        # Draw circles and labels
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        
        for i in range(n_steps):
            x = margin + i * step_width
            
            if i < self._current_step:
                circle_color = color_highlight
                text_color = color_text
            elif i == self._current_step:
                circle_color = color_highlight
                text_color = color_highlight
            else:
                circle_color = color_button
                text_color = color_disabled
            
            # Draw circle
            painter.setPen(Qt.NoPen)
            painter.setBrush(circle_color)
            painter.drawEllipse(int(x - circle_radius), circle_y - circle_radius,
                              circle_radius * 2, circle_radius * 2)
            
            # Draw checkmark or number
            if i < self._current_step:
                painter.setPen(QPen(color_button_text, 2))
                painter.drawLine(int(x - 5), circle_y, int(x - 1), circle_y + 4)
                painter.drawLine(int(x - 1), circle_y + 4, int(x + 6), circle_y - 4)
            else:
                painter.setPen(color_button_text)
                font_num = painter.font()
                font_num.setPointSize(10)
                font_num.setBold(True)
                painter.setFont(font_num)
                painter.drawText(int(x - 5), circle_y + 5, str(i + 1))
                painter.setFont(font)
            
            # Draw label
            painter.setPen(text_color)
            label = self._step_labels[i]
            fm = painter.fontMetrics()
            text_width = fm.horizontalAdvance(label)
            painter.drawText(int(x - text_width // 2), text_y, label)
        
        painter.end()
    
    def mousePressEvent(self, event) -> None:
        """Handle click on step."""
        width = self.width()
        margin = 80
        available_width = width - 2 * margin
        step_width = available_width / 3
        
        click_x = event.pos().x()
        for i in range(4):
            x = margin + i * step_width
            if abs(click_x - x) < 30:
                self.step_clicked.emit(i)
                break
