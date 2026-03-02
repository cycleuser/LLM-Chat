"""
LLM Chat - Standalone chat automation tool with Ollama integration.

Extracted from the TieChui project. Self-contained, no tiechui package imports.
Run: python llm_chat.py

Dependencies:
    pip install PySide6 requests pyautogui pyperclip Pillow pywin32 numpy easyocr
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import io
import json
import logging
import re
import struct
import sys
import time
import threading
from dataclasses import dataclass, field
from typing import Any, Iterator

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from PySide6.QtCore import QPoint, QRect, Qt, QThread, Signal, Slot
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("llm_chat")

# ============================================================================
# Section 1: Data Models
# ============================================================================

@dataclass
class WindowInfo:
    hwnd: int
    title: str
    class_name: str
    rect: tuple[int, int, int, int]  # left, top, right, bottom
    app_type: str  # "wechat", "wecom", "qq", "other"

    @property
    def width(self) -> int:
        return self.rect[2] - self.rect[0]

    @property
    def height(self) -> int:
        return self.rect[3] - self.rect[1]

    @property
    def center(self) -> tuple[int, int]:
        return (self.rect[0] + self.rect[2]) // 2, (self.rect[1] + self.rect[3]) // 2


@dataclass
class ChatMessage:
    sender: str  # "self" or "other"
    content: str
    msg_type: str = "text"
    timestamp: str | None = None


@dataclass
class AreaDetectionResult:
    chat_area_rect: tuple[int, int, int, int]
    input_area_rect: tuple[int, int, int, int]
    method: str = "heuristic"
    confidence: float = 0.5


class ConversationMemory:
    """Structured conversation memory with sender attribution."""

    def __init__(self, contact_name: str = "对方"):
        self._contact_name = contact_name
        self._messages: list[ChatMessage] = []

    def add_self_message(self, content: str) -> None:
        self._messages.append(ChatMessage(sender="self", content=content))

    def add_other_message(self, content: str) -> None:
        self._messages.append(ChatMessage(sender="other", content=content))

    @property
    def messages(self) -> list[ChatMessage]:
        return self._messages

    def format_for_llm(self, max_messages: int = 20) -> str:
        """Format conversation for LLM with highlighted latest exchange."""
        msgs = self._messages[-max_messages:]
        if not msgs:
            return "[对话记录为空]"

        # Find the boundary between history and the latest exchange
        last_other_idx = None
        for i in range(len(msgs) - 1, -1, -1):
            if msgs[i].sender == "other":
                last_other_idx = i
                break

        if last_other_idx is not None and last_other_idx > 0:
            # Split: history + current exchange
            history = msgs[:last_other_idx]
            current = msgs[last_other_idx:]
            parts = []
            if history:
                parts.append("[对话历史]")
                for m in history:
                    sender = "我" if m.sender == "self" else "对方"
                    parts.append(f"{sender}: {m.content}" if m.msg_type == "text" else f"{sender}: [{m.msg_type}]")
                parts.append("")
            parts.append("[当前 - 请回复这条]")
            for m in current:
                sender = "我" if m.sender == "self" else "对方"
                parts.append(f"{sender}: {m.content}" if m.msg_type == "text" else f"{sender}: [{m.msg_type}]")
            return "\n".join(parts)
        else:
            # All messages, no clear latest exchange
            lines = ["[对话记录]"]
            for m in msgs:
                sender = "我" if m.sender == "self" else "对方"
                lines.append(f"{sender}: {m.content}" if m.msg_type == "text" else f"{sender}: [{m.msg_type}]")
            return "\n".join(lines)

    def format_for_display_html(self, max_messages: int = 20) -> str:
        msgs = self._messages[-max_messages:]
        if not msgs:
            return "<p style='color:#999; text-align:center;'>对话记录为空</p>"
        parts = [
            "<html><body style='margin:4px; font-family:Microsoft YaHei,SimHei,sans-serif; font-size:13px;'>"
        ]
        for m in msgs:
            content = (
                m.content.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace("\n", "<br>")
            )
            if m.msg_type != "text":
                content = f"[{m.msg_type}]"
            if m.sender == "self":
                parts.append(
                    "<table width='100%' cellpadding='0' cellspacing='0'><tr>"
                    "<td width='25%'></td><td align='right'><div style='margin:3px 0;'>"
                    "<span style='font-size:11px; color:#888;'>我</span><br>"
                    f"<span style='background-color:#95EC69; color:#000; padding:6px 10px; border-radius:6px;'>{content}</span>"
                    "</div></td></tr></table>"
                )
            else:
                parts.append(
                    "<table width='100%' cellpadding='0' cellspacing='0'><tr>"
                    "<td align='left'><div style='margin:3px 0;'>"
                    "<span style='font-size:11px; color:#888;'>对方</span><br>"
                    f"<span style='background-color:#FFFFFF; color:#000; padding:6px 10px; border-radius:6px; border:1px solid #E0E0E0;'>{content}</span>"
                    "</div></td><td width='25%'></td></tr></table>"
                )
        parts.append("</body></html>")
        return "".join(parts)

    def get_last_other_message(self) -> str | None:
        for m in reversed(self._messages):
            if m.sender == "other":
                return m.content
        return None

    def clear(self) -> None:
        self._messages.clear()


# ============================================================================
# Section 2: Ollama Client (simplified)
# ============================================================================

class OllamaClient:
    """Simplified Ollama HTTP client for chat and model listing."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = ""):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._session = self._build_session()

    @staticmethod
    def _build_session() -> requests.Session:
        session = requests.Session()
        retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[502, 503, 504])
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def list_models(self) -> list[dict[str, Any]]:
        try:
            resp = self._session.get(f"{self.base_url}/api/tags", timeout=10)
            resp.raise_for_status()
            return resp.json().get("models", [])
        except Exception as exc:
            logger.warning("Failed to list models: %s", exc)
            return []

    def model_names(self) -> list[str]:
        return [m.get("name", m.get("model", "")) for m in self.list_models()]

    def chat(self, messages: list[dict], temperature: float | None = None) -> str:
        model = self.model or self._pick_default()
        payload: dict[str, Any] = {"model": model, "messages": messages, "stream": False}
        if temperature is not None:
            payload["options"] = {"temperature": temperature}
        resp = self._session.post(f"{self.base_url}/api/chat", json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()["message"]["content"]

    def chat_stream(self, messages: list[dict], temperature: float | None = None) -> Iterator[str]:
        model = self.model or self._pick_default()
        payload: dict[str, Any] = {"model": model, "messages": messages, "stream": True}
        if temperature is not None:
            payload["options"] = {"temperature": temperature}
        resp = self._session.post(f"{self.base_url}/api/chat", json=payload, stream=True, timeout=300)
        resp.raise_for_status()
        for line in resp.iter_lines():
            if line:
                chunk = json.loads(line)
                token = chunk.get("message", {}).get("content", "")
                if token:
                    yield token

    def is_available(self) -> bool:
        try:
            resp = self._session.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def _pick_default(self) -> str:
        names = self.model_names()
        embed_patterns = ("embed", "nomic", "bge", "e5-", "mxbai")
        chat_models = [n for n in names if not any(p in n.lower() for p in embed_patterns)]
        return chat_models[0] if chat_models else (names[0] if names else "llama3")


# ============================================================================
# Section 3: Prompts
# ============================================================================

AUTO_CHAT_SYSTEM_PROMPT = """\
你正在模拟真实的即时聊天对话。

【核心原则】
你的每一条消息都必须严格基于对方刚才说的话来回应。
不要自说自话，不要偏离对方的话题。
绝对不要连续发送两条消息——每发一条必须等对方回复后再说。

【对话规则】
1. 每次只生成一条简短消息（1-3句话），像真实微信/QQ聊天
2. 语气要口语化、自然，像朋友之间聊天，不要书面语
3. 根据对方消息的长度调整你的回复长度：对方发短消息你也简短回复，对方发长消息你可以多说一点
4. 根据对方的语气调整你的语气：对方热情你也热情，对方冷淡你就收着点
5. 如果对方问了问题，优先回答问题
6. 绝对不要重复之前说过的话
7. 不要编造不存在的信息（如虚构的书名、电影名、人名等），如果不确定就坦诚地说不太清楚
8. 保持话题连贯：始终围绕对方说的话来回复，不要突然转换话题

【格式要求】
- 直接输出消息内容，只输出消息本身
- 不要加引号、书名号包裹整条消息
- 不要添加翻译、拼音、解释或任何括号注释
- 绝对不要添加"我："、"我: "或任何发送者前缀
- 用中文回复，除非用户提示词要求其他语言

【对话记忆】
你会收到标注了"我"和"对方"的完整对话记录。
务必基于完整上下文来回复，不要忽略之前的对话内容。
不要重复之前说过的话，也不要把对方说的话当成自己说的。

【回复检查】
生成前请确认:
- 这是对"对方"最新消息的直接回应
- 没有重复之前说过的话
- 没有编造不存在的信息
- 没有添加"我："或其他前缀
- 长度和语气匹配对方的消息

【用户设定】
{user_prompt}
"""

AUTO_CHAT_FIRST_MESSAGE_PROMPT = """\
这是对话的第一条消息，你要主动开启话题。

根据以下设定，生成一条自然的开场白（10-30个字）：
{user_prompt}

要求：简短、友好、像微信聊天的开场，不要像发邮件。直接输出消息内容，不要加任何前缀。\
"""

AUTO_CHAT_NO_REPLY_PROMPT = """\
对方已经 {wait_seconds} 秒没有回复了。

回顾最近的对话，然后选择:
1. 如果对方可能还在思考（比如你问了需要想一想的问题），输出 WAIT
2. 如果适合发一个自然的追问（不超过8个字，比如"在吗？""怎么样？"），直接输出追问内容
3. 不要催促、不要显得不耐烦

直接输出你的选择（WAIT 或 简短追问内容，不要加任何前缀）：\
"""


# ============================================================================
# Section 4: Win32 Input
# ============================================================================

# --- ctypes structures for SendInput ---

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000
KEYEVENTF_KEYUP = 0x0002
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
VK_CONTROL = 0x11
VK_RETURN = 0x0D
VK_BACK = 0x08
VK_DELETE = 0x2E
VK_ESCAPE = 0x1B
VK_MENU = 0x12  # Alt


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


def _send_input(*inputs: INPUT) -> int:
    arr = (INPUT * len(inputs))(*inputs)
    return ctypes.windll.user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))


def _abs_coords(x: int, y: int) -> tuple[int, int]:
    """Convert screen pixel coordinates to SendInput normalized 0-65535 range."""
    sm_xvscreen = ctypes.windll.user32.GetSystemMetrics(76)
    sm_yvscreen = ctypes.windll.user32.GetSystemMetrics(77)
    sm_cxvscreen = ctypes.windll.user32.GetSystemMetrics(78)
    sm_cyvscreen = ctypes.windll.user32.GetSystemMetrics(79)
    nx = int((x - sm_xvscreen) * 65535 / sm_cxvscreen)
    ny = int((y - sm_yvscreen) * 65535 / sm_cyvscreen)
    return nx, ny


def focus_window_hard(hwnd: int) -> bool:
    """Bring window to foreground using thread-attach trick."""
    try:
        user32 = ctypes.windll.user32
        SW_RESTORE = 9
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
            time.sleep(0.3)
        current = user32.GetForegroundWindow()
        cur_tid = user32.GetWindowThreadProcessId(current, None)
        tgt_tid = user32.GetWindowThreadProcessId(hwnd, None)
        if cur_tid != tgt_tid:
            user32.AttachThreadInput(cur_tid, tgt_tid, True)
        user32.keybd_event(0x12, 0, 0, 0)  # Alt down
        user32.keybd_event(0x12, 0, 2, 0)  # Alt up
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
        if cur_tid != tgt_tid:
            user32.AttachThreadInput(cur_tid, tgt_tid, False)
        time.sleep(0.15)
        return True
    except Exception as exc:
        logger.warning("focus_window_hard failed: %s", exc)
        return False


def move_to(x: int, y: int, duration: float = 0, steps: int = 20) -> None:
    """Move mouse to (x, y) with optional smooth animation."""
    user32 = ctypes.windll.user32
    pt = ctypes.wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    sx, sy = pt.x, pt.y
    if duration <= 0 or steps <= 1:
        user32.SetCursorPos(x, y)
        return
    for i in range(1, steps + 1):
        t = i / steps
        t = t * t * (3 - 2 * t)  # ease in-out
        cx = int(sx + (x - sx) * t)
        cy = int(sy + (y - sy) * t)
        user32.SetCursorPos(cx, cy)
        time.sleep(duration / steps)


def click(x: int | None = None, y: int | None = None) -> None:
    """Click at (x, y) or current position."""
    if x is not None and y is not None:
        nx, ny = _abs_coords(x, y)
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
        _send_input(down, up)
    else:
        down = INPUT(type=INPUT_MOUSE)
        down.union.mi = MOUSEINPUT(dx=0, dy=0, mouseData=0, dwFlags=MOUSEEVENTF_LEFTDOWN, time=0, dwExtraInfo=None)
        up = INPUT(type=INPUT_MOUSE)
        up.union.mi = MOUSEINPUT(dx=0, dy=0, mouseData=0, dwFlags=MOUSEEVENTF_LEFTUP, time=0, dwExtraInfo=None)
        _send_input(down, up)


def move_and_click(x: int, y: int, duration: float = 0.2) -> None:
    move_to(x, y, duration=duration)
    time.sleep(0.05)
    click(x, y)


_VK_MAP = {
    "enter": VK_RETURN, "return": VK_RETURN,
    "backspace": VK_BACK, "delete": VK_DELETE,
    "escape": VK_ESCAPE, "esc": VK_ESCAPE,
    "ctrl": VK_CONTROL, "control": VK_CONTROL,
    "alt": VK_MENU, "tab": 0x09, "shift": 0x10,
    "a": 0x41, "c": 0x43, "v": 0x56, "x": 0x58, "z": 0x5A,
}


def press_key(key: str) -> None:
    vk = _VK_MAP.get(key.lower(), 0)
    if not vk:
        return
    down = INPUT(type=INPUT_KEYBOARD)
    down.union.ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=0, time=0, dwExtraInfo=None)
    up = INPUT(type=INPUT_KEYBOARD)
    up.union.ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=KEYEVENTF_KEYUP, time=0, dwExtraInfo=None)
    _send_input(down, up)


def hotkey(*keys: str) -> None:
    inputs = []
    for k in keys:
        vk = _VK_MAP.get(k.lower(), 0)
        if not vk:
            continue
        inp = INPUT(type=INPUT_KEYBOARD)
        inp.union.ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=0, time=0, dwExtraInfo=None)
        inputs.append(inp)
    for k in reversed(keys):
        vk = _VK_MAP.get(k.lower(), 0)
        if not vk:
            continue
        inp = INPUT(type=INPUT_KEYBOARD)
        inp.union.ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=KEYEVENTF_KEYUP, time=0, dwExtraInfo=None)
        inputs.append(inp)
    if inputs:
        _send_input(*inputs)


def send_enter() -> None:
    press_key("enter")


def click_send_button(x: int, y: int, hwnd: int | None = None, move_duration: float = 0.3) -> None:
    if hwnd:
        focus_window_hard(hwnd)
        time.sleep(0.1)
    move_and_click(x, y, duration=move_duration)


def click_and_type(
    x: int, y: int, text: str,
    hwnd: int | None = None, clear_first: bool = True, move_duration: float = 0.3,
) -> bool:
    """Focus window, move to input, click, clear, paste text."""
    try:
        import pyperclip
    except ImportError:
        logger.error("pyperclip not installed")
        return False

    if hwnd:
        focus_window_hard(hwnd)
        time.sleep(0.15)

    move_to(x, y, duration=move_duration)
    time.sleep(0.05)
    click(x, y)
    time.sleep(0.1)
    click(x, y)
    time.sleep(0.1)

    if clear_first:
        hotkey("ctrl", "a")
        time.sleep(0.05)
        press_key("delete")
        time.sleep(0.05)

    pyperclip.copy(text)
    time.sleep(0.05)
    hotkey("ctrl", "v")
    time.sleep(0.1)
    return True


# ============================================================================
# Section 5: Window Manager
# ============================================================================

CHAT_APP_PATTERNS = {
    "wechat": ["WeChatMainWndForPC", "ChatWnd", "微信"],
    "wecom": ["WeWorkWindow", "WeWorkMainWindow", "企业微信"],
    "qq": ["TXGuiFoundation", "QQMainWnd", "QQ"],
    "telegram": ["Telegram", "TelegramDesktop"],
    "dingtalk": ["钉钉", "DingTalk"],
    "feishu": ["飞书", "Lark"],
}


class WindowManager:
    def __init__(self):
        self._win32gui = None
        self._win32con = None
        try:
            import win32con
            import win32gui
            self._win32gui = win32gui
            self._win32con = win32con
        except ImportError:
            logger.warning("pywin32 not available")

    def is_available(self) -> bool:
        return self._win32gui is not None

    def get_all_visible_windows(self) -> list[WindowInfo]:
        if not self.is_available():
            return []
        windows: list[WindowInfo] = []

        def enum_cb(hwnd, _):
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
                windows.append(WindowInfo(hwnd=hwnd, title=title, class_name=cls, rect=rect, app_type=app_type))
            except Exception:
                pass
            return True

        self._win32gui.EnumWindows(enum_cb, None)
        windows.sort(key=lambda w: w.title.lower())
        return windows

    @staticmethod
    def _detect_app_type(title: str, class_name: str) -> str:
        tl, cl = title.lower(), class_name.lower()
        for app_type, patterns in CHAT_APP_PATTERNS.items():
            for p in patterns:
                if p.lower() in tl or p.lower() in cl:
                    return app_type
        return "other"

    def get_window_by_hwnd(self, hwnd: int) -> WindowInfo | None:
        if not self.is_available():
            return None
        try:
            if not self._win32gui.IsWindow(hwnd):
                return None
            title = self._win32gui.GetWindowText(hwnd)
            cls = self._win32gui.GetClassName(hwnd)
            rect = self._win32gui.GetWindowRect(hwnd)
            return WindowInfo(hwnd=hwnd, title=title, class_name=cls, rect=rect,
                              app_type=self._detect_app_type(title, cls))
        except Exception:
            return None

    def refresh_window_info(self, window: WindowInfo) -> WindowInfo | None:
        return self.get_window_by_hwnd(window.hwnd)


# ============================================================================
# Section 6: Screenshot Reader
# ============================================================================

class ScreenshotReader:
    def __init__(self):
        self._pyautogui = None
        self._pil = None
        self._ocr_reader = None
        self._ocr_type = None
        self._load_deps()

    def _load_deps(self):
        try:
            import pyautogui
            self._pyautogui = pyautogui
        except ImportError:
            logger.warning("pyautogui not available")
        try:
            from PIL import Image
            self._pil = Image
        except ImportError:
            logger.warning("Pillow not available")
        self._init_ocr()

    def _init_ocr(self):
        try:
            import easyocr
            self._ocr_reader = easyocr.Reader(["ch_sim", "en"], gpu=False, verbose=False)
            self._ocr_type = "easyocr"
            logger.info("Using EasyOCR")
            return
        except (ImportError, Exception):
            pass
        try:
            from rapidocr_onnxruntime import RapidOCR
            self._ocr_reader = RapidOCR()
            self._ocr_type = "rapidocr"
            logger.info("Using RapidOCR")
            return
        except (ImportError, Exception):
            pass
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            self._ocr_reader = pytesseract
            self._ocr_type = "pytesseract"
            logger.info("Using pytesseract")
            return
        except (ImportError, Exception):
            pass
        logger.warning("No OCR engine available. Install: pip install easyocr")

    def is_available(self) -> bool:
        return self._pyautogui is not None and self._pil is not None

    def has_ocr(self) -> bool:
        return self._ocr_reader is not None

    def get_ocr_status(self) -> str:
        return f"OCR: {self._ocr_type}" if self._ocr_type else "OCR 不可用"

    def capture_window(self, window_info: WindowInfo):
        if not self.is_available():
            return None
        try:
            left, top, right, bottom = window_info.rect
            w, h = right - left, bottom - top
            if w <= 0 or h <= 0:
                return None
            return self._pyautogui.screenshot(region=(left, top, w, h))
        except Exception as e:
            logger.error("Screenshot failed: %s", e)
            return None

    def capture_region(self, window_info: WindowInfo, region_rect: tuple[int, int, int, int]):
        if not self.is_available():
            return None
        try:
            left, top, right, bottom = region_rect
            w, h = right - left, bottom - top
            if w <= 0 or h <= 0:
                return None
            return self._pyautogui.screenshot(region=(left, top, w, h))
        except Exception as e:
            logger.error("Region capture failed: %s", e)
            return None

    def extract_text(self, image) -> str:
        if not self._ocr_reader:
            return ""
        try:
            if self._ocr_type == "easyocr":
                import numpy as np
                results = self._ocr_reader.readtext(np.array(image))
                return "\n".join(text for (_, text, prob) in results if prob > 0.3)
            elif self._ocr_type == "rapidocr":
                import numpy as np
                result, _ = self._ocr_reader(np.array(image))
                return "\n".join(item[1] for item in result) if result else ""
            elif self._ocr_type == "pytesseract":
                return self._ocr_reader.image_to_string(image, lang="chi_sim+eng")
        except Exception as e:
            logger.error("OCR failed: %s", e)
        return ""

    def extract_with_bboxes(self, image) -> list[tuple[list, str, float]]:
        if not self._ocr_reader:
            return []
        try:
            if self._ocr_type == "easyocr":
                import numpy as np
                results = self._ocr_reader.readtext(np.array(image))
                return [(bbox, text, prob) for (bbox, text, prob) in results if prob > 0.3]
            elif self._ocr_type == "rapidocr":
                import numpy as np
                result, _ = self._ocr_reader(np.array(image))
                return [(item[0], item[1], item[2]) for item in result] if result else []
            elif self._ocr_type == "pytesseract":
                text = self._ocr_reader.image_to_string(image, lang="chi_sim+eng")
                w, h = image.size
                if text.strip():
                    return [([[0, 0], [w, 0], [w, h], [0, h]], text.strip(), 0.5)]
                return []
        except Exception as e:
            logger.error("OCR bbox failed: %s", e)
        return []

    def capture_and_extract(self, window_info: WindowInfo) -> tuple:
        screenshot = self.capture_window(window_info)
        if not screenshot:
            return None, ""
        text = self.extract_text(screenshot) if self.has_ocr() else ""
        return screenshot, text

    @staticmethod
    def image_to_bytes(image, fmt: str = "PNG") -> bytes:
        buf = io.BytesIO()
        image.save(buf, format=fmt)
        return buf.getvalue()


# ============================================================================
# Section 7: OCR Chat Parser
# ============================================================================

# System text patterns to filter (timestamps, status, media)
_SYSTEM_TEXT_PATTERNS = [
    re.compile(r"^\d{1,2}:\d{2}(:\d{2})?$"),
    re.compile(r"^(上午|下午|AM|PM)\s*\d{1,2}:\d{2}$", re.IGNORECASE),
    re.compile(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}$"),
    re.compile(r"^(昨天|前天|今天|星期[一二三四五六日天]|周[一二三四五六日天])$"),
    re.compile(r"^(已读|已撤回|对方正在输入|消息已发送|以下为新消息)"),
    re.compile(r"^\[(图片|语音|视频|文件|位置|名片|红包|转账)\]$"),
]


def _is_system_text(text: str) -> bool:
    text = text.strip()
    if len(text) < 2:
        return True
    for pat in _SYSTEM_TEXT_PATTERNS:
        if pat.search(text):
            return True
    return False


class OCRChatParser:
    """Parse OCR results into ChatMessage objects with sender attribution."""

    def __init__(self, screenshot_reader: ScreenshotReader):
        self._reader = screenshot_reader

    def parse_chat_area(self, window_info: WindowInfo, chat_rect: tuple[int, int, int, int]) -> list[ChatMessage]:
        image = self._reader.capture_region(window_info, chat_rect)
        if image is None:
            return []
        results = self._reader.extract_with_bboxes(image)
        if not results:
            return []
        img_w, img_h = image.size
        return self._parse_ocr_results(results, img_w, image)

    def _parse_ocr_results(self, results: list, image_width: int, image) -> list[ChatMessage]:
        # Filter system text, collect with position info
        items = []
        for bbox, text, conf in results:
            if _is_system_text(text):
                continue
            cx = sum(p[0] for p in bbox) / 4
            cy = sum(p[1] for p in bbox) / 4
            left_x = min(p[0] for p in bbox)
            right_x = max(p[0] for p in bbox)
            top_y = min(p[1] for p in bbox)
            side = "left" if cx < image_width * 0.5 else "right"
            items.append({"text": text, "cx": cx, "cy": cy, "left_x": left_x, "right_x": right_x,
                          "top_y": top_y, "side": side, "bbox": bbox})

        if not items:
            return []

        # Sort by vertical position
        items.sort(key=lambda b: b["cy"])

        # Group by vertical proximity AND horizontal side
        groups: list[list[dict]] = []
        for item in items:
            if groups and (item["cy"] - groups[-1][-1]["cy"]) < 40 and item["side"] == groups[-1][-1]["side"]:
                groups[-1].append(item)
            else:
                groups.append([item])

        # Convert groups to messages, skip very short fragments
        messages = []
        for group in groups:
            text = " ".join(g["text"] for g in group)
            # Skip fragments that are too short after stripping punctuation
            stripped = re.sub(r'[，,。.！!？?、：:；;…\-—""\'\'\"()\[\]【】]', '', text).strip()
            if len(stripped) < 2:
                continue
            first = group[0]
            left_margin = first["left_x"]
            right_margin = image_width - first["right_x"]
            sender = "other" if left_margin < right_margin else "self"
            messages.append(ChatMessage(sender=sender, content=text))

        return messages

    def find_new_messages(self, current: list[ChatMessage], memory: ConversationMemory) -> list[ChatMessage]:
        known = {self._normalize(m.content) for m in memory.messages}
        new = []
        for msg in current:
            norm = self._normalize(msg.content)
            if norm and norm not in known and not any(norm in k or k in norm for k in known if len(k) > 5):
                new.append(msg)
        return new

    def find_new_other_messages(self, current: list[ChatMessage], memory: ConversationMemory) -> list[ChatMessage]:
        new_others = [m for m in self.find_new_messages(current, memory) if m.sender == "other"]
        if not new_others:
            return []
        # Filter out fragments that are likely misattributed pieces of self's messages
        recent_self = [m.content for m in memory.messages if m.sender == "self"][-5:]
        return [m for m in new_others if not self._is_likely_fragment(m.content, recent_self)]

    @staticmethod
    def _is_likely_fragment(text: str, recent_self_texts: list[str]) -> bool:
        """Check if an 'other' message is likely a misattributed fragment of self's message."""
        text = text.strip()
        if not text:
            return True
        # Very short text ending in continuation punctuation
        if len(text) < 6 and text[-1:] in (",", "，", "、", "-", "—", ":", "："):
            return True
        # Very short text starting with continuation (e.g. "深刻," "好推荐-些。")
        stripped = re.sub(r'[，,。.！!？?、：:；;…\-—]', '', text).strip()
        if len(stripped) < 3:
            return True
        # Check if text is a substring of any recent self message
        normalized = text.replace(" ", "").replace("\n", "")
        for self_text in recent_self_texts:
            self_norm = self_text.replace(" ", "").replace("\n", "")
            if len(normalized) < len(self_norm) and normalized in self_norm:
                return True
        return False

    @staticmethod
    def _normalize(text: str) -> str:
        return text.strip().replace(" ", "").replace("\n", "")


# ============================================================================
# Section 8: Area Detector (OCR + heuristic, no vision)
# ============================================================================

class ChatAreaDetector:
    def __init__(self, screenshot_reader: ScreenshotReader):
        self._reader = screenshot_reader

    def detect_areas(self, window_info: WindowInfo) -> AreaDetectionResult:
        if self._reader.has_ocr():
            result = self._detect_via_ocr(window_info)
            if result is not None:
                return result
        return self._detect_via_heuristic(window_info)

    def _detect_via_ocr(self, window_info: WindowInfo) -> AreaDetectionResult | None:
        screenshot = self._reader.capture_window(window_info)
        if screenshot is None:
            return None
        bboxes = self._reader.extract_with_bboxes(screenshot)
        if len(bboxes) < 3:
            return None
        win_left, win_top, win_right, win_bottom = window_info.rect
        win_w, win_h = win_right - win_left, win_bottom - win_top
        if win_w <= 0 or win_h <= 0:
            return None

        bbox_data = []
        for bbox, text, _conf in bboxes:
            cx = sum(p[0] for p in bbox) / 4
            cy = sum(p[1] for p in bbox) / 4
            left_x = min(p[0] for p in bbox)
            right_x = max(p[0] for p in bbox)
            top_y = min(p[1] for p in bbox)
            bottom_y = max(p[1] for p in bbox)
            bbox_data.append({"cx": cx, "cy": cy, "left_x": left_x, "right_x": right_x,
                              "top_y": top_y, "bottom_y": bottom_y})

        # Find columns
        sorted_xs = sorted(b["cx"] for b in bbox_data)
        min_gap = win_w * 0.05
        boundaries = [0]
        for i in range(len(sorted_xs) - 1):
            if sorted_xs[i + 1] - sorted_xs[i] > min_gap:
                boundaries.append((sorted_xs[i] + sorted_xs[i + 1]) / 2)
        boundaries.append(win_w)
        columns = [(boundaries[i], boundaries[i + 1]) for i in range(len(boundaries) - 1)]

        # Score columns
        best_score, best_col = -1, None
        for cl, cr in columns:
            cw = cr - cl
            if cw < win_w * 0.15:
                continue
            col_bboxes = [b for b in bbox_data if cl < b["cx"] < cr]
            if len(col_bboxes) < 3:
                continue
            score = 0
            xs = [b["cx"] - cl for b in col_bboxes]
            x_spread = (max(xs) - min(xs)) / cw if cw > 0 else 0
            if x_spread > 0.30:
                score += 40
            elif x_spread > 0.20:
                score += 20
            score += min(len(col_bboxes) * 2, 30)
            score += int(((cl + cr) / 2 / win_w) * 25)
            width_ratio = cw / win_w
            if 0.25 <= width_ratio <= 0.60:
                score += 15
            ys = [b["cy"] for b in col_bboxes]
            if (max(ys) - min(ys)) / win_h > 0.50:
                score += 15
            if score > best_score:
                best_score, best_col = score, (cl, cr)

        if best_col is None:
            return None

        col_left, col_right = best_col
        col_bboxes = [b for b in bbox_data if col_left <= b["cx"] <= col_right]
        if not col_bboxes:
            return None
        col_ys = [b["cy"] for b in col_bboxes]

        # Find input boundary
        num_bands = 10
        band_h = win_h / num_bands
        bands = [0] * num_bands
        for y in col_ys:
            bands[min(int(y / band_h), num_bands - 1)] += 1
        input_top_y = win_h * 0.85
        for i in range(num_bands * 6 // 10, num_bands):
            upper_avg = sum(bands[:i]) / max(i, 1)
            if upper_avg > 0 and bands[i] < upper_avg * 0.3:
                input_top_y = i * band_h
                break

        chat_bboxes = [b for b in col_bboxes if b["cy"] < input_top_y] or col_bboxes
        header = win_h * 0.05
        chat_left_x = max(col_left, min(b["left_x"] for b in chat_bboxes) - win_w * 0.02)
        chat_right_x = min(col_right, max(b["right_x"] for b in chat_bboxes) + win_w * 0.02)
        chat_top_y = max(header, min(b["top_y"] for b in chat_bboxes) - win_h * 0.02)

        return AreaDetectionResult(
            chat_area_rect=(win_left + int(chat_left_x), win_top + int(chat_top_y),
                            win_left + int(chat_right_x), win_top + int(input_top_y)),
            input_area_rect=(win_left + int(chat_left_x), win_top + int(input_top_y),
                             win_left + int(chat_right_x), win_bottom),
            method="ocr", confidence=0.8,
        )

    @staticmethod
    def _detect_via_heuristic(window_info: WindowInfo) -> AreaDetectionResult:
        wl, wt, wr, wb = window_info.rect
        ww, wh = wr - wl, wb - wt
        return AreaDetectionResult(
            chat_area_rect=(wl + int(ww * 0.55), wt + int(wh * 0.05), wr - int(ww * 0.02), wb - int(wh * 0.15)),
            input_area_rect=(wl + int(ww * 0.55), wb - int(wh * 0.15), wr - int(ww * 0.02), wb),
            method="heuristic", confidence=0.3,
        )


# ============================================================================
# Section 9: PySide6 GUI
# ============================================================================

class AreaSelectionOverlay(QWidget):
    """Transparent full-screen overlay for manual area selection."""

    area_selected = Signal(tuple)
    selection_cancelled = Signal()

    def __init__(self, target_window_rect=None, purpose="chat", existing_rects=None, parent=None):
        super().__init__(parent)
        self._start_global = None
        self._current_global = None
        self._is_selecting = False
        self._target_rect = target_window_rect
        self._purpose = purpose
        self._existing_rects = existing_rects or {}
        screen = QApplication.primaryScreen()
        self._dpr = screen.devicePixelRatio() if screen else 1.0
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setCursor(QCursor(Qt.CrossCursor))
        if screen:
            self.setGeometry(screen.geometry())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        dpr = self._dpr

        if self._target_rect:
            tl, tt, tr, tb = self._target_rect
            wp = self.mapFromGlobal(QPoint(int(tl / dpr), int(tt / dpr)))
            painter.setPen(QPen(QColor(255, 255, 0), 2, Qt.DashLine))
            painter.drawRect(QRect(wp.x(), wp.y(), int((tr - tl) / dpr), int((tb - tt) / dpr)))

        for name, rect in self._existing_rects.items():
            if rect is None:
                continue
            rl, rt, rr, rb = rect
            p1 = self.mapFromGlobal(QPoint(int(rl / dpr), int(rt / dpr)))
            r = QRect(p1.x(), p1.y(), int((rr - rl) / dpr), int((rb - rt) / dpr))
            color = {"chat": QColor(0, 200, 0), "input": QColor(0, 150, 255), "send": QColor(255, 165, 0)}.get(name, QColor(200, 200, 200))
            painter.setPen(QPen(color, 2, Qt.DashLine))
            painter.drawRect(r)

        if self._start_global and self._current_global:
            sl = self.mapFromGlobal(self._start_global)
            cl = self.mapFromGlobal(self._current_global)
            r = QRect(sl, cl).normalized()
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(r, Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            color = {"chat": QColor(0, 200, 0), "input": QColor(0, 150, 255)}.get(self._purpose, QColor(255, 165, 0))
            painter.setPen(QPen(color, 3, Qt.SolidLine))
            painter.drawRect(r)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(r.bottomRight() + QPoint(-80, 20), f"{r.width()} x {r.height()}")

        painter.setPen(QColor(255, 255, 255))
        labels = {"chat": "请框选【对话消息区域】(绿色)，按 ESC 取消",
                  "input": "请框选【输入框区域】(蓝色)，按 ESC 取消"}
        painter.drawText(20, 30, labels.get(self._purpose, "请框选【发送按钮】(橙色)，按 ESC 取消"))
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._start_global = event.globalPosition().toPoint()
            self._current_global = self._start_global
            self._is_selecting = True
            self.update()

    def mouseMoveEvent(self, event):
        if self._is_selecting:
            self._current_global = event.globalPosition().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._is_selecting:
            self._is_selecting = False
            if self._start_global and self._current_global:
                left = min(self._start_global.x(), self._current_global.x())
                top = min(self._start_global.y(), self._current_global.y())
                right = max(self._start_global.x(), self._current_global.x())
                bottom = max(self._start_global.y(), self._current_global.y())
                if (right - left) > 30 and (bottom - top) > 30:
                    dpr = self._dpr
                    self.area_selected.emit((int(left * dpr), int(top * dpr), int(right * dpr), int(bottom * dpr)))
                    self.close()
                else:
                    self._start_global = self._current_global = None
                    self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.selection_cancelled.emit()
            self.close()


class AutoChatWorker(QThread):
    """Worker thread for the auto-conversation loop."""

    message_generated = Signal(str)
    message_sent = Signal(str)
    token_streaming = Signal(str)
    reply_detected = Signal(str)
    screenshot_taken = Signal(bytes)
    area_detected = Signal(object)
    status_update = Signal(str)
    error_occurred = Signal(str)
    round_completed = Signal(int)
    conversation_log = Signal(str)

    def __init__(self, ollama_client, window_manager, screenshot_reader, window_info,
                 prompt, rounds=10, read_replies=True,
                 max_wait_seconds=60.0, poll_interval=3.0,
                 manual_chat_rect=None, manual_input_rect=None, manual_send_btn_pos=None):
        super().__init__()
        self._client = ollama_client
        self._wm = window_manager
        self._reader = screenshot_reader
        self._window = window_info
        self._prompt = prompt
        self._rounds = rounds
        self._read_replies = read_replies
        self._max_wait = max_wait_seconds
        self._poll_interval = poll_interval
        self._manual_chat_rect = manual_chat_rect
        self._manual_input_rect = manual_input_rect
        self._manual_send_btn_pos = manual_send_btn_pos
        self._running = True
        self._history: list[dict] = []

    def stop(self):
        self._running = False

    def run(self):
        system_msg = {"role": "system", "content": AUTO_CHAT_SYSTEM_PROMPT.format(user_prompt=self._prompt)}
        self._history = [system_msg]

        # Area detection
        has_manual = self._manual_chat_rect or self._manual_input_rect
        if has_manual:
            self.status_update.emit("使用手动选择的区域")
            chat_r = self._manual_chat_rect
            input_r = self._manual_input_rect
            if chat_r and not input_r:
                input_r = (chat_r[0], chat_r[3], chat_r[2], chat_r[3] + 60)
            elif input_r and not chat_r:
                chat_r = (input_r[0], input_r[1] - 300, input_r[2], input_r[1])
            areas = AreaDetectionResult(chat_area_rect=chat_r, input_area_rect=input_r, method="manual", confidence=1.0)
        else:
            self.status_update.emit("检测对话区域...")
            detector = ChatAreaDetector(self._reader)
            areas = detector.detect_areas(self._window)
        self.area_detected.emit(areas)
        self.status_update.emit(f"区域检测完成 ({areas.method}, {areas.confidence:.0%})")

        ocr_parser = OCRChatParser(self._reader)
        memory = ConversationMemory()
        input_rect = areas.input_area_rect
        chat_rect = areas.chat_area_rect

        # Initial OCR scan
        self.status_update.emit("OCR扫描现有对话...")
        initial = ocr_parser.parse_chat_area(self._window, chat_rect)
        for msg in initial:
            if msg.sender == "self":
                memory.add_self_message(msg.content)
            else:
                memory.add_other_message(msg.content)
        if initial:
            self.status_update.emit(f"识别到 {len(initial)} 条现有消息")
            self.conversation_log.emit(memory.format_for_display_html())
        else:
            self.status_update.emit("未识别到现有消息")

        # ---- Main loop with reply gate ----
        # Key invariant: NEVER generate a new message if the last message
        # in memory is from "self". Must wait for a reply first.
        round_num = 0
        consecutive_no_reply = 0

        while round_num < self._rounds and self._running:
            # Refresh window
            refreshed = self._wm.refresh_window_info(self._window)
            if not refreshed:
                self.error_occurred.emit("窗口已关闭")
                return
            self._window = refreshed

            # ---- REPLY GATE ----
            # If last message is from self, we MUST wait for a reply before
            # generating the next message.
            if memory.messages and memory.messages[-1].sender == "self":
                self.status_update.emit(f"等待对方回复... (已完成 {round_num}/{self._rounds} 轮)")
                new_reply = self._poll_for_reply(ocr_parser, memory, chat_rect, round_num)
                if not self._running:
                    return
                if new_reply:
                    self.reply_detected.emit(new_reply)
                    memory.add_other_message(new_reply)
                    self.conversation_log.emit(memory.format_for_display_html())
                    consecutive_no_reply = 0
                    # Got reply - fall through to GENERATE below
                else:
                    consecutive_no_reply += 1
                    if consecutive_no_reply >= 2:
                        # Already probed once, still no reply - give up this round
                        self.status_update.emit("对方未回复，跳过本轮")
                        round_num += 1
                        consecutive_no_reply = 0
                        time.sleep(2)
                        continue
                    # First timeout - send ONE short probe
                    self.status_update.emit("等待超时，发送追问...")
                    probe = self._handle_no_reply(input_rect)
                    if probe:
                        memory.add_self_message(probe)
                        self.message_sent.emit(probe)
                        self.conversation_log.emit(memory.format_for_display_html())
                    # Loop back to reply gate - do NOT generate a full message
                    continue

            # ---- GENERATE & SEND ----
            round_num += 1
            consecutive_no_reply = 0

            # Rebuild history fresh from memory
            self._history = [system_msg]
            context = memory.format_for_llm(max_messages=20)

            if not memory.messages:
                self._history.append({"role": "user", "content": AUTO_CHAT_FIRST_MESSAGE_PROMPT.format(user_prompt=self._prompt)})
            else:
                last_other = memory.get_last_other_message()
                if last_other:
                    self._history.append({"role": "user", "content": (
                        f"{context}\n\n"
                        f"请针对对方说的「{last_other}」自然地回复。\n"
                        f"要求：直接回应对方的话，不要偏题，不要重复之前说过的内容。"
                    )})
                else:
                    self._history.append({"role": "user", "content": AUTO_CHAT_FIRST_MESSAGE_PROMPT.format(user_prompt=self._prompt)})

            self.status_update.emit(f"第 {round_num}/{self._rounds} 轮 - 生成中...")
            try:
                generated = self._generate_and_stream(input_rect)
                if not generated:
                    if not self._running:
                        return
                    self.error_occurred.emit("生成失败: 空内容")
                    time.sleep(2)
                    round_num -= 1  # Don't count failed rounds
                    continue
                generated = generated.strip().strip('"').strip("'")
                # Strip "我：" or "我:" prefix the LLM sometimes adds
                for prefix in ("我：", "我:", "我: ", "我："):
                    if generated.startswith(prefix):
                        generated = generated[len(prefix):].strip()
                if self._is_duplicate(generated, memory):
                    self.status_update.emit("检测到重复消息，跳过")
                    time.sleep(1)
                    round_num -= 1
                    continue
                memory.add_self_message(generated)
                self.message_generated.emit(generated)
                self.conversation_log.emit(memory.format_for_display_html())
            except Exception as e:
                self.error_occurred.emit(f"生成失败: {e}")
                if not self._running:
                    return
                time.sleep(2)
                round_num -= 1
                continue

            if not self._running:
                return

            # Send
            self._send_action()
            self.status_update.emit(f"第 {round_num}/{self._rounds} 轮 - 已发送")
            self.message_sent.emit(generated)
            self.round_completed.emit(round_num)

            if round_num >= self._rounds:
                break
            if not self._running:
                return

            # Brief pause before entering reply gate on next iteration
            time.sleep(1.5)

            # Take screenshot for UI
            refreshed = self._wm.refresh_window_info(self._window)
            if refreshed:
                self._window = refreshed
                ss = self._reader.capture_window(self._window)
                if ss:
                    self.screenshot_taken.emit(self._reader.image_to_bytes(ss))

        self.status_update.emit(f"已完成 {round_num}/{self._rounds} 轮对话")

    def _generate_and_stream(self, input_rect) -> str:
        tokens = self._client.chat_stream(self._history, temperature=0.65)
        accumulated = ""
        for token in tokens:
            if not self._running:
                return accumulated
            accumulated += token
            self.token_streaming.emit(accumulated)
        accumulated = accumulated.strip()
        if not accumulated:
            return ""
        refreshed = self._wm.refresh_window_info(self._window)
        if not refreshed:
            return ""
        self._window = refreshed
        ix = (input_rect[0] + input_rect[2]) // 2
        iy = (input_rect[1] + input_rect[3]) // 2
        click_and_type(x=ix, y=iy, text=accumulated, hwnd=self._window.hwnd, clear_first=True, move_duration=0.4)
        return accumulated

    def _send_action(self):
        focus_window_hard(self._window.hwnd)
        time.sleep(0.1)
        if self._manual_send_btn_pos:
            click_send_button(*self._manual_send_btn_pos, hwnd=self._window.hwnd, move_duration=0.3)
        else:
            send_enter()
        time.sleep(0.2)

    def _handle_no_reply(self, input_rect) -> str:
        prompt = AUTO_CHAT_NO_REPLY_PROMPT.format(wait_seconds=int(self._max_wait))
        try:
            response = self._client.chat(self._history + [{"role": "user", "content": prompt}], temperature=0.5)
            response = response.strip().strip('"').strip("'")
            if response.upper() == "WAIT":
                self.status_update.emit("继续等待...")
                return ""
            refreshed = self._wm.refresh_window_info(self._window)
            if not refreshed:
                return ""
            self._window = refreshed
            ix = (input_rect[0] + input_rect[2]) // 2
            iy = (input_rect[1] + input_rect[3]) // 2
            click_and_type(x=ix, y=iy, text=response, hwnd=self._window.hwnd, clear_first=True, move_duration=0.3)
            self._send_action()
            return response
        except Exception as e:
            self.error_occurred.emit(f"追问生成失败: {e}")
        return ""

    def _poll_for_reply(self, ocr_parser, memory, chat_rect, round_num) -> str:
        start = time.time()
        while time.time() - start < self._max_wait:
            if not self._running:
                return ""
            elapsed = int(time.time() - start)
            self.status_update.emit(f"第 {round_num}/{self._rounds} 轮 - 等待回复... ({elapsed}/{int(self._max_wait)}秒)")
            time.sleep(self._poll_interval)
            if not self._running:
                return ""
            refreshed = self._wm.refresh_window_info(self._window)
            if not refreshed:
                return ""
            self._window = refreshed
            current = ocr_parser.parse_chat_area(self._window, chat_rect)
            new_others = ocr_parser.find_new_other_messages(current, memory)
            if new_others:
                for msg in new_others[:-1]:
                    memory.add_other_message(msg.content)
                return new_others[-1].content
        return ""

    @staticmethod
    def _is_duplicate(new_msg: str, memory: ConversationMemory) -> bool:
        clean = new_msg.strip().replace(" ", "").replace("\n", "")
        if not clean:
            return True
        for msg in memory.messages[-6:]:
            if msg.sender == "self":
                old = msg.content.strip().replace(" ", "").replace("\n", "")
                if clean == old:
                    return True
                if len(clean) > 10 and clean in old:
                    return True
                if len(old) > 10 and old in clean:
                    return True
        return False


# ============================================================================
# Main Window
# ============================================================================

class LLMChatWindow(QMainWindow):
    """Standalone LLM chat automation window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("LLM Chat - 聊天自动化工具")
        self.resize(900, 900)

        self._ollama_client: OllamaClient | None = None
        self._window_manager = WindowManager()
        self._screenshot_reader = ScreenshotReader()
        self._selected_window: WindowInfo | None = None
        self._window_list: list[WindowInfo] = []
        self._auto_worker: AutoChatWorker | None = None
        self._detected_areas: AreaDetectionResult | None = None
        self._manual_chat_rect = None
        self._manual_input_rect = None
        self._manual_send_btn_pos = None
        self._overlay: AreaSelectionOverlay | None = None
        self._selecting_purpose = ""

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(6)

        # ---- 1. Ollama Connection ----
        conn_group = QGroupBox("1. Ollama 连接")
        conn_layout = QVBoxLayout(conn_group)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("URL:"))
        self.url_edit = QLineEdit("http://localhost:11434")
        row1.addWidget(self.url_edit)
        row1.addWidget(QLabel("模型:"))
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(200)
        row1.addWidget(self.model_combo)
        self.connect_btn = QPushButton("连接")
        self.connect_btn.clicked.connect(self._on_connect)
        row1.addWidget(self.connect_btn)
        conn_layout.addLayout(row1)
        self.conn_status = QLabel("未连接")
        self.conn_status.setStyleSheet("color: #888;")
        conn_layout.addWidget(self.conn_status)
        root.addWidget(conn_group)

        # ---- 2. Window Selection ----
        win_group = QGroupBox("2. 选择目标窗口")
        win_layout = QVBoxLayout(win_group)
        row2 = QHBoxLayout()
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self._refresh_windows)
        row2.addWidget(self.refresh_btn)
        row2.addWidget(QLabel("筛选:"))
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("关键词...")
        self.filter_edit.textChanged.connect(self._filter_windows)
        row2.addWidget(self.filter_edit)
        win_layout.addLayout(row2)
        self.window_list_widget = QListWidget()
        self.window_list_widget.setMaximumHeight(100)
        self.window_list_widget.itemDoubleClicked.connect(self._on_window_selected)
        win_layout.addWidget(self.window_list_widget)
        self.selected_label = QLabel("双击列表选择窗口")
        self.selected_label.setStyleSheet("color: #888;")
        win_layout.addWidget(self.selected_label)
        root.addWidget(win_group)

        # ---- 3. Area Setup ----
        area_group = QGroupBox("3. 区域设置")
        area_layout = QVBoxLayout(area_group)
        area_btns = QHBoxLayout()
        self.capture_btn = QPushButton("截图并检测")
        self.capture_btn.clicked.connect(self._on_capture)
        self.capture_btn.setEnabled(False)
        area_btns.addWidget(self.capture_btn)
        self.sel_chat_btn = QPushButton("选择对话区域")
        self.sel_chat_btn.setStyleSheet("QPushButton{background:#27ae60;color:white}QPushButton:disabled{background:#ccc}")
        self.sel_chat_btn.clicked.connect(lambda: self._on_area_select("chat"))
        self.sel_chat_btn.setEnabled(False)
        area_btns.addWidget(self.sel_chat_btn)
        self.sel_input_btn = QPushButton("选择输入区域")
        self.sel_input_btn.setStyleSheet("QPushButton{background:#2980b9;color:white}QPushButton:disabled{background:#ccc}")
        self.sel_input_btn.clicked.connect(lambda: self._on_area_select("input"))
        self.sel_input_btn.setEnabled(False)
        area_btns.addWidget(self.sel_input_btn)
        self.sel_send_btn = QPushButton("选择发送按钮")
        self.sel_send_btn.setStyleSheet("QPushButton{background:#e67e22;color:white}QPushButton:disabled{background:#ccc}")
        self.sel_send_btn.clicked.connect(lambda: self._on_area_select("send"))
        self.sel_send_btn.setEnabled(False)
        area_btns.addWidget(self.sel_send_btn)
        self.clear_area_btn = QPushButton("清除选区")
        self.clear_area_btn.clicked.connect(self._on_clear_areas)
        self.clear_area_btn.setVisible(False)
        area_btns.addWidget(self.clear_area_btn)
        area_layout.addLayout(area_btns)
        self.screenshot_label = QLabel("截图预览")
        self.screenshot_label.setAlignment(Qt.AlignCenter)
        self.screenshot_label.setMinimumHeight(180)
        self.screenshot_label.setStyleSheet("background:#f0f0f0; border:1px solid #ddd;")
        area_layout.addWidget(self.screenshot_label)
        root.addWidget(area_group)

        # ---- 4. Auto Chat ----
        chat_group = QGroupBox("4. 自动对话")
        chat_layout = QVBoxLayout(chat_group)
        chat_layout.addWidget(QLabel("对话提示词:"))
        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setPlainText("你是一个热情友好的朋友，根据对方的消息自然地回复，语气轻松随和，回复简短自然（1-3句话），像真人聊天一样。")
        self.prompt_edit.setMaximumHeight(50)
        chat_layout.addWidget(self.prompt_edit)

        settings_row = QHBoxLayout()
        settings_row.addWidget(QLabel("轮数:"))
        self.rounds_spin = QSpinBox()
        self.rounds_spin.setRange(1, 100)
        self.rounds_spin.setValue(5)
        settings_row.addWidget(self.rounds_spin)
        settings_row.addWidget(QLabel("最长等待(秒):"))
        self.max_wait_spin = QSpinBox()
        self.max_wait_spin.setRange(5, 300)
        self.max_wait_spin.setValue(60)
        settings_row.addWidget(self.max_wait_spin)
        self.read_replies_cb = QCheckBox("识别回复")
        self.read_replies_cb.setChecked(True)
        settings_row.addWidget(self.read_replies_cb)
        settings_row.addStretch()
        chat_layout.addLayout(settings_row)
        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("开始自动对话")
        self.start_btn.setStyleSheet("QPushButton{background:#07c160;color:white;font-weight:bold;padding:8px 24px;font-size:14px}")
        self.start_btn.clicked.connect(self._on_start)
        self.start_btn.setEnabled(False)
        btn_row.addWidget(self.start_btn)
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setStyleSheet("QPushButton{background:#e74c3c;color:white;font-weight:bold;padding:8px 24px;font-size:14px}")
        self.stop_btn.clicked.connect(self._on_stop)
        self.stop_btn.setEnabled(False)
        btn_row.addWidget(self.stop_btn)
        btn_row.addStretch()
        chat_layout.addLayout(btn_row)

        # Conversation display + log splitter
        conv_splitter = QSplitter(Qt.Vertical)
        self.conv_display = QTextEdit()
        self.conv_display.setReadOnly(True)
        self.conv_display.setPlaceholderText("对话记录...")
        self.conv_display.setStyleSheet("QTextEdit{background:#EDEDED}")
        conv_splitter.addWidget(self.conv_display)
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setMaximumHeight(100)
        self.log_display.setStyleSheet("background:#1e1e1e; color:#ddd; font-family:monospace;")
        conv_splitter.addWidget(self.log_display)
        conv_splitter.setSizes([250, 100])
        chat_layout.addWidget(conv_splitter)
        root.addWidget(chat_group)

        # ---- 5. Manual Send ----
        manual_group = QGroupBox("5. 手动发送")
        manual_layout = QHBoxLayout(manual_group)
        self.manual_edit = QLineEdit()
        self.manual_edit.setPlaceholderText("输入消息...")
        self.manual_edit.returnPressed.connect(self._on_manual_send)
        manual_layout.addWidget(self.manual_edit)
        self.send_btn = QPushButton("发送")
        self.send_btn.setStyleSheet("background:#07c160; color:white; font-weight:bold; padding:6px 16px;")
        self.send_btn.clicked.connect(self._on_manual_send)
        self.send_btn.setEnabled(False)
        manual_layout.addWidget(self.send_btn)
        root.addWidget(manual_group)

        # Status bar
        self.status_label = QLabel("就绪")
        root.addWidget(self.status_label)

    # ---- Ollama connection ----

    def _on_connect(self):
        url = self.url_edit.text().strip()
        if not url:
            return
        self.conn_status.setText("连接中...")
        self.conn_status.setStyleSheet("color: #e67e22;")
        QApplication.processEvents()

        client = OllamaClient(base_url=url)
        if not client.is_available():
            self.conn_status.setText("连接失败 - 请检查 Ollama 是否运行")
            self.conn_status.setStyleSheet("color: #e74c3c;")
            return

        models = client.model_names()
        self.model_combo.clear()
        if models:
            # Filter out embedding models for the combo
            embed_pats = ("embed", "nomic", "bge", "e5-", "mxbai")
            chat_models = [m for m in models if not any(p in m.lower() for p in embed_pats)]
            for m in (chat_models or models):
                self.model_combo.addItem(m)
            self.conn_status.setText(f"已连接 - {len(chat_models or models)} 个模型可用")
            self.conn_status.setStyleSheet("color: #07c160; font-weight: bold;")
            self._ollama_client = client
            self._update_enabled()
        else:
            self.conn_status.setText("已连接但无模型 - 请先 ollama pull 下载模型")
            self.conn_status.setStyleSheet("color: #e67e22;")

    def _update_enabled(self):
        has_client = self._ollama_client is not None
        has_window = self._selected_window is not None
        self.capture_btn.setEnabled(has_window)
        self.sel_chat_btn.setEnabled(has_window)
        self.sel_input_btn.setEnabled(has_window)
        self.sel_send_btn.setEnabled(has_window)
        self.send_btn.setEnabled(has_window)
        self.start_btn.setEnabled(has_client and has_window)

    # ---- Window selection ----

    def _refresh_windows(self):
        self._window_list = self._window_manager.get_all_visible_windows()
        self._show_windows()
        self.status_label.setText(f"找到 {len(self._window_list)} 个窗口")

    def _show_windows(self, filter_text=""):
        self.window_list_widget.clear()
        f = filter_text.lower()
        for w in self._window_list:
            if f and f not in w.title.lower():
                continue
            tag = f"[{w.app_type}] " if w.app_type != "other" else ""
            item = QListWidgetItem(f"{tag}{w.title}")
            item.setData(Qt.UserRole, w.hwnd)
            self.window_list_widget.addItem(item)

    def _filter_windows(self, text):
        self._show_windows(text)

    def _on_window_selected(self, item):
        hwnd = item.data(Qt.UserRole)
        for w in self._window_list:
            if w.hwnd == hwnd:
                self._selected_window = w
                break
        if self._selected_window:
            self.selected_label.setText(f"已选择: {self._selected_window.title}")
            self.selected_label.setStyleSheet("color: #07c160; font-weight: bold;")
            self._detected_areas = None
            self._manual_chat_rect = self._manual_input_rect = self._manual_send_btn_pos = None
            self.clear_area_btn.setVisible(False)
            self.sel_chat_btn.setText("选择对话区域")
            self.sel_input_btn.setText("选择输入区域")
            self.sel_send_btn.setText("选择发送按钮")
            self._update_enabled()

    # ---- Area selection ----

    def _on_capture(self):
        if not self._selected_window:
            return
        self._selected_window = self._window_manager.refresh_window_info(self._selected_window)
        if not self._selected_window:
            return
        detector = ChatAreaDetector(self._screenshot_reader)
        self._detected_areas = detector.detect_areas(self._selected_window)
        ss, text = self._screenshot_reader.capture_and_extract(self._selected_window)
        if ss:
            self._show_screenshot_with_areas(self._screenshot_reader.image_to_bytes(ss), self._detected_areas)
            self.status_label.setText(f"区域检测: {self._detected_areas.method} ({self._detected_areas.confidence:.0%})")

    def _on_area_select(self, purpose):
        if not self._selected_window:
            return
        if self._overlay:
            self._overlay.close()
        self._selecting_purpose = purpose
        existing = {}
        if self._manual_chat_rect:
            existing["chat"] = self._manual_chat_rect
        if self._manual_input_rect:
            existing["input"] = self._manual_input_rect
        if self._manual_send_btn_pos:
            sx, sy = self._manual_send_btn_pos
            existing["send"] = (sx - 20, sy - 10, sx + 20, sy + 10)
        self._overlay = AreaSelectionOverlay(
            target_window_rect=self._selected_window.rect, purpose=purpose, existing_rects=existing)
        self._overlay.area_selected.connect(self._on_area_selected)
        self._overlay.selection_cancelled.connect(lambda: setattr(self, '_overlay', None))
        self._overlay.show()

    @Slot(tuple)
    def _on_area_selected(self, rect):
        self._overlay = None
        p = self._selecting_purpose
        left, top, right, bottom = rect
        if p == "chat":
            self._manual_chat_rect = rect
            self.sel_chat_btn.setText(f"对话区域 ({right - left}x{bottom - top})")
        elif p == "input":
            self._manual_input_rect = rect
            self.sel_input_btn.setText(f"输入区域 ({right - left}x{bottom - top})")
        elif p == "send":
            cx, cy = (left + right) // 2, (top + bottom) // 2
            self._manual_send_btn_pos = (cx, cy)
            self.sel_send_btn.setText(f"发送按钮 ({cx},{cy})")
        has_any = bool(self._manual_chat_rect or self._manual_input_rect or self._manual_send_btn_pos)
        self.clear_area_btn.setVisible(has_any)
        self._refresh_area_display()

    def _on_clear_areas(self):
        self._manual_chat_rect = self._manual_input_rect = self._manual_send_btn_pos = None
        self.clear_area_btn.setVisible(False)
        self.sel_chat_btn.setText("选择对话区域")
        self.sel_input_btn.setText("选择输入区域")
        self.sel_send_btn.setText("选择发送按钮")
        self.status_label.setText("已清除选区")
        if self._selected_window:
            self._on_capture()

    def _refresh_area_display(self):
        if not self._selected_window:
            return
        ss = self._screenshot_reader.capture_window(self._selected_window)
        if not ss:
            return
        png = self._screenshot_reader.image_to_bytes(ss)
        # Build composite areas for display
        chat_r = self._manual_chat_rect
        input_r = self._manual_input_rect
        if chat_r and not input_r:
            input_r = (chat_r[0], chat_r[3], chat_r[2], chat_r[3] + 50)
        elif input_r and not chat_r:
            chat_r = (input_r[0], input_r[1] - 200, input_r[2], input_r[1])
        if chat_r and input_r:
            areas = AreaDetectionResult(chat_area_rect=chat_r, input_area_rect=input_r, method="manual", confidence=1.0)
            self._show_screenshot_with_areas(png, areas)
        else:
            self._show_screenshot_raw(png)

    def _show_screenshot_raw(self, png_bytes):
        pm = QPixmap()
        pm.loadFromData(png_bytes)
        self.screenshot_label.setPixmap(pm.scaled(self.screenshot_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _show_screenshot_with_areas(self, png_bytes, areas):
        pm = QPixmap()
        pm.loadFromData(png_bytes)
        if areas and self._selected_window:
            wl, wt = self._selected_window.rect[0], self._selected_window.rect[1]
            painter = QPainter(pm)
            cl, ct, cr, cb = areas.chat_area_rect
            painter.fillRect(cl - wl, ct - wt, cr - cl, cb - ct, QColor(0, 200, 0, 40))
            painter.setPen(QColor(0, 200, 0, 160))
            painter.drawRect(cl - wl, ct - wt, cr - cl, cb - ct)
            il, it, ir, ib = areas.input_area_rect
            painter.fillRect(il - wl, it - wt, ir - il, ib - it, QColor(0, 100, 255, 40))
            painter.setPen(QColor(0, 100, 255, 160))
            painter.drawRect(il - wl, it - wt, ir - il, ib - it)
            if self._manual_send_btn_pos:
                sx, sy = self._manual_send_btn_pos
                rx, ry = sx - wl, sy - wt
                painter.setPen(QPen(QColor(255, 165, 0), 2))
                painter.drawLine(rx - 15, ry, rx + 15, ry)
                painter.drawLine(rx, ry - 15, rx, ry + 15)
                painter.drawEllipse(QPoint(rx, ry), 10, 10)
            painter.end()
        self.screenshot_label.setPixmap(pm.scaled(self.screenshot_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    # ---- Auto chat ----

    def _on_start(self):
        if not self._selected_window or not self._ollama_client:
            return
        prompt = self.prompt_edit.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "提示", "请输入对话提示词")
            return
        self._selected_window = self._window_manager.refresh_window_info(self._selected_window)
        if not self._selected_window:
            QMessageBox.warning(self, "错误", "窗口已关闭")
            return

        # Set model from combo
        model = self.model_combo.currentText()
        if model:
            self._ollama_client.model = model

        self.log_display.clear()
        self._log("开始自动对话...")
        self._log(f"目标: {self._selected_window.title}")
        self._log(f"模型: {model}")

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.prompt_edit.setEnabled(False)

        self._auto_worker = AutoChatWorker(
            ollama_client=self._ollama_client,
            window_manager=self._window_manager,
            screenshot_reader=self._screenshot_reader,
            window_info=self._selected_window,
            prompt=prompt,
            rounds=self.rounds_spin.value(),
            read_replies=self.read_replies_cb.isChecked(),
            max_wait_seconds=self.max_wait_spin.value(),
            poll_interval=3.0,
            manual_chat_rect=self._manual_chat_rect,
            manual_input_rect=self._manual_input_rect,
            manual_send_btn_pos=self._manual_send_btn_pos,
        )
        w = self._auto_worker
        w.message_generated.connect(lambda m: self._log(f"[生成] {m}"))
        w.message_sent.connect(lambda m: self._log(f"[已发送] {m}"))
        w.token_streaming.connect(lambda t: self.status_label.setText(f"生成: {t[-40:]}..."))
        w.reply_detected.connect(lambda t: self._log(f"[回复] {t[:80]}..."))
        w.screenshot_taken.connect(lambda b: self._show_screenshot_raw(b))
        w.area_detected.connect(lambda a: self._log(f"[区域] {a.method} ({a.confidence:.0%})"))
        w.status_update.connect(lambda m: self.status_label.setText(m))
        w.error_occurred.connect(lambda m: self._log(f"[错误] {m}"))
        w.round_completed.connect(lambda n: self._log(f"--- 第 {n} 轮完成 ---"))
        w.conversation_log.connect(self._on_conv_log)
        w.finished.connect(self._on_finished)
        w.start()

    def _on_stop(self):
        if self._auto_worker:
            self._auto_worker.stop()
            self._log("正在停止...")

    def _on_finished(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.prompt_edit.setEnabled(True)
        self._log("对话结束")

    @Slot(str)
    def _on_conv_log(self, html):
        self.conv_display.setHtml(html)
        sb = self.conv_display.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _log(self, text):
        self.log_display.append(text)
        sb = self.log_display.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ---- Manual send ----

    def _on_manual_send(self):
        if not self._selected_window:
            return
        msg = self.manual_edit.text().strip()
        if not msg:
            return
        self._selected_window = self._window_manager.refresh_window_info(self._selected_window)
        if not self._selected_window:
            return
        input_rect = None
        if self._manual_input_rect:
            input_rect = self._manual_input_rect
        elif self._detected_areas:
            input_rect = self._detected_areas.input_area_rect

        if input_rect:
            ix = (input_rect[0] + input_rect[2]) // 2
            iy = (input_rect[1] + input_rect[3]) // 2
        else:
            wl, wt, wr, wb = self._selected_window.rect
            ix = wl + int((wr - wl) * 0.65)
            iy = wb - int((wb - wt) * 0.08)

        focus_window_hard(self._selected_window.hwnd)
        time.sleep(0.15)
        ok = click_and_type(x=ix, y=iy, text=msg, hwnd=self._selected_window.hwnd, clear_first=True, move_duration=0.3)
        if ok:
            time.sleep(0.1)
            send_enter()
            self._log(f"[手动发送] {msg}")
            self.manual_edit.clear()
            self.status_label.setText("发送成功")
        else:
            self.status_label.setText("发送失败")


# ============================================================================
# Entry point
# ============================================================================

def main():
    # DPI awareness for Windows
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = LLMChatWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
