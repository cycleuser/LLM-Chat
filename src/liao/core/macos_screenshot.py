"""Screenshot capture for macOS using pyautogui."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    from ..models.window import WindowInfo

logger = logging.getLogger(__name__)

IS_MACOS = sys.platform == "darwin"


class MacOSScreenshot:
    """Capture screenshots using pyautogui (handles DPI automatically)."""

    def __init__(self):
        self._pyautogui = None
        self._screen_size = None
        logger.info("Using pyautogui for screenshots")

    def _get_pyautogui(self):
        if self._pyautogui is None:
            import pyautogui

            self._pyautogui = pyautogui
            self._screen_size = pyautogui.size()
            logger.info(f"Screen size: {self._screen_size}")
        return self._pyautogui

    @property
    def screen_size(self) -> tuple[int, int]:
        """Get screen size in pyautogui coordinates."""
        pg = self._get_pyautogui()
        return (self._screen_size.width, self._screen_size.height)

    def capture_region(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> Image.Image | None:
        """Capture a screen region.

        Args:
            x: Left coordinate
            y: Top coordinate
            width: Region width
            height: Region height

        Returns:
            PIL Image or None
        """
        if width <= 0 or height <= 0:
            logger.error(f"Invalid dimensions: {width}x{height}")
            return None

        try:
            pg = self._get_pyautogui()
            return pg.screenshot(region=(x, y, width, height))
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return None

    def capture_window(self, window_info: WindowInfo) -> Image.Image | None:
        """Capture a window.

        Args:
            window_info: Window to capture

        Returns:
            PIL Image or None
        """
        # 获取窗口在pyautogui坐标系中的位置
        # 使用pyautogui.position()来校准坐标系
        pg = self._get_pyautogui()

        # 尝试使用窗口标题找到窗口
        # pyautogui使用的是屏幕坐标系，需要定位窗口
        x, y, right, bottom = window_info.rect
        width = right - x
        height = bottom - y

        return self.capture_region(x, y, width, height)


# Re-export
ScreenshotReader = MacOSScreenshot
