"""Window information data model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WindowInfo:
    """Information about a desktop window.
    
    Attributes:
        hwnd: Window handle (HWND)
        title: Window title text
        class_name: Window class name
        rect: Window rectangle (left, top, right, bottom)
        app_type: Detected application type ("wechat", "qq", "telegram", etc.)
    """
    
    hwnd: int
    title: str
    class_name: str
    rect: tuple[int, int, int, int]  # left, top, right, bottom
    app_type: str  # "wechat", "wecom", "qq", "telegram", "dingtalk", "feishu", "other"

    @property
    def width(self) -> int:
        """Window width in pixels."""
        return self.rect[2] - self.rect[0]

    @property
    def height(self) -> int:
        """Window height in pixels."""
        return self.rect[3] - self.rect[1]

    @property
    def center(self) -> tuple[int, int]:
        """Center point of the window (x, y)."""
        return (self.rect[0] + self.rect[2]) // 2, (self.rect[1] + self.rect[3]) // 2

    @property
    def left(self) -> int:
        """Left edge x-coordinate."""
        return self.rect[0]

    @property
    def top(self) -> int:
        """Top edge y-coordinate."""
        return self.rect[1]

    @property
    def right(self) -> int:
        """Right edge x-coordinate."""
        return self.rect[2]

    @property
    def bottom(self) -> int:
        """Bottom edge y-coordinate."""
        return self.rect[3]

    def __str__(self) -> str:
        return f"WindowInfo({self.title!r}, hwnd={self.hwnd}, {self.width}x{self.height})"
