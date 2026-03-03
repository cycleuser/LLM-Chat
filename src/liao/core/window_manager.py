"""Window management module with cross-platform support.

Uses Win32 APIs on Windows, xwininfo/wmctrl/xdotool on Linux.
"""

from __future__ import annotations

import logging
import re
import subprocess
import sys
from typing import TYPE_CHECKING

from ..models.window import WindowInfo

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform == "linux"

# Application type detection patterns
CHAT_APP_PATTERNS = {
    "wechat": ["WeChatMainWndForPC", "ChatWnd", "微信", "WeChat"],
    "wecom": ["WeWorkWindow", "WeWorkMainWindow", "企业微信"],
    "qq": ["TXGuiFoundation", "QQMainWnd", "QQ"],
    "telegram": ["Telegram", "TelegramDesktop"],
    "dingtalk": ["钉钉", "DingTalk"],
    "feishu": ["飞书", "Lark"],
    "slack": ["Slack"],
    "discord": ["Discord"],
    "teams": ["Microsoft Teams", "Teams"],
}

# xwininfo output pattern:
#   0xe00004 "publish.sh - Liao - Qoder": ("qoder" "Qoder")  2560x1411+0+29  +0+29
_XWININFO_RE = re.compile(
    r'^\s+(0x[0-9a-fA-F]+)\s+'         # XID hex
    r'"([^"]*)"'                         # title in quotes
    r'(?::\s*\("([^"]*)")?'             # optional WM_CLASS part 1
    r'(?:\s+"([^"]*)")?\)?'             # optional WM_CLASS part 2
    r'\s+(\d+)x(\d+)\+(-?\d+)\+(-?\d+)' # WxH+X+Y (geometry)
)


class WindowManager:
    """Manages desktop windows with cross-platform support.
    
    Uses Win32 APIs on Windows, xwininfo/wmctrl/xdotool on Linux.
    Works under both X11 and Wayland (via XWayland).
    
    Example:
        wm = WindowManager()
        windows = wm.get_all_visible_windows()
        for w in windows:
            print(f"{w.title} ({w.app_type})")
    """

    def __init__(self):
        self._win32gui = None
        self._win32con = None
        self._linux_xwininfo = False
        self._linux_wmctrl = False
        self._linux_xdotool = False
        self._load_win32()
        self._load_linux()

    def _load_win32(self):
        """Load Win32 modules if available."""
        if not IS_WINDOWS:
            return
        try:
            import win32con
            import win32gui
            self._win32gui = win32gui
            self._win32con = win32con
        except ImportError:
            logger.warning("pywin32 not available - window management disabled")

    def _load_linux(self):
        """Detect Linux window management tools."""
        if not IS_LINUX:
            return
        
        # Check for xwininfo (part of x11-utils, usually pre-installed)
        try:
            subprocess.run(
                ["xwininfo", "-version"],
                capture_output=True, text=True, timeout=2,
            )
            self._linux_xwininfo = True
            logger.debug("xwininfo available for window management")
        except FileNotFoundError:
            logger.debug("xwininfo not found")
        except (subprocess.TimeoutExpired, Exception):
            # xwininfo -version may fail but the binary exists
            self._linux_xwininfo = True
        
        # Check for wmctrl
        try:
            subprocess.run(
                ["wmctrl", "--version"],
                capture_output=True, text=True, timeout=2,
            )
            self._linux_wmctrl = True
            logger.debug("wmctrl available for window management")
        except FileNotFoundError:
            pass
        except (subprocess.TimeoutExpired, Exception):
            pass
        
        # Check for xdotool
        try:
            subprocess.run(
                ["xdotool", "version"],
                capture_output=True, text=True, timeout=2,
            )
            self._linux_xdotool = True
            logger.debug("xdotool available for window management")
        except FileNotFoundError:
            pass
        except (subprocess.TimeoutExpired, Exception):
            pass
        
        if not self._linux_xwininfo and not self._linux_wmctrl and not self._linux_xdotool:
            logger.warning(
                "No window management tools available - "
                "install with: sudo apt install x11-utils wmctrl xdotool"
            )

    def is_available(self) -> bool:
        """Check if window management is available on this platform."""
        return (
            self._win32gui is not None
            or self._linux_xwininfo
            or self._linux_wmctrl
            or self._linux_xdotool
        )

    def get_all_visible_windows(self) -> list[WindowInfo]:
        """Get all visible windows with valid titles.
        
        Returns:
            List of WindowInfo objects sorted by title
        """
        if self._win32gui is not None:
            return self._get_windows_win32()
        elif IS_LINUX:
            return self._get_windows_linux()
        return []

    def _get_windows_win32(self) -> list[WindowInfo]:
        """Enumerate windows using Win32 APIs."""
        windows: list[WindowInfo] = []

        def enum_callback(hwnd, _):
            try:
                if not self._win32gui.IsWindowVisible(hwnd):
                    return True
                title = self._win32gui.GetWindowText(hwnd)
                if not title or not title.strip():
                    return True
                rect = self._win32gui.GetWindowRect(hwnd)
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

    def _get_windows_linux(self) -> list[WindowInfo]:
        """Enumerate windows on Linux, trying backends in order."""
        # 1. xwininfo (works on both X11 and Wayland via XWayland, usually pre-installed)
        if self._linux_xwininfo:
            windows = self._get_windows_xwininfo()
            if windows is not None:
                return windows
        
        # 2. wmctrl (X11 only, needs separate install)
        if self._linux_wmctrl:
            windows = self._get_windows_wmctrl()
            if windows is not None:
                return windows
        
        # 3. xdotool (X11 only, needs separate install)
        if self._linux_xdotool:
            windows = self._get_windows_xdotool()
            if windows is not None:
                return windows
        
        return []

    def _get_windows_xwininfo(self) -> list[WindowInfo] | None:
        """Enumerate windows using xwininfo -root -children.
        
        Works on both X11 and Wayland (via XWayland). Pre-installed
        on most Linux desktops as part of x11-utils.
        
        Output format per child line:
            0xe00004 "Window Title": ("instance" "Class")  WxH+X+Y  +absX+absY
        """
        try:
            result = subprocess.run(
                ["xwininfo", "-root", "-children"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0:
                logger.warning(f"xwininfo failed: {result.stderr}")
                return None
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            logger.warning(f"xwininfo error: {e}")
            return None
        
        # Skip internal/utility window patterns
        skip_patterns = {
            "mutter guard window", "mutter-x11-frames",
            "chromium clipboard", "qt selection owner",
            "gsd-xsettings", "ibus-x11", "ibus-xim",
            "gnome shell",
        }
        
        windows: list[WindowInfo] = []
        for line in result.stdout.splitlines():
            m = _XWININFO_RE.match(line)
            if not m:
                continue
            
            xid_str, title, wm_instance, wm_class, w_str, h_str, x_str, y_str = m.groups()
            
            if not title or not title.strip():
                continue
            
            # Skip known internal windows
            title_lower = title.lower()
            if any(p in title_lower for p in skip_patterns):
                continue
            
            try:
                xid = int(xid_str, 16)
                w = int(w_str)
                h = int(h_str)
                x = int(x_str)
                y = int(y_str)
            except ValueError:
                continue
            
            if w < 200 or h < 150:
                continue
            
            class_name = wm_class or wm_instance or ""
            rect = (x, y, x + w, y + h)
            app_type = self._detect_app_type(title, class_name)
            
            windows.append(WindowInfo(
                hwnd=xid,
                title=title,
                class_name=class_name,
                rect=rect,
                app_type=app_type,
            ))
        
        windows.sort(key=lambda w: w.title.lower())
        return windows

    def _get_windows_wmctrl(self) -> list[WindowInfo] | None:
        """Enumerate windows using wmctrl -lG."""
        try:
            result = subprocess.run(
                ["wmctrl", "-lG"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0:
                logger.warning(f"wmctrl failed: {result.stderr}")
                return None
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            logger.warning(f"wmctrl error: {e}")
            return None
        
        windows: list[WindowInfo] = []
        for line in result.stdout.strip().splitlines():
            try:
                parts = line.split(None, 7)
                if len(parts) < 8:
                    continue
                
                xid = int(parts[0], 16)
                x = int(parts[2])
                y = int(parts[3])
                w = int(parts[4])
                h = int(parts[5])
                title = parts[7].strip()
                
                if not title:
                    continue
                if w < 200 or h < 150:
                    continue
                
                rect = (x, y, x + w, y + h)
                app_type = self._detect_app_type(title, "")
                windows.append(WindowInfo(
                    hwnd=xid,
                    title=title,
                    class_name="",
                    rect=rect,
                    app_type=app_type,
                ))
            except (ValueError, IndexError):
                continue
        
        windows.sort(key=lambda w: w.title.lower())
        return windows

    def _get_windows_xdotool(self) -> list[WindowInfo] | None:
        """Enumerate windows using xdotool."""
        try:
            result = subprocess.run(
                ["xdotool", "search", "--onlyvisible", "--name", ""],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0:
                return None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None
        
        xids = result.stdout.strip().splitlines()
        if not xids:
            return None
        
        windows: list[WindowInfo] = []
        for xid_str in xids:
            try:
                xid = int(xid_str.strip())
            except ValueError:
                continue
            
            try:
                name_result = subprocess.run(
                    ["xdotool", "getwindowname", str(xid)],
                    capture_output=True, text=True, timeout=2,
                )
                title = name_result.stdout.strip() if name_result.returncode == 0 else ""
                if not title:
                    continue
                
                geo_result = subprocess.run(
                    ["xdotool", "getwindowgeometry", "--shell", str(xid)],
                    capture_output=True, text=True, timeout=2,
                )
                if geo_result.returncode != 0:
                    continue
                
                geo = {}
                for geo_line in geo_result.stdout.strip().splitlines():
                    if "=" in geo_line:
                        k, v = geo_line.split("=", 1)
                        geo[k] = v
                
                x = int(geo.get("X", 0))
                y = int(geo.get("Y", 0))
                w = int(geo.get("WIDTH", 0))
                h = int(geo.get("HEIGHT", 0))
                
                if w < 200 or h < 150:
                    continue
                
                rect = (x, y, x + w, y + h)
                app_type = self._detect_app_type(title, "")
                windows.append(WindowInfo(
                    hwnd=xid,
                    title=title,
                    class_name="",
                    rect=rect,
                    app_type=app_type,
                ))
            except (subprocess.TimeoutExpired, FileNotFoundError, ValueError, KeyError):
                continue
        
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
            hwnd: Window handle (HWND on Windows, XID on Linux)
            
        Returns:
            WindowInfo if found, None otherwise
        """
        if self._win32gui is not None:
            return self._get_window_by_hwnd_win32(hwnd)
        elif IS_LINUX:
            # Search current window list for matching ID
            for w in self.get_all_visible_windows():
                if w.hwnd == hwnd:
                    return w
        return None

    def _get_window_by_hwnd_win32(self, hwnd: int) -> WindowInfo | None:
        """Get window info by HWND using Win32 APIs."""
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
