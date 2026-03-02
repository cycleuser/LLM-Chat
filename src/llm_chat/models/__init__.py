"""Data models for vision-gui-agent."""

from .window import WindowInfo
from .message import ChatMessage
from .detection import AreaDetectionResult

__all__ = [
    "WindowInfo",
    "ChatMessage",
    "AreaDetectionResult",
]
