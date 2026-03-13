"""Knowledge Base file upload and indexing dialog."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Signal, QThread
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr

logger = logging.getLogger(__name__)


class KBUploadDialog(QDialog):
    """Dialog for uploading and indexing documents into KB.

    Features:
    - Select files (.md, .txt supported)
    - Select directory for batch import
    - Configure chunking parameters
    - View upload progress
    - Index after upload
    """

    upload_complete = Signal(list)  # Emitted with list of indexed document names

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(tr("kb.upload_documents"))
        self.setMinimumSize(600, 500)

        self._files_to_upload: list[Path] = []
        self._chunk_size = 800
        self._chunk_overlap = 150

        self._build_ui()

    def _build_ui(self) -> None:
        """Build UI components."""
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # File selection group
        file_group = self._create_file_selection_group()
        layout.addWidget(file_group)

        # Chunking settings group
        chunk_group = self._create_chunking_group()
        layout.addWidget(chunk_group)

        # Progress section
        self._progress_section = self._create_progress_section()
        layout.addWidget(self._progress_section)
        self._progress_section.setVisible(False)

        # Buttons
        button_box = self._create_buttons()
        layout.addWidget(button_box)

        self.setLayout(layout)

    def _create_file_selection_group(self) -> QWidget:
        """Create file selection group."""
        group = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Instructions
        instructions = QLabel(tr("kb.upload_instructions"))
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # File list
        self._file_list_widget = QListWidget()
        self._file_list_widget.setSelectionMode(
            QListWidget.SelectionMode.ExtendedSelection
        )
        layout.addWidget(self._file_list_widget)

        # Add/remove buttons
        btn_layout = QHBoxLayout()

        self._add_files_btn = QPushButton(tr("kb.add_files"))
        self._add_files_btn.clicked.connect(self._add_files)
        btn_layout.addWidget(self._add_files_btn)

        self._add_dir_btn = QPushButton(tr("kb.add_directory"))
        self._add_dir_btn.clicked.connect(self._add_directory)
        btn_layout.addWidget(self._add_dir_btn)

        self._remove_btn = QPushButton(tr("kb.remove_selected"))
        self._remove_btn.clicked.connect(self._remove_selected)
        btn_layout.addWidget(self._remove_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        group.setLayout(layout)
        return group

    def _create_chunking_group(self) -> QWidget:
        """Create chunking settings group."""
        group = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Chunk size
        chunk_size_label = QLabel(tr("kb.chunk_size"))
        self._chunk_size_spin = QSpinBox()
        self._chunk_size_spin.setRange(100, 2000)
        self._chunk_size_spin.setValue(800)
        self._chunk_size_spin.setSingleStep(50)
        self._chunk_size_spin.valueChanged.connect(self._on_chunk_size_changed)
        layout.addWidget(chunk_size_label)
        layout.addWidget(self._chunk_size_spin)

        # Chunk overlap
        overlap_label = QLabel(tr("kb.chunk_overlap"))
        self._chunk_overlap_spin = QSpinBox()
        self._chunk_overlap_spin.setRange(0, 500)
        self._chunk_overlap_spin.setValue(150)
        self._chunk_overlap_spin.setSingleStep(10)
        self._chunk_overlap_spin.valueChanged.connect(self._on_chunk_overlap_changed)
        layout.addWidget(overlap_label)
        layout.addWidget(self._chunk_overlap_spin)

        layout.addStretch()
        group.setLayout(layout)
        return group

    def _create_progress_section(self) -> QWidget:
        """Create progress section."""
        group = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setFormat("%p% (%v/%m)")
        layout.addWidget(self._progress_bar)

        # Status label
        self._status_label = QLabel()
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        group.setLayout(layout)
        return group

    def _create_buttons(self) -> QDialogButtonBox:
        """Create dialog buttons."""
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.button(QDialogButtonBox.StandardButton.Ok).setText(tr("kb.upload_and_index"))
        button_box.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("kb.cancel"))
        button_box.accepted.connect(self._start_upload)
        button_box.rejected.connect(self.reject)

        return button_box

    # -- Event Handlers --------------------------------------------------------

    def _add_files(self) -> None:
        """Add files to upload list."""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            tr("kb.select_files"),
            str(Path.home()),
            tr("kb.file_filter"),
        )

        for file_path in files:
            path = Path(file_path)
            if path.suffix.lower() in [".md", ".txt"]:
                self._files_to_upload.append(path)
                self._file_list_widget.addItem(str(path))
            else:
                logger.warning(f"Unsupported file type: {path.suffix}")

    def _add_directory(self) -> None:
        """Add all supported files from a directory."""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            tr("kb.select_directory"),
            str(Path.home()),
        )

        if dir_path:
            directory = Path(dir_path)
            count = 0
            for ext in ["*.md", "*.txt"]:
                for file_path in directory.rglob(ext):
                    self._files_to_upload.append(file_path)
                    self._file_list_widget.addItem(str(file_path))
                    count += 1

            logger.info(f"Added {count} files from {directory}")

    def _remove_selected(self) -> None:
        """Remove selected files from list."""
        selected_items = self._file_list_widget.selectedItems()
        for item in selected_items:
            row = self._file_list_widget.row(item)
            self._file_list_widget.takeItem(row)

            # Remove from internal list
            file_path = Path(item.text())
            if file_path in self._files_to_upload:
                self._files_to_upload.remove(file_path)

    def _on_chunk_size_changed(self, value: int) -> None:
        """Handle chunk size change."""
        self._chunk_size = value

    def _on_chunk_overlap_changed(self, value: int) -> None:
        """Handle chunk overlap change."""
        self._chunk_overlap = value

    def _start_upload(self) -> None:
        """Start upload and indexing process."""
        if not self._files_to_upload:
            return

        # Show progress section
        self._progress_section.setVisible(True)
        self._progress_bar.setMaximum(len(self._files_to_upload))
        self._progress_bar.setValue(0)

        # Disable buttons during upload
        self._set_buttons_enabled(False)

        # TODO: Start indexing worker thread
        self._status_label.setText(tr("kb.indexing_in_progress"))

        # For now, just accept
        self.accept()

    def _set_buttons_enabled(self, enabled: bool) -> None:
        """Enable/disable all buttons."""
        self._add_files_btn.setEnabled(enabled)
        self._add_dir_btn.setEnabled(enabled)
        self._remove_btn.setEnabled(enabled)

    # -- Getters ---------------------------------------------------------------

    def get_files(self) -> list[Path]:
        """Get list of files to upload.

        Returns:
            List of file paths
        """
        return self._files_to_upload.copy()

    def get_chunk_settings(self) -> tuple[int, int]:
        """Get chunking settings.

        Returns:
            Tuple of (chunk_size, chunk_overlap)
        """
        return self._chunk_size, self._chunk_overlap


class KBIndexWorker(QThread):
    """Worker thread for indexing documents.

    Runs indexing in background to avoid blocking UI.
    """

    progress = Signal(int, str)  # (current, filename)
    complete = Signal(list)      # List of indexed document names
    error = Signal(str)          # Error message

    def __init__(self, files: list[Path], kb_name: str,
                 chunk_size: int = 800, chunk_overlap: int = 150):
        super().__init__()

        self._files = files
        self._kb_name = kb_name
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    def run(self) -> None:
        """Run indexing process."""
        try:
            indexed = []
            for i, file_path in enumerate(self._files):
                # Emit progress
                self.progress.emit(i + 1, file_path.name)

                # TODO: Call KBManager.index_document()
                indexed.append(file_path.stem)

            self.complete.emit(indexed)
        except Exception as e:
            logger.error(f"Indexing failed: {e}")
            self.error.emit(str(e))
