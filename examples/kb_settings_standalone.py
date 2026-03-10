#!/usr/bin/env python3
"""
Standalone KB Settings Dialog

Run this to configure Liao's knowledge base settings.
"""

import sys
from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout, QDialogButtonBox, QMessageBox
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from liao.knowledge import KBConfig, KBManager
from liao.gui.pages import KBSettingsPage


class KBSettingsDialog(QDialog):
    """Standalone KB settings dialog."""
    
   def __init__(self):
        super().__init__()
       self.setWindowTitle("Knowledge Base Settings")
       self.setMinimumSize(700, 600)
        
        # Load existing config
       self.config = load_kb_config()
        
        # Build UI
        layout = QVBoxLayout()
        
        # Add KB settings page
       self.kb_page = KBSettingsPage(self)
       self.kb_page.set_kb_config({
            "enabled": True,
            "chroma_dir": self.config.chroma_dir,
            "embedding_model": self.config.embedding_model,
            "ollama_url": self.config.ollama_url,
            "strict_mode": self.config.strict_kb_mode,
            "kb_scope": self.config.kb_scope,
        })
       self.kb_page.kb_config_changed.connect(self._on_config_changed)
        layout.addWidget(self.kb_page)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
       self.setLayout(layout)
    
   def _on_config_changed(self):
        """Save config when changed."""
       config_dict = self.kb_page.get_kb_config()
        save_kb_config(config_dict)


def load_kb_config():
    """Load KB config from file."""
   config_path = Path.home() / ".liao" / "kb" / "config.json"
   if config_path.exists():
        import json
        with open(config_path, 'r') as f:
            data = json.load(f)
       return KBConfig(**data)
   return KBConfig()


def save_kb_config(config_dict: dict):
    """Save KB config to file."""
   config_path = Path.home() / ".liao" / "kb" / "config.json"
   config_path.parent.mkdir(parents=True, exist_ok=True)
    
    import json
    with open(config_path, 'w') as f:
        json.dump(config_dict, f, indent=2, ensure_ascii=False)
    
    print(f"✓ KB config saved to {config_path}")


def main():
    app = QApplication(sys.argv)
    
    # Show splash message
    QMessageBox.information(
        None,
        "KB Settings",
        "Configure Knowledge Base settings for Liao.\n\n"
        "Changes will be saved to ~/.liao/kb/config.json"
    )
    
    dialog = KBSettingsDialog()
   result = dialog.exec()
    
   if result == QDialog.DialogCode.Accepted:
        print("✓ KB settings saved")
   else:
        print("KB settings cancelled")
    
   sys.exit(0)


if __name__ == "__main__":
   main()
