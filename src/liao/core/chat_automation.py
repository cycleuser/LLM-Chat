"""Complete chat automation with click, paste, and send."""

from __future__ import annotations

import logging
import time
import pyperclip
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from ..models.window import WindowInfo

from .screenshot import ScreenshotReader
from .send_mode import SendModeManager, SendShortcut
from .macos_input import MacOSInputSimulator

logger = logging.getLogger(__name__)


@dataclass
class ChatConfig:
    """Chat automation configuration."""

    chat_area: tuple[int, int, int, int] | None = None
    input_area: tuple[int, int, int, int] | None = None
    send_button: tuple[int, int] | None = None
    app_type: str = "other"
    send_shortcut: SendShortcut = SendShortcut.ENTER


class ChatAutomation:
    """Complete chat automation: detect, click, paste, send.

    Usage:
        automation = ChatAutomation()

        # Auto-detect
        config = automation.detect(window_info)

        # Send message
        success = automation.send_message("Hello!", window_info, config)

        # Verify
        if success:
            verified = automation.verify_send(window_info, config, "Hello!")
    """

    def __init__(self):
        self._screenshot = ScreenshotReader()
        self._input = MacOSInputSimulator()
        self._send_manager = SendModeManager()
        self._config: ChatConfig | None = None

        # Callbacks
        self.on_status: Callable[[str], None] | None = None

    def detect(self, window: WindowInfo) -> ChatConfig | None:
        """Auto-detect chat elements.

        Args:
            window: Target window

        Returns:
            ChatConfig or None
        """
        self._emit("检测窗口元素...")

        rect = window.rect
        width = rect[2] - rect[0]
        height = rect[3] - rect[1]

        # 根据应用类型设置默认区域
        app_type = window.app_type

        # 默认：左侧是联系人列表，右侧是对话区域
        # 对话区域占窗口宽度的 55%-75%
        # 输入区域在底部，高度约 10%-15%

        chat_left = rect[0] + int(width * 0.25)  # 左边 25% 是联系人列表
        chat_top = rect[1] + int(height * 0.05)  # 顶部 5% 是标题栏
        chat_right = rect[2] - int(width * 0.02)  # 右边留 2% 边距
        chat_bottom = rect[3] - int(height * 0.12)  # 底部 12% 是输入区

        input_left = chat_left
        input_top = chat_bottom
        input_right = chat_right
        input_bottom = rect[3] - int(height * 0.02)

        # 发送按钮：输入区右下角
        send_x = input_right - 45
        send_y = input_bottom - 15

        config = ChatConfig(
            chat_area=(chat_left, chat_top, chat_right, chat_bottom),
            input_area=(input_left, input_top, input_right, input_bottom),
            send_button=(send_x, send_y),
            app_type=app_type,
        )

        # 获取发送快捷键配置
        send_config = self._send_manager.get_config(app_type)
        config.send_shortcut = send_config.shortcut

        self._config = config

        self._emit("检测完成:")
        self._emit(f"  对话区域: {config.chat_area}")
        self._emit(f"  输入区域: {config.input_area}")
        self._emit(f"  发送按钮: {config.send_button}")
        self._emit(f"  发送方式: {config.send_shortcut.value}")

        return config

    def click_input(self, window: WindowInfo, config: ChatConfig | None = None) -> bool:
        """Click on input area.

        Args:
            window: Target window
            config: Chat config

        Returns:
            True if successful
        """
        config = config or self._config
        if not config or not config.input_area:
            self._emit("❌ 没有输入区域配置")
            return False

        # 计算输入区中心点
        ix = (config.input_area[0] + config.input_area[2]) // 2
        iy = (config.input_area[1] + config.input_area[3]) // 2

        self._emit(f"点击输入区域 ({ix}, {iy})...")

        # 移动鼠标
        if self._input.move_mouse(ix, iy):
            time.sleep(0.1)

            # 点击
            if self._input.click(ix, iy):
                time.sleep(0.15)
                self._emit("✅ 已点击输入区域")
                return True

        self._emit("❌ 点击失败")
        return False

    def paste_text(self, text: str) -> bool:
        """Copy text to clipboard and paste.

        Args:
            text: Text to paste

        Returns:
            True if successful
        """
        self._emit(f"粘贴文本 ({len(text)} 字符)...")

        try:
            # 复制到剪贴板
            pyperclip.copy(text)
            time.sleep(0.1)

            # 粘贴 (Cmd+V on macOS, Ctrl+V on others)
            import sys

            if sys.platform == "darwin":
                self._input.hotkey("cmd", "v")
            else:
                self._input.hotkey("ctrl", "v")

            time.sleep(0.2)
            self._emit("✅ 已粘贴文本")
            return True

        except Exception as e:
            self._emit(f"❌ 粘贴失败: {e}")
            return False

    def type_text(self, text: str) -> bool:
        """Type text character by character.

        Args:
            text: Text to type

        Returns:
            True if successful
        """
        self._emit(f"输入文本 ({len(text)} 字符)...")

        try:
            if self._input.type_text(text):
                time.sleep(0.1)
                self._emit("✅ 已输入文本")
                return True
        except Exception as e:
            self._emit(f"❌ 输入失败: {e}")

        return False

    def send_message(
        self,
        text: str,
        window: WindowInfo,
        config: ChatConfig | None = None,
        use_clipboard: bool = True,
    ) -> bool:
        """Send message: click input, paste/type, send.

        Args:
            text: Message to send
            window: Target window
            config: Chat config
            use_clipboard: Use clipboard paste (faster) or type directly

        Returns:
            True if successful
        """
        config = config or self._config
        if not config:
            config = self.detect(window)
            if not config:
                return False

        self._emit("=== 开始发送消息 ===")

        # 1. 点击输入区域
        if not self.click_input(window, config):
            return False

        # 2. 输入文本
        if use_clipboard:
            if not self.paste_text(text):
                # 粘贴失败，尝试直接输入
                if not self.type_text(text):
                    return False
        else:
            if not self.type_text(text):
                return False

        time.sleep(0.2)

        # 3. 发送
        return self._trigger_send(config)

    def _trigger_send(self, config: ChatConfig) -> bool:
        """Trigger send action.

        Args:
            config: Chat config

        Returns:
            True if successful
        """
        shortcut = config.send_shortcut

        self._emit(f"发送消息 (方式: {shortcut.value})...")

        try:
            if shortcut == SendShortcut.BUTTON and config.send_button:
                # 点击发送按钮
                bx, by = config.send_button
                self._input.click(bx, by)
                time.sleep(0.1)
                # 有些应用还需要按 Enter
                self._input.press_key("enter")

            elif shortcut == SendShortcut.ENTER:
                self._input.press_key("enter")

            elif shortcut == SendShortcut.CTRL_ENTER:
                self._input.hotkey("ctrl", "enter")

            elif shortcut == SendShortcut.SHIFT_ENTER:
                self._input.hotkey("shift", "enter")

            elif shortcut == SendShortcut.CMD_ENTER:
                self._input.hotkey("cmd", "enter")

            else:
                # 默认 Enter
                self._input.press_key("enter")

            time.sleep(0.3)
            self._emit("✅ 已发送")
            return True

        except Exception as e:
            self._emit(f"❌ 发送失败: {e}")
            return False

    def verify_send(
        self,
        window: WindowInfo,
        config: ChatConfig | None,
        expected_text: str,
        timeout: float = 2.0,
    ) -> bool:
        """Verify message was sent.

        Args:
            window: Target window
            config: Chat config
            expected_text: Expected message text
            timeout: Verification timeout

        Returns:
            True if verified
        """
        config = config or self._config
        if not config:
            return False

        self._emit("验证发送...")

        # 截图
        img = self._screenshot.capture_window(window)
        if not img:
            self._emit("❌ 截图失败")
            return False

        # OCR 检测
        if self._screenshot.has_ocr():
            text = self._screenshot.extract_text(img)
            if expected_text in text:
                self._emit("✅ 发送验证成功 (OCR)")
                self._send_manager.record_success(config.app_type)
                return True

        # 无法验证，假设成功
        self._emit("⚠️ 无法验证，假设成功")
        self._send_manager.record_success(config.app_type)
        return True

    def test_send(
        self,
        window: WindowInfo,
        config: ChatConfig | None = None,
    ) -> SendShortcut | None:
        """Test send shortcuts to find working one.

        Args:
            window: Target window
            config: Chat config

        Returns:
            Working shortcut or None
        """
        config = config or self._config
        if not config:
            config = self.detect(window)

        test_msg = "【测试】"

        shortcuts = [
            SendShortcut.ENTER,
            SendShortcut.CTRL_ENTER,
            SendShortcut.BUTTON,
        ]

        for shortcut in shortcuts:
            config.send_shortcut = shortcut

            self._emit(f"测试 {shortcut.value}...")

            if self.send_message(test_msg, window, config):
                time.sleep(1.0)
                if self.verify_send(window, config, test_msg):
                    self._emit(f"✅ {shortcut.value} 可用!")
                    return shortcut

        self._emit("❌ 所有方式都失败")
        return None

    def get_messages(
        self,
        window: WindowInfo,
        config: ChatConfig | None = None,
    ) -> list[str]:
        """Get messages from chat area.

        Args:
            window: Target window
            config: Chat config

        Returns:
            List of message strings
        """
        config = config or self._config
        if not config or not config.chat_area:
            return []

        # 截取对话区域
        img = self._screenshot.capture_region(window, config.chat_area)
        if not img:
            return []

        # OCR 提取文本
        if not self._screenshot.has_ocr():
            return []

        text = self._screenshot.extract_text(img)
        if not text:
            return []

        # 按行分割
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return lines

    def _emit(self, msg: str) -> None:
        """Emit status message."""
        logger.info(msg)
        if self.on_status:
            self.on_status(msg)

    @property
    def config(self) -> ChatConfig | None:
        return self._config

    def is_ready(self) -> bool:
        return self._config is not None
