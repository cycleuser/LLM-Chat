"""Chat input automation using pyautogui."""

from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pyautogui
import pyperclip

if TYPE_CHECKING:
    from ..models.window import WindowInfo

logger = logging.getLogger(__name__)

pyautogui.PAUSE = 0.1
pyautogui.FAILSAFE = True

IS_MACOS = sys.platform == "darwin"


@dataclass
class ChatAreas:
    """Detected chat UI areas."""

    chat_rect: tuple[int, int, int, int]
    input_rect: tuple[int, int, int, int]
    send_button: tuple[int, int] | None = None
    method: str = "heuristic"
    confidence: float = 0.5


class ChatInput:
    """Chat input automation with click, paste, and send."""

    def __init__(self):
        self._areas: ChatAreas | None = None
        self._detector = None
        logger.info("ChatInput initialized")

    def _get_detector(self):
        """Get platform-specific detector."""
        if self._detector is None:
            if IS_MACOS:
                from .macos_area_detector import MacOSAreaDetector

                self._detector = MacOSAreaDetector()
            else:
                self._detector = self
        return self._detector

    def detect_areas(self, window: WindowInfo) -> ChatAreas:
        """Detect chat UI areas using OCR or heuristics."""
        if IS_MACOS:
            detector = self._get_detector()
            result = detector.detect_areas(window)
            if result:
                self._areas = ChatAreas(
                    chat_rect=result.chat_rect,
                    input_rect=result.input_rect,
                    send_button=result.send_button,
                    method=result.method,
                    confidence=result.confidence,
                )
                logger.info(
                    f"Areas detected via {result.method}: "
                    f"chat={self._areas.chat_rect}, "
                    f"input={self._areas.input_rect}"
                )
                return self._areas

        return self._detect_areas_heuristic(window)

    def _detect_areas_heuristic(self, window: WindowInfo) -> ChatAreas:
        """Fallback heuristic detection."""
        rect = window.rect
        w = rect[2] - rect[0]
        h = rect[3] - rect[1]

        sidebar = 0.22
        header = 0.06
        input_h = 0.13
        right_margin = 0.01

        chat_left = rect[0] + int(w * sidebar)
        chat_top = rect[1] + int(h * header)
        chat_right = rect[2] - int(w * right_margin)
        chat_bottom = rect[3] - int(h * input_h)

        input_left = chat_left
        input_top = chat_bottom
        input_right = chat_right
        input_bottom = rect[3] - int(h * 0.01)

        send_x = input_right - 50
        send_y = input_bottom - 18

        self._areas = ChatAreas(
            chat_rect=(chat_left, chat_top, chat_right, chat_bottom),
            input_rect=(input_left, input_top, input_right, input_bottom),
            send_button=(send_x, send_y),
            method="heuristic",
            confidence=0.5,
        )

        logger.info(f"Areas detected via heuristic: chat={self._areas.chat_rect}")
        return self._areas

    def click_at(self, x: int, y: int) -> bool:
        """Click at position."""
        try:
            pyautogui.click(x, y)
            logger.info(f"Clicked at ({x}, {y})")
            return True
        except Exception as e:
            logger.error(f"Click failed: {e}")
            return False

    def click_input(self, window: WindowInfo | None = None) -> bool:
        """Click on input area."""
        if window and not self._areas:
            self.detect_areas(window)

        if not self._areas:
            logger.error("No areas detected")
            return False

        x = (self._areas.input_rect[0] + self._areas.input_rect[2]) // 2
        y = (self._areas.input_rect[1] + self._areas.input_rect[3]) // 2

        logger.info(f"Clicking input at ({x}, {y})")
        return self.click_at(x, y)

    def paste_text(self, text: str) -> bool:
        """Paste text using clipboard."""
        try:
            pyperclip.copy(text)
            time.sleep(0.1)
            if IS_MACOS:
                pyautogui.hotkey("command", "v")
            else:
                pyautogui.hotkey("ctrl", "v")
            time.sleep(0.2)
            logger.info(f"Pasted {len(text)} characters")
            return True
        except Exception as e:
            logger.error(f"Paste failed: {e}")
            return False

    def clear_input(self) -> bool:
        """Clear input field."""
        try:
            if IS_MACOS:
                pyautogui.hotkey("command", "a")
            else:
                pyautogui.hotkey("ctrl", "a")
            time.sleep(0.1)
            logger.info("Cleared input")
            return True
        except Exception as e:
            logger.error(f"Clear failed: {e}")
            return False

    def press_enter(self) -> bool:
        """Press Enter key."""
        try:
            pyautogui.press("enter")
            logger.info("Pressed Enter")
            return True
        except Exception as e:
            logger.error(f"Enter press failed: {e}")
            return False

    def click_send_button(self) -> bool:
        """Click send button."""
        if not self._areas or not self._areas.send_button:
            logger.error("No send button detected")
            return False

        x, y = self._areas.send_button
        logger.info(f"Clicking send button at ({x}, {y})")
        return self.click_at(x, y)

    def send_message(self, text: str, window: WindowInfo, method: str = "auto") -> bool:
        """Send message to the target window.

        Args:
            text: Message content
            window: Target window
            method: Send method ("auto", "enter", "button", "ctrl_enter")
        """
        logger.info(f"=== Sending message ({len(text)} chars) ===")
        print(f"\n>>> 发送消息: {text}")

        if not self._areas:
            self.detect_areas(window)

        logger.info("Step 1: Click input")
        if not self.click_input():
            logger.error("Failed to click input")
            return False
        time.sleep(0.3)

        logger.info("Step 2: Clear input")
        self.clear_input()
        time.sleep(0.1)

        logger.info("Step 3: Paste text")
        if not self.paste_text(text):
            logger.error("Failed to paste")
            return False
        time.sleep(0.3)

        logger.info(f"Step 4: Send (method={method})")
        if method == "button":
            self.click_send_button()
            time.sleep(0.1)
            self.press_enter()
        elif method == "ctrl_enter":
            pyautogui.hotkey("ctrl", "enter")
        else:
            self.press_enter()

        logger.info("=== Message sent ===")
        return True

    def get_chat_text(self, window: WindowInfo) -> str:
        """Get text from chat area using OCR."""
        if not self._areas:
            self.detect_areas(window)

        if not self._areas:
            return ""

        from .macos_screenshot import MacOSScreenshot

        screenshot = MacOSScreenshot()

        img = screenshot.capture_region(
            self._areas.chat_rect[0],
            self._areas.chat_rect[1],
            self._areas.chat_rect[2] - self._areas.chat_rect[0],
            self._areas.chat_rect[3] - self._areas.chat_rect[1],
        )

        if not img:
            return ""

        try:
            import easyocr
            import numpy as np

            reader = easyocr.Reader(["ch_sim", "en"], gpu=False, verbose=False)
            results = reader.readtext(np.array(img))

            texts = [text for bbox, text, prob in results if prob > 0.3]
            return "\n".join(texts)

        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return ""

    @property
    def areas(self) -> ChatAreas | None:
        return self._areas
