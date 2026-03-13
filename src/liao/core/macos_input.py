"""Input simulation for macOS using Quartz events."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class MacOSInputSimulator:
    """Simulate mouse and keyboard input on macOS."""

    def __init__(self):
        self._quartz_available = self._check_quartz()

    def _check_quartz(self) -> bool:
        """Check if Quartz is available."""
        try:
            from Quartz import CGEventCreateMouseEvent

            return True
        except ImportError:
            logger.debug("Quartz input not available")
            return False

    def move_mouse(self, x: int, y: int) -> bool:
        """Move mouse to screen coordinates.

        Args:
            x: Screen X coordinate
            y: Screen Y coordinate

        Returns:
            True if successful
        """
        if not self._quartz_available:
            return False

        try:
            from Quartz import (
                CGEventCreateMouseEvent,
                CGEventPost,
                kCGHIDEventTap,
                kCGMouseEventMoved,
            )

            # Quartz uses flipped coordinate system (0,0 at bottom-left)
            # but we need screen coordinates (0,0 at top-left)
            event = CGEventCreateMouseEvent(None, kCGMouseEventMoved, (x, y), 0)
            if event:
                CGEventPost(kCGHIDEventTap, event)
                return True
            return False
        except Exception as e:
            logger.error(f"Mouse move failed: {e}")
            return False

    def click(self, x: int | None = None, y: int | None = None) -> bool:
        """Click at screen coordinates.

        Args:
            x: Screen X coordinate (optional, uses current position if None)
            y: Screen Y coordinate (optional, uses current position if None)

        Returns:
            True if successful
        """
        if not self._quartz_available:
            return False

        try:
            from Quartz import (
                CGEventCreateMouseEvent,
                CGEventPost,
                kCGHIDEventTap,
                kCGMouseEventLeftMouseDown,
                kCGMouseEventLeftMouseUp,
            )

            # Move to position if specified
            if x is not None and y is not None:
                self.move_mouse(x, y)
                time.sleep(0.05)

            # Click
            for event_type in [kCGMouseEventLeftMouseDown, kCGMouseEventLeftMouseUp]:
                event = CGEventCreateMouseEvent(None, event_type, (x or 0, y or 0), 0)
                if event:
                    CGEventPost(kCGHIDEventTap, event)
                    time.sleep(0.05)

            return True
        except Exception as e:
            logger.error(f"Click failed: {e}")
            return False

    def type_text(self, text: str) -> bool:
        """Type text using keyboard.

        Args:
            text: Text to type

        Returns:
            True if successful
        """
        if not self._quartz_available:
            return False

        try:
            from Quartz import (
                CGEventCreateKeyboardEvent,
                CGEventKeyboardSetUnicodeString,
                CGEventPost,
                kCGHIDEventTap,
            )

            for char in text:
                # Create key down event
                event = CGEventCreateKeyboardEvent(None, 0, True)
                if event:
                    CGEventKeyboardSetUnicodeString(event, 1, char)
                    CGEventPost(kCGHIDEventTap, event)

                time.sleep(0.02)

                # Create key up event
                event = CGEventCreateKeyboardEvent(None, 0, False)
                if event:
                    CGEventKeyboardSetUnicodeString(event, 1, char)
                    CGEventPost(kCGHIDEventTap, event)

                time.sleep(0.02)

            return True
        except Exception as e:
            logger.error(f"Type text failed: {e}")
            return False

    def press_key(self, key: str) -> bool:
        """Press a special key.

        Args:
            key: Key name (enter, backspace, etc.)

        Returns:
            True if successful
        """
        if not self._quartz_available:
            return False

        try:
            from Quartz import (
                CGEventCreateKeyboardEvent,
                CGEventPost,
                kCGHIDEventTap,
            )

            # Virtual key codes for special keys
            key_codes = {
                "enter": 36,
                "return": 36,
                "backspace": 51,
                "delete": 51,
                "escape": 53,
                "esc": 53,
                "tab": 48,
                "space": 49,
                "up": 126,
                "down": 125,
                "left": 123,
                "right": 124,
            }

            key_code = key_codes.get(key.lower())
            if key_code is None:
                # Try single character
                return self.type_text(key)

            # Key down
            event = CGEventCreateKeyboardEvent(None, key_code, True)
            if event:
                CGEventPost(kCGHIDEventTap, event)

            time.sleep(0.05)

            # Key up
            event = CGEventCreateKeyboardEvent(None, key_code, False)
            if event:
                CGEventPost(kCGHIDEventTap, event)

            return True
        except Exception as e:
            logger.error(f"Press key failed: {e}")
            return False

    def hotkey(self, *keys: str) -> bool:
        """Press multiple keys together (hotkey).

        Args:
            keys: Key names (e.g., "ctrl", "c")

        Returns:
            True if successful
        """
        if not self._quartz_available:
            return False

        try:
            from Quartz import (
                CGEventCreateKeyboardEvent,
                CGEventPost,
                kCGHIDEventTap,
            )

            key_codes = {
                "ctrl": 59,
                "control": 59,
                "cmd": 55,
                "command": 55,
                "win": 55,
                "alt": 58,
                "option": 58,
                "shift": 56,
            }

            # Press all keys down
            for key in keys:
                key_code = key_codes.get(key.lower())
                if key_code:
                    event = CGEventCreateKeyboardEvent(None, key_code, True)
                    if event:
                        CGEventPost(kCGHIDEventTap, event)
                    time.sleep(0.02)

            # Release all keys
            for key in reversed(keys):
                key_code = key_codes.get(key.lower())
                if key_code:
                    event = CGEventCreateKeyboardEvent(None, key_code, False)
                    if event:
                        CGEventPost(kCGHIDEventTap, event)
                    time.sleep(0.02)

            return True
        except Exception as e:
            logger.error(f"Hotkey failed: {e}")
            return False

    def focus_window(self, hwnd: int) -> bool:
        """Focus a window by bringing it to front.

        On macOS, this uses AppleScript.

        Args:
            hwnd: Window handle (not used on macOS)

        Returns:
            True if successful
        """
        import subprocess

        try:
            # Use AppleScript to activate frontmost app
            result = subprocess.run(
                [
                    "osascript",
                    "-e",
                    'tell application "System Events" to set frontmost of first process to true',
                ],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Focus window failed: {e}")
            return False

    def click_in_window(
        self,
        hwnd: int,
        win_left: int,
        win_top: int,
        screen_x: int,
        screen_y: int,
    ) -> bool:
        """Click at position within a window.

        Args:
            hwnd: Window handle
            win_left: Window left coordinate
            win_top: Window top coordinate
            screen_x: Click X coordinate (screen space)
            screen_y: Click Y coordinate (screen space)

        Returns:
            True if successful
        """
        return self.click(screen_x, screen_y)
