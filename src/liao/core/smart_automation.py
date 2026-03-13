"""Intelligent automation manager with smart send detection."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from .area_detector import ChatAreaDetector
from .input_simulator import InputSimulator
from .screenshot import ScreenshotReader
from .send_mode import SendModeManager, SendShortcut, SendConfig
from ..models.message import ChatMessage
from ..agent.chat_parser import OCRChatParser

if TYPE_CHECKING:
    from ..models.window import WindowInfo

logger = logging.getLogger(__name__)


@dataclass
class AutomationConfig:
    """Configuration for automated chat control."""
    chat_area: tuple[int, int, int, int] | None = None
    input_area: tuple[int, int, int, int] | None = None
    send_button_pos: tuple[int, int] | None = None
    app_type: str = "other"
    detection_method: str = "auto"
    confidence: float = 0.5
    send_shortcut: SendShortcut = SendShortcut.ENTER


class SmartAutomationManager:
    """Intelligent automation manager with adaptive send detection."""

    def __init__(self, screenshot_reader: ScreenshotReader):
        self._reader = screenshot_reader
        self._detector = ChatAreaDetector(screenshot_reader)
        self._parser = OCRChatParser(screenshot_reader)
        self._input = InputSimulator()
        self._send_manager = SendModeManager()

        self._last_messages: list[ChatMessage] = []
        self._last_message_count: dict[str, int] = {}
        self._config: AutomationConfig | None = None

        self.on_status: Callable[[str], None] | None = None
        self.on_detection: Callable[[AutomationConfig], None] | None = None
        self.on_message: Callable[[ChatMessage], None] | None = None
        self.on_send_result: Callable[[bool, str], None] | None = None

    def auto_detect(self, window_info: WindowInfo, force_ocr: bool = False) -> AutomationConfig | None:
        """Auto-detect chat elements and send mode."""
        self._emit_status("Detecting chat areas...")
        app_type = window_info.app_type
        
        areas = self._detector.detect_areas(window_info)
        if not areas:
            self._emit_status("Failed to detect areas")
            return None

        send_config = self._send_manager.detect_send_mode(app_type, has_button=False)

        config = AutomationConfig(
            chat_area=areas.chat_area_rect,
            input_area=areas.input_area_rect,
            app_type=app_type,
            detection_method=areas.method,
            confidence=areas.confidence,
            send_shortcut=send_config.shortcut,
        )

        send_pos = self._detect_send_button(window_info, config)
        if send_pos:
            config.send_button_pos = send_pos
            send_config.has_button = True
            send_config.button_pos = send_pos
            send_config.shortcut = SendShortcut.BUTTON

        self._config = config
        if self.on_detection:
            self.on_detection(config)

        send_status = self._send_manager.get_status(app_type)
        self._emit_status(f"Detected: {app_type} | Send: {send_status}")
        return config

    def _detect_send_button(self, window_info: WindowInfo, config: AutomationConfig) -> tuple[int, int] | None:
        """Detect send button position via OCR."""
        if not config.input_area:
            return None

        if self._reader.has_ocr():
            try:
                screenshot = self._reader.capture_window(window_info)
                if screenshot:
                    results = self._reader.extract_with_bboxes(screenshot)
                    send_patterns = [r"发送|Send", r"提交|Submit", r"📤|✉️"]
                    
                    for bbox, text, conf in results:
                        for pattern in send_patterns:
                            if re.search(pattern, text, re.IGNORECASE):
                                cx = sum(p[0] for p in bbox) / 4
                                cy = sum(p[1] for p in bbox) / 4
                                return (int(cx), int(cy))
            except Exception as e:
                logger.debug(f"OCR button detection failed: {e}")

        offset = (-45, -15)
        input_rect = config.input_area
        return (input_rect[2] + offset[0], input_rect[3] + offset[1])

    def send_message(self, text: str, window_info: WindowInfo, config: AutomationConfig | None = None) -> bool:
        """Send message with verification."""
        config = config or self._config
        if not config or not config.input_area:
            logger.error("No input area configured")
            return False

        app_type = config.app_type
        send_config = self._send_manager.get_config(app_type)
        old_count = self._get_message_count(window_info, config)

        self._input.focus_window(window_info.hwnd)
        time.sleep(0.2)

        input_rect = config.input_area
        ix, iy = (input_rect[0] + input_rect[2]) // 2, (input_rect[1] + input_rect[3]) // 2

        self._emit_status("Typing message...")
        self._input.click_and_type(x=ix, y=iy, text=text, hwnd=window_info.hwnd,
                                   win_rect=window_info.rect, clear_first=True, move_duration=0.3)
        time.sleep(0.15)

        success = self._trigger_send(window_info, config, send_config)
        if success:
            self._last_message_count[app_type] = old_count
        return success

    def _trigger_send(self, window_info: WindowInfo, config: AutomationConfig, send_config: SendConfig) -> bool:
        """Trigger send using configured method."""
        hwnd = window_info.hwnd

        if send_config.shortcut == SendShortcut.BUTTON and config.send_button_pos:
            bx, by = config.send_button_pos
            self._emit_status("Clicking send button...")
            self._input.click_in_window(hwnd=hwnd, win_left=window_info.rect[0],
                                        win_top=window_info.rect[1], screen_x=bx, screen_y=by)
            time.sleep(0.1)
            self._input.press_key("enter")
            return True

        shortcut_keys = self._send_manager.get_shortcut_keys(send_config.shortcut)
        if shortcut_keys:
            self._emit_status(f"Sending with {send_config.shortcut.value}...")
            if len(shortcut_keys) == 1:
                self._input.press_key(shortcut_keys[0])
            else:
                self._input.hotkey(*shortcut_keys)
            time.sleep(0.1)
            return True

        self._input.press_key("enter")
        return True

    def verify_send(self, window_info: WindowInfo, config: AutomationConfig, expected_text: str | None = None) -> bool:
        """Verify if message was sent successfully."""
        app_type = config.app_type
        time.sleep(0.5)

        new_count = self._get_message_count(window_info, config)
        old_count = self._last_message_count.get(app_type, 0)

        if new_count > old_count:
            self._send_manager.record_success(app_type)
            self._emit_status(f"✓ Send verified ({old_count} → {new_count})")
            if self.on_send_result:
                self.on_send_result(True, "Message sent successfully")
            return True

        if expected_text and config.chat_area:
            screenshot = self._reader.capture_window(window_info)
            if screenshot:
                chat_crop = screenshot.crop(config.chat_area)
                ocr_text = self._reader.extract_text(chat_crop)
                if expected_text in ocr_text:
                    self._send_manager.record_success(app_type)
                    self._emit_status("✓ Send verified (OCR)")
                    if self.on_send_result:
                        self.on_send_result(True, "Message verified via OCR")
                    return True

        self._send_manager.record_failure(app_type)
        self._emit_status("✗ Send verification failed")
        if self.on_send_result:
            self.on_send_result(False, "Could not verify")
        
        if self._send_manager.get_config(app_type).fail_count >= 2:
            next_shortcut = self._send_manager.try_next_shortcut(app_type)
            if next_shortcut:
                self._emit_status(f"Trying alternative: {next_shortcut.value}")
                config.send_shortcut = next_shortcut
        
        return False

    def _get_message_count(self, window_info: WindowInfo, config: AutomationConfig) -> int:
        """Get current message count in chat."""
        if not config.chat_area:
            return 0
        messages = self._parser.parse_chat_area(window_info, config.chat_area)
        return len(messages)

    def test_send_shortcuts(self, window_info: WindowInfo, config: AutomationConfig,
                           test_message: str = "【发送测试】") -> SendShortcut | None:
        """Test different send shortcuts to find working one."""
        shortcuts_to_test = [SendShortcut.ENTER, SendShortcut.CTRL_ENTER, SendShortcut.SHIFT_ENTER]

        for shortcut in shortcuts_to_test:
            send_config = self._send_manager.get_config(config.app_type)
            send_config.shortcut = shortcut
            
            self._emit_status(f"Testing {shortcut.value}...")
            if self.send_message(test_message, window_info, config):
                if self.verify_send(window_info, config, test_message):
                    self._emit_status(f"✓ {shortcut.value} works!")
                    return shortcut
        
        return None

    def get_send_info(self) -> dict:
        """Get detailed send configuration info."""
        if not self._config:
            return {"configured": False}
        send_config = self._send_manager.get_config(self._config.app_type)
        return {
            "configured": True,
            "app_name": self._config.app_type,
            "send_mode": send_config.shortcut.value,
            "has_button": send_config.has_button,
            "verified": send_config.verified,
            "success_count": send_config.success_count,
            "fail_count": send_config.fail_count,
            "confidence": f"{send_config.confidence:.0%}",
            "status": self._send_manager.get_status(self._config.app_type),
        }

    def _emit_status(self, msg: str) -> None:
        logger.info(msg)
        if self.on_status:
            self.on_status(msg)

    def is_ready(self) -> bool:
        return self._config is not None and self._config.chat_area is not None and self._config.input_area is not None

    def get_status_text(self) -> str:
        if not self._config:
            return "Not configured"
        info = self.get_send_info()
        return f"Ready: {info['app_name']} | Send: {info['status']} | Method: {self._config.detection_method}"
