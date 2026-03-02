"""Window management module using Win32 APIs."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..models.window import WindowInfo

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Application type detection patterns
CHAT_APP_PATTERNS = {
    "wechat": ["WeChatMainWndForPC", "ChatWnd", "微信"],
    "wecom": ["WeWorkWindow", "WeWorkMainWindow", "企业微信"],
    "qq": ["TXGuiFoundation", "QQMainWnd", "QQ"],
    "telegram": ["Telegram", "TelegramDesktop"],
    "dingtalk": ["钉钉", "DingTalk"],
    "feishu": ["飞书", "Lark"],
    "slack": ["Slack"],
    "discord": ["Discord"],
    "teams": ["Microsoft Teams", "Teams"],
}


class WindowManager:
    """Manages desktop windows using Win32 APIs.
    
    This class provides functionality to enumerate visible windows,
    detect application types, and manage window state.
    
    Example:
        wm = WindowManager()
        windows = wm.get_all_visible_windows()
        for w in windows:
            print(f"{w.title} ({w.app_type})")
    """

    def __init__(self):
        self._win32gui = None
        self._win32con = None
        self._load_win32()

    def _load_win32(self):
        """Load Win32 modules if available."""
        try:
            import win32con
            import win32gui
            self._win32gui = win32gui
            self._win32con = win32con
        except ImportError:
            logger.warning("pywin32 not available - window management disabled")

    def is_available(self) -> bool:
        """Check if Win32 APIs are available."""
        return self._win32gui is not None

    def get_all_visible_windows(self) -> list[WindowInfo]:
        """Get all visible windows with valid titles.
        
        Returns:
            List of WindowInfo objects sorted by title
        """
        if not self.is_available():
            return []
        
        windows: list[WindowInfo] = []

        def enum_callback(hwnd, _):
            try:
                if not self._win32gui.IsWindowVisible(hwnd):
                    return True
                title = self._win32gui.GetWindowText(hwnd)
                if not title or not title.strip():
                    return True
                rect = self._win32gui.GetWindowRect(hwnd)
                # Filter out tiny windows
                if (rect[2] - rect[0]) < 200 or (rect[3] - rect[1]) < 150:
                    return True
                cls = self._win32gui.GetClassName(hwnd)
                app_type = self._detect_app_type(title, cls)
                windows.append(WindowInfo(
                    hwnd=hwnd,
                    title=title,
                    class_name=cls,
                    rect=rect,
                    app_type=app_type
                ))
            except Exception:
                pass
            return True

        self._win32gui.EnumWindows(enum_callback, None)
        windows.sort(key=lambda w: w.title.lower())
        return windows

    @staticmethod
    def _detect_app_type(title: str, class_name: str) -> str:
        """Detect application type from title and class name."""
        tl, cl = title.lower(), class_name.lower()
        for app_type, patterns in CHAT_APP_PATTERNS.items():
            for pattern in patterns:
                if pattern.lower() in tl or pattern.lower() in cl:
                    return app_type
        return "other"

    def get_window_by_hwnd(self, hwnd: int) -> WindowInfo | None:
        """Get window info by handle.
        
        Args:
            hwnd: Window handle
            
        Returns:
            WindowInfo if found, None otherwise
        """
        if not self.is_available():
            return None
        try:
            if not self._win32gui.IsWindow(hwnd):
                return None
            title = self._win32gui.GetWindowText(hwnd)
            cls = self._win32gui.GetClassName(hwnd)
            rect = self._win32gui.GetWindowRect(hwnd)
            return WindowInfo(
                hwnd=hwnd,
                title=title,
                class_name=cls,
                rect=rect,
                app_type=self._detect_app_type(title, cls)
            )
        except Exception as e:
            logger.warning(f"Failed to get window by hwnd: {e}")
            return None

    def refresh_window_info(self, window: WindowInfo) -> WindowInfo | None:
        """Refresh window info (get updated rect, title, etc.).
        
        Args:
            window: Existing WindowInfo to refresh
            
        Returns:
            Updated WindowInfo if window still exists, None otherwise
        """
        return self.get_window_by_hwnd(window.hwnd)

    def get_chat_windows(self) -> list[WindowInfo]:
        """Get only windows detected as chat applications.
        
        Returns:
            List of WindowInfo for chat apps (WeChat, QQ, etc.)
        """
        return [w for w in self.get_all_visible_windows() if w.app_type != "other"]

    def find_window_by_title(self, title_substring: str) -> WindowInfo | None:
        """Find first window containing title substring.
        
        Args:
            title_substring: Substring to search for in window titles
            
        Returns:
            First matching WindowInfo or None
        """
        title_lower = title_substring.lower()
        for w in self.get_all_visible_windows():
            if title_lower in w.title.lower():
                return w
        return None
