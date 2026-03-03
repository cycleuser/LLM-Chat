"""Input simulation module with cross-platform support.

Uses Win32 SendInput API on Windows for best performance,
ydotool/xdotool on Linux/Wayland, falls back to pyautogui on other platforms.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Check platform
IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform == "linux"
IS_WAYLAND = IS_LINUX and os.environ.get("XDG_SESSION_TYPE") == "wayland"

# Windows-specific constants and structures
if IS_WINDOWS:
    import ctypes
    import ctypes.wintypes

    # Windows constants
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_ABSOLUTE = 0x8000
    MOUSEEVENTF_VIRTUALDESK = 0x4000
    KEYEVENTF_KEYUP = 0x0002
    INPUT_MOUSE = 0
    INPUT_KEYBOARD = 1

    # Virtual key codes
    VK_CONTROL = 0x11
    VK_RETURN = 0x0D
    VK_BACK = 0x08
    VK_DELETE = 0x2E
    VK_ESCAPE = 0x1B
    VK_MENU = 0x12  # Alt
    VK_SHIFT = 0x10
    VK_TAB = 0x09

    # Key name to VK code mapping
    VK_MAP = {
        "enter": VK_RETURN, "return": VK_RETURN,
        "backspace": VK_BACK, "delete": VK_DELETE,
        "escape": VK_ESCAPE, "esc": VK_ESCAPE,
        "ctrl": VK_CONTROL, "control": VK_CONTROL,
        "alt": VK_MENU, "tab": VK_TAB, "shift": VK_SHIFT,
        "a": 0x41, "b": 0x42, "c": 0x43, "d": 0x44, "e": 0x45,
        "f": 0x46, "g": 0x47, "h": 0x48, "i": 0x49, "j": 0x4A,
        "k": 0x4B, "l": 0x4C, "m": 0x4D, "n": 0x4E, "o": 0x4F,
        "p": 0x50, "q": 0x51, "r": 0x52, "s": 0x53, "t": 0x54,
        "u": 0x55, "v": 0x56, "w": 0x57, "x": 0x58, "y": 0x59, "z": 0x5A,
    }

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", ctypes.wintypes.LONG),
            ("dy", ctypes.wintypes.LONG),
            ("mouseData", ctypes.wintypes.DWORD),
            ("dwFlags", ctypes.wintypes.DWORD),
            ("time", ctypes.wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(ctypes.wintypes.ULONG)),
        ]

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", ctypes.wintypes.WORD),
            ("wScan", ctypes.wintypes.WORD),
            ("dwFlags", ctypes.wintypes.DWORD),
            ("time", ctypes.wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(ctypes.wintypes.ULONG)),
        ]

    class _INPUT_UNION(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", ctypes.wintypes.DWORD), ("union", _INPUT_UNION)]

# xdotool key name mapping (internal names -> X11 keysym names)
_XDOTOOL_KEY_MAP = {
    "enter": "Return", "return": "Return",
    "backspace": "BackSpace", "delete": "Delete",
    "escape": "Escape", "esc": "Escape",
    "ctrl": "ctrl", "control": "ctrl",
    "alt": "alt", "shift": "shift",
    "tab": "Tab", "space": "space",
    "up": "Up", "down": "Down", "left": "Left", "right": "Right",
    "home": "Home", "end": "End",
    "pageup": "Page_Up", "pagedown": "Page_Down",
}

# ydotool key code mapping (internal names -> Linux evdev keycodes)
# See /usr/include/linux/input-event-codes.h for full list
_YDOTOOL_KEY_MAP = {
    "enter": 28, "return": 28,  # KEY_ENTER
    "backspace": 14, "delete": 111,  # KEY_BACKSPACE, KEY_DELETE
    "escape": 1, "esc": 1,  # KEY_ESC
    "ctrl": 29, "control": 29,  # KEY_LEFTCTRL
    "alt": 56, "shift": 42,  # KEY_LEFTALT, KEY_LEFTSHIFT
    "tab": 15, "space": 57,  # KEY_TAB, KEY_SPACE
    "up": 103, "down": 108, "left": 105, "right": 106,
    "home": 102, "end": 107,
    "pageup": 104, "pagedown": 109,
    # Letters a-z (KEY_A=30 through KEY_Z)
    "a": 30, "b": 48, "c": 46, "d": 32, "e": 18,
    "f": 33, "g": 34, "h": 35, "i": 23, "j": 36,
    "k": 37, "l": 38, "m": 50, "n": 49, "o": 24,
    "p": 25, "q": 16, "r": 19, "s": 31, "t": 20,
    "u": 22, "v": 47, "w": 17, "x": 45, "y": 21, "z": 44,
}


class InputSimulator:
    """Simulates mouse and keyboard input.

    Uses Win32 SendInput on Windows, ydotool/xdotool on Linux,
    falls back to pyautogui on other platforms.

    Example:
        sim = InputSimulator()
        sim.move_to(500, 300)
        sim.click()
        sim.type_text("Hello, World!")
        sim.press_key("enter")
    """

    def __init__(self):
        self._pyautogui = None
        self._pyperclip = None
        self._user32 = None
        self._use_win32 = False
        self._linux_xdotool = False
        self._linux_ydotool = False
        self._linux_wtype = False
        self._linux_wl_copy = False
        self._linux_xclip = False
        self._load_deps()

    def _load_deps(self):
        """Load dependencies based on platform."""
        # Load pyperclip for clipboard operations
        try:
            import pyperclip
            self._pyperclip = pyperclip
        except ImportError:
            logger.warning("pyperclip not available - clipboard operations disabled")

        # Load pyautogui as fallback
        try:
            import pyautogui
            self._pyautogui = pyautogui
            # Disable pyautogui's fail-safe (moving to corner stops program)
            pyautogui.FAILSAFE = False
        except Exception as e:
            logger.warning(f"pyautogui not available - some input features disabled: {e}")

        # On Windows, prefer Win32 API
        if IS_WINDOWS:
            try:
                self._user32 = ctypes.windll.user32
                self._use_win32 = True
                logger.debug("Using Win32 SendInput API")
            except Exception as e:
                logger.warning(f"Win32 API not available: {e}")
                self._use_win32 = False

        # On Linux, detect available tools
        if IS_LINUX:
            self._detect_linux_tools()

    def _detect_linux_tools(self):
        """Detect available Linux input tools."""
        # Check ydotool (Wayland-native, requires working ydotoold daemon)
        try:
            # Run a harmless ydotool command and check stderr for backend errors.
            # ydotool prints "ydotoold backend unavailable" when the daemon
            # socket is unreachable, even if the process exists.
            test = subprocess.run(
                ["ydotool", "key", ""],
                capture_output=True, text=True, timeout=3,
            )
            if "ydotoold backend unavailable" not in (test.stderr + test.stdout):
                self._linux_ydotool = True
                logger.info("Using ydotool for Wayland input simulation")
            else:
                logger.info(
                    "ydotool daemon not reachable, skipping ydotool"
                )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Check wtype (Wayland typing tool)
        try:
            r = subprocess.run(
                ["wtype", "--help"],
                capture_output=True, timeout=3,
            )
            self._linux_wtype = True
            logger.debug("wtype available for Wayland typing")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Check xdotool (X11/XWayland)
        try:
            r = subprocess.run(
                ["xdotool", "version"],
                capture_output=True, timeout=3,
            )
            if r.returncode == 0:
                self._linux_xdotool = True
                logger.info("Using xdotool for X11/XWayland input simulation")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        if not self._linux_xdotool and not self._linux_ydotool:
            logger.warning(
                "No input simulation tool found. Install one of:\n"
                "  For Wayland: sudo apt install ydotool && sudo systemctl enable --now ydotool\n"
                "  For XWayland: sudo apt install xdotool"
            )

        # Check wl-copy (native Wayland clipboard)
        try:
            r = subprocess.run(
                ["wl-copy", "--version"],
                capture_output=True, timeout=3,
            )
            if r.returncode == 0:
                self._linux_wl_copy = True
                logger.debug("wl-copy available for clipboard")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Check xclip (X11 clipboard, works via XWayland)
        try:
            r = subprocess.run(
                ["xclip", "-version"],
                capture_output=True, timeout=3,
            )
            # xclip -version prints to stderr and returns 0
            self._linux_xclip = True
            logger.debug("xclip available for clipboard")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    def _run_xdotool(self, *args: str) -> bool:
        """Run an xdotool command.

        Args:
            *args: xdotool arguments.

        Returns:
            True if the command succeeded.
        """
        cmd = ["xdotool"] + list(args)
        logger.info("Running xdotool: %s", " ".join(cmd))
        try:
            r = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode != 0:
                logger.warning(f"xdotool {' '.join(args)} failed: {r.stderr.strip()}")
                return False
            if r.stdout.strip():
                logger.debug(f"xdotool output: {r.stdout.strip()}")
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            logger.warning(f"xdotool error: {e}")
            return False

    def _run_ydotool(self, *args: str) -> bool:
        """Run a ydotool command.

        Args:
            *args: ydotool arguments.

        Returns:
            True if the command succeeded.
        """
        try:
            r = subprocess.run(
                ["ydotool"] + list(args),
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode != 0:
                logger.warning(f"ydotool {' '.join(args)} failed: {r.stderr.strip()}")
                return False
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            logger.warning(f"ydotool error: {e}")
            return False

    def _run_wtype(self, text: str) -> bool:
        """Run wtype to type text on Wayland.

        Args:
            text: Text to type.

        Returns:
            True if the command succeeded.
        """
        try:
            r = subprocess.run(
                ["wtype", text],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode != 0:
                logger.warning(f"wtype failed: {r.stderr.strip()}")
                return False
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            logger.warning(f"wtype error: {e}")
            return False

    @staticmethod
    def _xdotool_key_name(key: str) -> str:
        """Map internal key name to xdotool X11 keysym name."""
        return _XDOTOOL_KEY_MAP.get(key.lower(), key)

    @staticmethod
    def _ydotool_key_code(key: str) -> int | None:
        """Map internal key name to ydotool Linux evdev keycode."""
        return _YDOTOOL_KEY_MAP.get(key.lower())

    def _linux_set_clipboard(self, text: str) -> bool:
        """Set clipboard content on Linux.

        Tries wl-copy (Wayland native) > xclip > pyperclip.

        Args:
            text: Text to put on clipboard.

        Returns:
            True if clipboard was set successfully.
        """
        encoded = text.encode("utf-8")

        if self._linux_wl_copy:
            try:
                r = subprocess.run(
                    ["wl-copy"],
                    input=encoded, capture_output=True, timeout=3,
                )
                if r.returncode == 0:
                    return True
                logger.debug(f"wl-copy failed: {r.stderr}")
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

        if self._linux_xclip:
            try:
                r = subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=encoded, capture_output=True, timeout=3,
                )
                if r.returncode == 0:
                    return True
                logger.debug(f"xclip failed: {r.stderr}")
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

        if self._pyperclip:
            try:
                self._pyperclip.copy(text)
                return True
            except Exception as e:
                logger.debug(f"pyperclip failed: {e}")

        logger.error(
            "Could not set clipboard. "
            "Install wl-clipboard or xclip: sudo apt install wl-clipboard xclip"
        )
        return False

    def is_available(self) -> bool:
        """Check if input simulation is available."""
        return (
            self._use_win32
            or self._pyautogui is not None
            or (IS_LINUX and (self._linux_xdotool or self._linux_ydotool))
        )

    def _send_input(self, *inputs) -> int:
        """Send input events via SendInput API (Windows only)."""
        if not self._use_win32:
            return 0
        arr = (INPUT * len(inputs))(*inputs)
        return self._user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))

    def _abs_coords(self, x: int, y: int) -> tuple[int, int]:
        """Convert screen coordinates to SendInput normalized 0-65535 range."""
        if not self._use_win32:
            return x, y
        sm_xvscreen = self._user32.GetSystemMetrics(76)
        sm_yvscreen = self._user32.GetSystemMetrics(77)
        sm_cxvscreen = self._user32.GetSystemMetrics(78)
        sm_cyvscreen = self._user32.GetSystemMetrics(79)
        nx = int((x - sm_xvscreen) * 65535 / sm_cxvscreen)
        ny = int((y - sm_yvscreen) * 65535 / sm_cyvscreen)
        return nx, ny

    def focus_window(self, hwnd: int) -> bool:
        """Bring window to foreground.

        Args:
            hwnd: Window handle (HWND on Windows, XID on Linux)

        Returns:
            True if successful
        """
        if IS_LINUX and self._linux_xdotool:
            ok = self._run_xdotool("windowactivate", "--sync", str(hwnd))
            time.sleep(0.15)
            return ok
        if not self._use_win32:
            logger.debug("focus_window not supported on this platform")
            return False
        try:
            SW_RESTORE = 9
            if self._user32.IsIconic(hwnd):
                self._user32.ShowWindow(hwnd, SW_RESTORE)
                time.sleep(0.3)
            current = self._user32.GetForegroundWindow()
            cur_tid = self._user32.GetWindowThreadProcessId(current, None)
            tgt_tid = self._user32.GetWindowThreadProcessId(hwnd, None)
            if cur_tid != tgt_tid:
                self._user32.AttachThreadInput(cur_tid, tgt_tid, True)
            # Alt key press trick to allow SetForegroundWindow
            self._user32.keybd_event(0x12, 0, 0, 0)  # Alt down
            self._user32.keybd_event(0x12, 0, 2, 0)  # Alt up
            self._user32.SetForegroundWindow(hwnd)
            self._user32.BringWindowToTop(hwnd)
            if cur_tid != tgt_tid:
                self._user32.AttachThreadInput(cur_tid, tgt_tid, False)
            time.sleep(0.15)
            return True
        except Exception as e:
            logger.warning(f"focus_window failed: {e}")
            return False

    def move_to(self, x: int, y: int, duration: float = 0, steps: int = 20) -> None:
        """Move mouse to (x, y) with optional smooth animation.

        Args:
            x: Target x coordinate
            y: Target y coordinate
            duration: Animation duration in seconds (0 for instant)
            steps: Number of animation steps
        """
        if self._use_win32:
            pt = ctypes.wintypes.POINT()
            self._user32.GetCursorPos(ctypes.byref(pt))
            sx, sy = pt.x, pt.y

            if duration <= 0 or steps <= 1:
                self._user32.SetCursorPos(x, y)
                return

            for i in range(1, steps + 1):
                t = i / steps
                # Ease in-out cubic
                t = t * t * (3 - 2 * t)
                cx = int(sx + (x - sx) * t)
                cy = int(sy + (y - sy) * t)
                self._user32.SetCursorPos(cx, cy)
                time.sleep(duration / steps)
        elif IS_LINUX:
            # Try ydotool first (Wayland native), then xdotool (XWayland)
            if self._linux_ydotool:
                if self._run_ydotool("mousemove", "-a", str(int(x)), str(int(y))):
                    return
            if self._linux_xdotool:
                self._run_xdotool("mousemove", str(int(x)), str(int(y)))
        elif self._pyautogui:
            self._pyautogui.moveTo(x, y, duration=duration)

    def click(self, x: int | None = None, y: int | None = None) -> None:
        """Click at (x, y) or current position.

        Args:
            x: Optional x coordinate
            y: Optional y coordinate
        """
        if self._use_win32:
            if x is not None and y is not None:
                nx, ny = self._abs_coords(x, y)
                down = INPUT(type=INPUT_MOUSE)
                down.union.mi = MOUSEINPUT(
                    dx=nx, dy=ny, mouseData=0,
                    dwFlags=MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK | MOUSEEVENTF_MOVE | MOUSEEVENTF_LEFTDOWN,
                    time=0, dwExtraInfo=None,
                )
                up = INPUT(type=INPUT_MOUSE)
                up.union.mi = MOUSEINPUT(
                    dx=nx, dy=ny, mouseData=0,
                    dwFlags=MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK | MOUSEEVENTF_MOVE | MOUSEEVENTF_LEFTUP,
                    time=0, dwExtraInfo=None,
                )
                self._send_input(down, up)
            else:
                down = INPUT(type=INPUT_MOUSE)
                down.union.mi = MOUSEINPUT(dx=0, dy=0, mouseData=0, dwFlags=MOUSEEVENTF_LEFTDOWN, time=0, dwExtraInfo=None)
                up = INPUT(type=INPUT_MOUSE)
                up.union.mi = MOUSEINPUT(dx=0, dy=0, mouseData=0, dwFlags=MOUSEEVENTF_LEFTUP, time=0, dwExtraInfo=None)
                self._send_input(down, up)
        elif IS_LINUX:
            # Try ydotool first (Wayland native), then xdotool (XWayland)
            if self._linux_ydotool:
                if x is not None and y is not None:
                    self._run_ydotool("mousemove", "-a", str(int(x)), str(int(y)))
                    time.sleep(0.02)
                # 0xC0 = left button down+up
                if self._run_ydotool("click", "0xC0"):
                    return
            if self._linux_xdotool:
                if x is not None and y is not None:
                    self._run_xdotool("mousemove", str(int(x)), str(int(y)))
                    time.sleep(0.02)
                self._run_xdotool("click", "1")
        elif self._pyautogui:
            if x is not None and y is not None:
                self._pyautogui.click(x, y)
            else:
                self._pyautogui.click()

    def move_and_click(self, x: int, y: int, duration: float = 0.2) -> None:
        """Move to position and click.

        Args:
            x: Target x coordinate
            y: Target y coordinate
            duration: Movement animation duration
        """
        self.move_to(x, y, duration=duration)
        time.sleep(0.05)
        self.click(x, y)

    def click_in_window(
        self,
        hwnd: int,
        win_left: int,
        win_top: int,
        screen_x: int,
        screen_y: int,
    ) -> bool:
        """Click at a position within a specific window.

        Uses global screen coordinates with xdotool mousemove + click,
        which works on both X11 and Wayland/XWayland.

        Args:
            hwnd: Window handle (X11 window ID) - used only for focus
            win_left: Window's left edge (unused, kept for API compat)
            win_top: Window's top edge (unused, kept for API compat)
            screen_x: Target click x in screen coordinates
            screen_y: Target click y in screen coordinates

        Returns:
            True if click was sent
        """
        if IS_LINUX and self._linux_xdotool:
            logger.info(
                "click_in_window: screen=(%d,%d), hwnd=%s",
                screen_x, screen_y, hwnd,
            )
            # Move mouse to absolute screen position and click
            self._run_xdotool("mousemove", str(screen_x), str(screen_y))
            time.sleep(0.1)
            self._run_xdotool("click", "1")
            return True
        # Fallback
        self.move_and_click(screen_x, screen_y, duration=0.2)
        return True

    def press_key(self, key: str) -> None:
        """Press and release a single key.

        Args:
            key: Key name (e.g., "enter", "a", "ctrl")
        """
        if self._use_win32:
            vk = VK_MAP.get(key.lower(), 0)
            if not vk:
                logger.warning(f"Unknown key: {key}")
                return
            down = INPUT(type=INPUT_KEYBOARD)
            down.union.ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=0, time=0, dwExtraInfo=None)
            up = INPUT(type=INPUT_KEYBOARD)
            up.union.ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=KEYEVENTF_KEYUP, time=0, dwExtraInfo=None)
            self._send_input(down, up)
        elif IS_LINUX:
            # Try ydotool first (Wayland native), then xdotool (XWayland)
            if self._linux_ydotool:
                keycode = self._ydotool_key_code(key)
                if keycode is not None:
                    if self._run_ydotool("key", str(keycode)):
                        return
                else:
                    logger.debug(f"Unknown ydotool key: {key}, falling back to xdotool")
            if self._linux_xdotool:
                sym = self._xdotool_key_name(key)
                self._run_xdotool("key", sym)
        elif self._pyautogui:
            self._pyautogui.press(key)

    def hotkey(self, *keys: str) -> None:
        """Press a key combination (e.g., Ctrl+V).

        Args:
            *keys: Key names to press in sequence
        """
        if self._use_win32:
            inputs = []
            # Key down events
            for k in keys:
                vk = VK_MAP.get(k.lower(), 0)
                if not vk:
                    continue
                inp = INPUT(type=INPUT_KEYBOARD)
                inp.union.ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=0, time=0, dwExtraInfo=None)
                inputs.append(inp)
            # Key up events (reversed order)
            for k in reversed(keys):
                vk = VK_MAP.get(k.lower(), 0)
                if not vk:
                    continue
                inp = INPUT(type=INPUT_KEYBOARD)
                inp.union.ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=KEYEVENTF_KEYUP, time=0, dwExtraInfo=None)
                inputs.append(inp)
            if inputs:
                self._send_input(*inputs)
        elif IS_LINUX:
            # Try ydotool first (Wayland native), then xdotool (XWayland)
            if self._linux_ydotool:
                keycodes = [self._ydotool_key_code(k) for k in keys]
                if all(kc is not None for kc in keycodes):
                    # Build key sequence: down events, then up events (reversed)
                    # Format: keycode:1 for down, keycode:0 for up
                    key_args = []
                    for kc in keycodes:
                        key_args.append(f"{kc}:1")  # Key down
                    for kc in reversed(keycodes):
                        key_args.append(f"{kc}:0")  # Key up
                    if self._run_ydotool("key", *key_args):
                        return
            if self._linux_xdotool:
                syms = [self._xdotool_key_name(k) for k in keys]
                combo = "+".join(syms)
                self._run_xdotool("key", combo)
        elif self._pyautogui:
            self._pyautogui.hotkey(*keys)

    def send_enter(self, hwnd: int | None = None) -> None:
        """Press Enter key, optionally targeting a specific window.

        Args:
            hwnd: Optional window handle to target (Linux only).
        """
        if IS_LINUX and hwnd and self._linux_xdotool:
            self._run_xdotool("key", "--window", str(hwnd), "Return")
        else:
            self.press_key("enter")

    def send_ctrl_enter(self, hwnd: int | None = None) -> None:
        """Press Ctrl+Enter, optionally targeting a specific window.

        Args:
            hwnd: Optional window handle to target (Linux only).
        """
        if IS_LINUX and hwnd and self._linux_xdotool:
            self._run_xdotool("key", "--window", str(hwnd), "ctrl+Return")
        else:
            self.hotkey("ctrl", "enter")

    def type_text(self, text: str, clear_first: bool = True) -> bool:
        """Type text using clipboard paste.

        Args:
            text: Text to type
            clear_first: Whether to clear existing text first (Ctrl+A, Delete)

        Returns:
            True if successful
        """
        # On Linux, use Linux clipboard + key simulation (ydotool or xdotool)
        if IS_LINUX and (self._linux_ydotool or self._linux_xdotool):
            if clear_first:
                self.hotkey("ctrl", "a")
                time.sleep(0.05)
                self.press_key("delete")
                time.sleep(0.05)
            if not self._linux_set_clipboard(text):
                return False
            time.sleep(0.05)
            self.hotkey("ctrl", "v")
            time.sleep(0.1)
            return True

        # Default path: pyperclip + platform hotkey
        if not self._pyperclip:
            logger.error("pyperclip not available for type_text")
            return False

        if clear_first:
            self.hotkey("ctrl", "a")
            time.sleep(0.05)
            self.press_key("delete")
            time.sleep(0.05)

        self._pyperclip.copy(text)
        time.sleep(0.05)
        self.hotkey("ctrl", "v")
        time.sleep(0.1)
        return True

    def click_and_type(
        self,
        x: int,
        y: int,
        text: str,
        hwnd: int | None = None,
        win_rect: tuple[int, int, int, int] | None = None,
        clear_first: bool = True,
        move_duration: float = 0.3,
    ) -> bool:
        """Focus window, move to input, click, clear, paste text.

        Args:
            x: Input field x coordinate (screen coords)
            y: Input field y coordinate (screen coords)
            text: Text to type
            hwnd: Optional window handle to focus first
            win_rect: Optional window rect (unused, kept for API compat)
            clear_first: Whether to clear existing text
            move_duration: Mouse movement duration

        Returns:
            True if successful
        """
        if hwnd:
            self.focus_window(hwnd)
            time.sleep(0.15)

        # Use xdotool with global screen coordinates
        if IS_LINUX and self._linux_xdotool:
            logger.info("click_and_type: clicking at (%d, %d)", x, y)
            self._run_xdotool("mousemove", str(x), str(y))
            time.sleep(0.1)
            self._run_xdotool("click", "1")
            time.sleep(0.1)
            self._run_xdotool("click", "1")  # Double click
        else:
            self.move_to(x, y, duration=move_duration)
            time.sleep(0.05)
            self.click(x, y)
            time.sleep(0.1)
            self.click(x, y)  # Double click to ensure focus
        time.sleep(0.1)

        return self.type_text(text, clear_first=clear_first)

    def click_send_button(
        self,
        x: int,
        y: int,
        hwnd: int | None = None,
        move_duration: float = 0.3,
    ) -> None:
        """Click a send button.

        Args:
            x: Button x coordinate
            y: Button y coordinate
            hwnd: Optional window handle to focus first
            move_duration: Mouse movement duration
        """
        if hwnd:
            self.focus_window(hwnd)
            time.sleep(0.1)
        self.move_and_click(x, y, duration=move_duration)


# Module-level convenience functions
_default_simulator: InputSimulator | None = None


def _get_default_simulator() -> InputSimulator:
    """Get or create the default InputSimulator instance."""
    global _default_simulator
    if _default_simulator is None:
        _default_simulator = InputSimulator()
    return _default_simulator


def focus_window_hard(hwnd: int) -> bool:
    """Bring window to foreground (convenience function)."""
    return _get_default_simulator().focus_window(hwnd)


def move_to(x: int, y: int, duration: float = 0, steps: int = 20) -> None:
    """Move mouse to position (convenience function)."""
    _get_default_simulator().move_to(x, y, duration, steps)


def click(x: int | None = None, y: int | None = None) -> None:
    """Click at position (convenience function)."""
    _get_default_simulator().click(x, y)


def move_and_click(x: int, y: int, duration: float = 0.2) -> None:
    """Move and click (convenience function)."""
    _get_default_simulator().move_and_click(x, y, duration)


def press_key(key: str) -> None:
    """Press key (convenience function)."""
    _get_default_simulator().press_key(key)


def hotkey(*keys: str) -> None:
    """Press hotkey combination (convenience function)."""
    _get_default_simulator().hotkey(*keys)


def send_enter(hwnd: int | None = None) -> None:
    """Press Enter (convenience function)."""
    _get_default_simulator().send_enter(hwnd=hwnd)


def send_ctrl_enter(hwnd: int | None = None) -> None:
    """Press Ctrl+Enter (convenience function)."""
    _get_default_simulator().send_ctrl_enter(hwnd=hwnd)


def click_and_type(
    x: int, y: int, text: str,
    hwnd: int | None = None, clear_first: bool = True, move_duration: float = 0.3,
) -> bool:
    """Click and type text (convenience function)."""
    return _get_default_simulator().click_and_type(x, y, text, hwnd, clear_first, move_duration)


def click_send_button(x: int, y: int, hwnd: int | None = None, move_duration: float = 0.3) -> None:
    """Click send button (convenience function)."""
    _get_default_simulator().click_send_button(x, y, hwnd, move_duration)
