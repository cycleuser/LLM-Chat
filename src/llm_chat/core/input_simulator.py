"""Input simulation module using Win32 SendInput API."""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

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


class InputSimulator:
    """Simulates mouse and keyboard input using Win32 SendInput.
    
    Example:
        sim = InputSimulator()
        sim.move_to(500, 300)
        sim.click()
        sim.type_text("Hello, World!")
        sim.press_key("enter")
    """

    def __init__(self):
        self._user32 = ctypes.windll.user32
        self._pyperclip = None
        self._load_pyperclip()

    def _load_pyperclip(self):
        """Load pyperclip for clipboard operations."""
        try:
            import pyperclip
            self._pyperclip = pyperclip
        except ImportError:
            logger.warning("pyperclip not available - clipboard operations disabled")

    def _send_input(self, *inputs: INPUT) -> int:
        """Send input events via SendInput API."""
        arr = (INPUT * len(inputs))(*inputs)
        return self._user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))

    def _abs_coords(self, x: int, y: int) -> tuple[int, int]:
        """Convert screen coordinates to SendInput normalized 0-65535 range."""
        sm_xvscreen = self._user32.GetSystemMetrics(76)
        sm_yvscreen = self._user32.GetSystemMetrics(77)
        sm_cxvscreen = self._user32.GetSystemMetrics(78)
        sm_cyvscreen = self._user32.GetSystemMetrics(79)
        nx = int((x - sm_xvscreen) * 65535 / sm_cxvscreen)
        ny = int((y - sm_yvscreen) * 65535 / sm_cyvscreen)
        return nx, ny

    def focus_window(self, hwnd: int) -> bool:
        """Bring window to foreground using thread-attach trick.
        
        Args:
            hwnd: Window handle to focus
            
        Returns:
            True if successful
        """
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

    def click(self, x: int | None = None, y: int | None = None) -> None:
        """Click at (x, y) or current position.
        
        Args:
            x: Optional x coordinate
            y: Optional y coordinate
        """
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

    def press_key(self, key: str) -> None:
        """Press and release a single key.
        
        Args:
            key: Key name (e.g., "enter", "a", "ctrl")
        """
        vk = VK_MAP.get(key.lower(), 0)
        if not vk:
            logger.warning(f"Unknown key: {key}")
            return
        down = INPUT(type=INPUT_KEYBOARD)
        down.union.ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=0, time=0, dwExtraInfo=None)
        up = INPUT(type=INPUT_KEYBOARD)
        up.union.ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=KEYEVENTF_KEYUP, time=0, dwExtraInfo=None)
        self._send_input(down, up)

    def hotkey(self, *keys: str) -> None:
        """Press a key combination (e.g., Ctrl+V).
        
        Args:
            *keys: Key names to press in sequence
        """
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

    def send_enter(self) -> None:
        """Press Enter key."""
        self.press_key("enter")

    def type_text(self, text: str, clear_first: bool = True) -> bool:
        """Type text using clipboard paste.
        
        Args:
            text: Text to type
            clear_first: Whether to clear existing text first (Ctrl+A, Delete)
            
        Returns:
            True if successful
        """
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
        clear_first: bool = True,
        move_duration: float = 0.3,
    ) -> bool:
        """Focus window, move to input, click, clear, paste text.
        
        Args:
            x: Input field x coordinate
            y: Input field y coordinate
            text: Text to type
            hwnd: Optional window handle to focus first
            clear_first: Whether to clear existing text
            move_duration: Mouse movement duration
            
        Returns:
            True if successful
        """
        if hwnd:
            self.focus_window(hwnd)
            time.sleep(0.15)

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


def send_enter() -> None:
    """Press Enter (convenience function)."""
    _get_default_simulator().send_enter()


def click_and_type(
    x: int, y: int, text: str,
    hwnd: int | None = None, clear_first: bool = True, move_duration: float = 0.3,
) -> bool:
    """Click and type text (convenience function)."""
    return _get_default_simulator().click_and_type(x, y, text, hwnd, clear_first, move_duration)


def click_send_button(x: int, y: int, hwnd: int | None = None, move_duration: float = 0.3) -> None:
    """Click send button (convenience function)."""
    _get_default_simulator().click_send_button(x, y, hwnd, move_duration)
