"""Send mode configuration and testing."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class SendShortcut(Enum):
    """Available send shortcuts."""

    ENTER = "enter"
    CTRL_ENTER = "ctrl_enter"
    SHIFT_ENTER = "shift_enter"
    ALT_ENTER = "alt_enter"
    CMD_ENTER = "cmd_enter"  # macOS
    CTRL_SPACE = "ctrl_space"
    BUTTON = "button"


@dataclass
class SendConfig:
    """Configuration for sending messages."""

    shortcut: SendShortcut = SendShortcut.ENTER
    has_button: bool = False
    button_pos: tuple[int, int] | None = None
    verified: bool = False
    success_count: int = 0
    fail_count: int = 0
    last_verified: float = 0.0
    notes: str = ""

    @property
    def is_reliable(self) -> bool:
        """Check if this config is reliable."""
        return self.verified and self.success_count > 0 and self.fail_count == 0

    @property
    def confidence(self) -> float:
        """Calculate confidence score."""
        total = self.success_count + self.fail_count
        if total == 0:
            return 0.0
        return self.success_count / total


# Default send configs by app type
DEFAULT_SEND_CONFIGS: dict[str, SendConfig] = {
    "wechat": SendConfig(
        shortcut=SendShortcut.BUTTON,
        has_button=True,
        notes="WeChat: Button or Enter",
    ),
    "wecom": SendConfig(
        shortcut=SendShortcut.BUTTON,
        has_button=True,
        notes="WeCom: Button or Enter",
    ),
    "qq": SendConfig(
        shortcut=SendShortcut.CTRL_ENTER,
        notes="QQ: Ctrl+Enter (configurable in QQ settings)",
    ),
    "telegram": SendConfig(
        shortcut=SendShortcut.ENTER,
        notes="Telegram: Enter (Shift+Enter for new line)",
    ),
    "dingtalk": SendConfig(
        shortcut=SendShortcut.ENTER,
        notes="DingTalk: Enter",
    ),
    "feishu": SendConfig(
        shortcut=SendShortcut.ENTER,
        notes="Feishu: Enter",
    ),
    "slack": SendConfig(
        shortcut=SendShortcut.ENTER,
        notes="Slack: Enter",
    ),
    "discord": SendConfig(
        shortcut=SendShortcut.ENTER,
        notes="Discord: Enter",
    ),
    "teams": SendConfig(
        shortcut=SendShortcut.CTRL_ENTER,
        notes="Teams: Ctrl+Enter",
    ),
    "whatsapp": SendConfig(
        shortcut=SendShortcut.ENTER,
        notes="WhatsApp: Enter",
    ),
    "line": SendConfig(
        shortcut=SendShortcut.CTRL_ENTER,
        notes="LINE: Ctrl+Enter",
    ),
    "other": SendConfig(
        shortcut=SendShortcut.ENTER,
        notes="Unknown app: trying Enter first",
    ),
}


class SendModeManager:
    """Manages send mode detection and configuration.

    Features:
    - Auto-detect send shortcut by testing
    - Track success/failure rates
    - Persist successful configurations
    - Adapt to user settings

    Example:
        manager = SendModeManager()
        config = manager.get_config("wechat")

        # Test send shortcut
        if manager.test_shortcut(window_info, config, "enter"):
            manager.record_success(config)
        else:
            manager.record_failure(config)
            manager.try_next_shortcut(config)
    """

    def __init__(self):
        self._configs: dict[str, SendConfig] = {}
        self._last_message_count: dict[str, int] = {}
        self._load_defaults()

    def _load_defaults(self):
        """Load default configurations."""
        for app_type, config in DEFAULT_SEND_CONFIGS.items():
            self._configs[app_type] = SendConfig(
                shortcut=config.shortcut,
                has_button=config.has_button,
                button_pos=config.button_pos,
                notes=config.notes,
            )

    def get_config(self, app_type: str) -> SendConfig:
        """Get send config for app type."""
        if app_type not in self._configs:
            self._configs[app_type] = SendConfig(
                shortcut=SendShortcut.ENTER,
                notes=f"Auto-detected for {app_type}",
            )
        return self._configs[app_type]

    def set_config(self, app_type: str, config: SendConfig) -> None:
        """Set send config for app type."""
        self._configs[app_type] = config

    def get_shortcut_keys(self, shortcut: SendShortcut) -> tuple[str, ...]:
        """Get key names for shortcut."""
        mapping = {
            SendShortcut.ENTER: ("enter",),
            SendShortcut.CTRL_ENTER: ("ctrl", "enter"),
            SendShortcut.SHIFT_ENTER: ("shift", "enter"),
            SendShortcut.ALT_ENTER: ("alt", "enter"),
            SendShortcut.CMD_ENTER: ("cmd", "enter"),
            SendShortcut.CTRL_SPACE: ("ctrl", "space"),
            SendShortcut.BUTTON: (),
        }
        return mapping.get(shortcut, ("enter",))

    def record_success(self, app_type: str) -> None:
        """Record successful send."""
        config = self.get_config(app_type)
        config.success_count += 1
        config.last_verified = time.time()
        if config.success_count >= 3:
            config.verified = True
        logger.info(f"Send success for {app_type}: {config.success_count}/{config.fail_count}")

    def record_failure(self, app_type: str) -> None:
        """Record failed send."""
        config = self.get_config(app_type)
        config.fail_count += 1
        logger.warning(f"Send failure for {app_type}: {config.success_count}/{config.fail_count}")

    def try_next_shortcut(self, app_type: str) -> SendShortcut | None:
        """Try next shortcut when current one fails.

        Returns:
            Next shortcut to try, or None if all tried
        """
        config = self.get_config(app_type)

        # Order of shortcuts to try
        shortcut_order = [
            SendShortcut.ENTER,
            SendShortcut.CTRL_ENTER,
            SendShortcut.SHIFT_ENTER,
            SendShortcut.ALT_ENTER,
        ]

        # Find current position
        try:
            current_idx = shortcut_order.index(config.shortcut)
            if current_idx < len(shortcut_order) - 1:
                next_shortcut = shortcut_order[current_idx + 1]
                config.shortcut = next_shortcut
                logger.info(f"Switching to {next_shortcut.value} for {app_type}")
                return next_shortcut
        except ValueError:
            # Current shortcut not in order, use first
            config.shortcut = shortcut_order[0]
            return shortcut_order[0]

        return None

    def detect_send_mode(
        self,
        app_type: str,
        has_button: bool,
        button_pos: tuple[int, int] | None = None,
    ) -> SendConfig:
        """Detect send mode based on app type and UI.

        Args:
            app_type: Application type
            has_button: Whether send button is visible
            button_pos: Send button position

        Returns:
            SendConfig for this app
        """
        config = self.get_config(app_type)
        config.has_button = has_button
        config.button_pos = button_pos

        # If button exists, prefer it
        if has_button and button_pos:
            config.shortcut = SendShortcut.BUTTON

        return config

    def should_verify(self, app_type: str) -> bool:
        """Check if we should verify send mode."""
        config = self.get_config(app_type)

        # Verify if not verified yet
        if not config.verified:
            return True

        # Re-verify periodically (every 10 sends)
        if config.success_count > 0 and config.success_count % 10 == 0:
            return True

        return False

    def get_status(self, app_type: str) -> str:
        """Get human-readable status."""
        config = self.get_config(app_type)
        status = f"{config.shortcut.value}"

        if config.verified:
            status += f" ✓ ({config.success_count} successful)"
        elif config.fail_count > 0:
            status += f" ✗ ({config.fail_count} failed)"

        return status

    def to_dict(self) -> dict[str, dict]:
        """Export configs to dict."""
        return {
            app_type: {
                "shortcut": config.shortcut.value,
                "has_button": config.has_button,
                "button_pos": config.button_pos,
                "verified": config.verified,
                "success_count": config.success_count,
                "fail_count": config.fail_count,
            }
            for app_type, config in self._configs.items()
        }

    def from_dict(self, data: dict[str, dict]) -> None:
        """Import configs from dict."""
        for app_type, app_data in data.items():
            if app_type in self._configs:
                config = self._configs[app_type]
                config.shortcut = SendShortcut(app_data.get("shortcut", "enter"))
                config.has_button = app_data.get("has_button", False)
                config.button_pos = app_data.get("button_pos")
                config.verified = app_data.get("verified", False)
                config.success_count = app_data.get("success_count", 0)
                config.fail_count = app_data.get("fail_count", 0)
