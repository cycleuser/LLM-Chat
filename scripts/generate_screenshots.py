#!/usr/bin/env python
"""
Screenshot Generation Script for llm-chat

Generates screenshots for documentation by running the GUI
and capturing specific states.

Usage:
    python scripts/generate_screenshots.py

This will create screenshots in the images/ directory.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Add src to path
src_dir = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_dir))


def capture_main_window() -> None:
    """Capture the main window in various states."""
    import ctypes
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QPixmap
    
    from llm_chat.gui.main_window import MainWindow
    from llm_chat.gui.i18n import set_locale
    
    # DPI awareness
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    images_dir = Path(__file__).parent.parent / "images"
    images_dir.mkdir(exist_ok=True)
    
    screenshots = []
    
    def capture_and_close():
        # English screenshot
        set_locale("en_US")
        window_en = MainWindow()
        window_en.show()
        QApplication.processEvents()
        time.sleep(0.5)
        
        # Capture
        pm = window_en.grab()
        pm.save(str(images_dir / "main_window_en.png"))
        print(f"Saved: main_window_en.png")
        screenshots.append("main_window_en.png")
        window_en.close()
        
        # Chinese screenshot
        set_locale("zh_CN")
        window_zh = MainWindow()
        window_zh.show()
        QApplication.processEvents()
        time.sleep(0.5)
        
        pm = window_zh.grab()
        pm.save(str(images_dir / "main_window_zh.png"))
        print(f"Saved: main_window_zh.png")
        screenshots.append("main_window_zh.png")
        window_zh.close()
        
        app.quit()
    
    # Schedule capture
    QTimer.singleShot(1000, capture_and_close)
    
    app.exec()
    
    return screenshots


def main() -> int:
    print("Generating screenshots for llm-chat...\n")
    
    try:
        screenshots = capture_main_window()
        print(f"\nGenerated {len(screenshots)} screenshots")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
