"""Connection page for LLM setup."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr
from ...llm.factory import LLMClientFactory
from .base_page import BasePage

if TYPE_CHECKING:
    from ..main_window import MainWindow


class ConnectionPage(BasePage):
    """Page for LLM connection setup."""
    
    connection_changed = Signal(bool)
    
    def __init__(self, main_window: "MainWindow", parent: QWidget | None = None):
        super().__init__(main_window, parent)
    
    def _build_ui(self) -> None:
        """Build the connection page UI."""
        content = QWidget()
        content.setMaximumWidth(500)
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(20)
        
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
        
        # Form layout
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignRight)
        
        self._url_edit = QLineEdit("http://localhost:11434")
        self._url_label = QLabel()
        form.addRow(self._url_label, self._url_edit)
        
        self._api_key_edit = QLineEdit()
        self._api_key_edit.setEchoMode(QLineEdit.Password)
        self._api_key_label = QLabel()
        form.addRow(self._api_key_label, self._api_key_edit)
        
        self._model_combo = QComboBox()
        self._model_combo.setEditable(True)
        self._model_combo.setMinimumWidth(200)
        self._model_label = QLabel()
        form.addRow(self._model_label, self._model_combo)
        
        content_layout.addLayout(form)
        
        # Connect button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self._connect_btn = QPushButton()
        self._connect_btn.clicked.connect(self._on_connect)
        btn_layout.addWidget(self._connect_btn)
        btn_layout.addStretch()
        content_layout.addLayout(btn_layout)
        
        # Status label
        self._status_label = QLabel()
        self._status_label.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(self._status_label)
        
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
        self._title.setText(tr("connection.title"))
        self._subtitle.setText(tr("connection.subtitle"))
        self._url_label.setText(tr("connection.url"))
        self._api_key_label.setText(tr("connection.api_key"))
        self._model_label.setText(tr("connection.model"))
        self._connect_btn.setText(tr("connection.connect"))
        self._api_key_edit.setPlaceholderText(tr("connection.api_key_hint"))
        
        if self.main_window._llm_client is None:
            self._status_label.setText(tr("connection.status.disconnected"))
    
    def is_valid(self) -> bool:
        """Connection page is valid when LLM client is connected."""
        return self.main_window._llm_client is not None
    
    def _on_connect(self) -> None:
        """Handle connect button click."""
        url = self._url_edit.text().strip()
        api_key = self._api_key_edit.text().strip()
        
        self._status_label.setText(tr("connection.status.connecting"))
        QApplication.processEvents()
        
        try:
            is_ollama = "11434" in url or "ollama" in url.lower()
            provider = "ollama" if is_ollama and not api_key else "openai"
            
            kwargs = {"base_url": url}
            if api_key:
                kwargs["api_key"] = api_key
            
            model = self._model_combo.currentText()
            if model:
                kwargs["model"] = model
            
            client = LLMClientFactory.create_client(provider, **kwargs)
            
            if not client.is_available():
                self._status_label.setText(tr("connection.status.failed"))
                return
            
            models = client.list_models()
            self._model_combo.clear()
            
            if models:
                if provider == "ollama":
                    embed_pats = ("embed", "nomic", "bge", "e5-", "mxbai")
                    chat_models = [m for m in models if not any(p in m.lower() for p in embed_pats)]
                    models = chat_models or models
                
                for m in models:
                    self._model_combo.addItem(m)
                
                self._status_label.setText(tr("connection.status.connected", count=len(models)))
                self.main_window._llm_client = client
            else:
                self._status_label.setText(tr("connection.status.no_models"))
            
            self._emit_validity_changed()
            self.connection_changed.emit(self.is_valid())
            
        except Exception as e:
            self._status_label.setText(f"{tr('connection.status.failed')}: {e}")
    
    def get_selected_model(self) -> str:
        """Get currently selected model name."""
        return self._model_combo.currentText()
