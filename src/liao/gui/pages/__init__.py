"""Page widgets for multi-page GUI."""

from .base_page import BasePage
from .connection_page import ConnectionPage
from .window_page import WindowPage
from .area_page import AreaPage
from .kb_page import KBPage
from .chat_page import ChatPage
from .kb_settings_page import KBSettingsPage

__all__ = [
    "BasePage",
    "ConnectionPage",
    "WindowPage",
    "AreaPage",
    "KBPage",
    "ChatPage",
    "KBSettingsPage",
]
