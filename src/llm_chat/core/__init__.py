"""Core modules for vision-gui-agent."""

from .window_manager import WindowManager
from .input_simulator import InputSimulator
from .screenshot import ScreenshotReader
from .area_detector import ChatAreaDetector

__all__ = [
    "WindowManager",
    "InputSimulator",
    "ScreenshotReader",
    "ChatAreaDetector",
]
