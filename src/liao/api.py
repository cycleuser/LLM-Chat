"""
Liao - Unified Python API.

Provides the VisionAgent class and ToolResult-based wrappers
for programmatic usage and agent integration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, TYPE_CHECKING, Callable

from .core.window_manager import WindowManager
from .core.screenshot import ScreenshotReader
from .agent.workflow import AgentWorkflow
from .agent.conversation import ConversationMemory

if TYPE_CHECKING:
    from .models.window import WindowInfo
    from .llm.base import BaseLLMClient


@dataclass
class ToolResult:
    """Standardised return type for all Liao API functions."""

    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
        }


class VisionAgent:
    """High-level API for vision-based GUI automation.

    This is the main entry point for programmatic usage of Liao.

    Example:
        from liao import VisionAgent, LLMClientFactory
        from liao.core import WindowManager

        # Setup
        llm = LLMClientFactory.create_client(provider="ollama", model="llama3")
        wm = WindowManager()
        window = wm.find_window_by_title("WeChat")

        # Create agent
        agent = VisionAgent(
            llm_client=llm,
            target_window=window,
            prompt="Be friendly and helpful",
            max_rounds=10,
        )

        # Run automation
        agent.run()

        # Access conversation history
        for msg in agent.conversation.messages:
            print(f"{msg.sender}: {msg.content}")
    """

    def __init__(
        self,
        llm_client: "BaseLLMClient",
        target_window: "WindowInfo",
        prompt: str = "",
        max_rounds: int = 10,
        max_wait_seconds: float = 10.0,
        poll_interval: float = 3.0,
        chat_area: tuple[int, int, int, int] | None = None,
        input_area: tuple[int, int, int, int] | None = None,
        send_button_pos: tuple[int, int] | None = None,
    ):
        self._llm_client = llm_client
        self._window = target_window
        self._prompt = prompt
        self._max_rounds = max_rounds
        self._max_wait = max_wait_seconds
        self._poll_interval = poll_interval
        self._chat_area = chat_area
        self._input_area = input_area
        self._send_button_pos = send_button_pos

        self._window_manager = WindowManager()
        self._screenshot_reader = ScreenshotReader()
        self._workflow: AgentWorkflow | None = None

        # Callbacks
        self.on_status: Callable[[str], None] | None = None
        self.on_message_generated: Callable[[str], None] | None = None
        self.on_message_sent: Callable[[str], None] | None = None
        self.on_reply_detected: Callable[[str], None] | None = None
        self.on_error: Callable[[str], None] | None = None
        self.on_round_complete: Callable[[int], None] | None = None

    @property
    def conversation(self) -> ConversationMemory:
        if self._workflow:
            return self._workflow.memory
        return ConversationMemory()

    @property
    def is_running(self) -> bool:
        return self._workflow is not None and self._workflow.is_running

    def set_area_manual(
        self,
        chat_area: tuple[int, int, int, int] | None = None,
        input_area: tuple[int, int, int, int] | None = None,
        send_button_pos: tuple[int, int] | None = None,
    ) -> None:
        if chat_area:
            self._chat_area = chat_area
        if input_area:
            self._input_area = input_area
        if send_button_pos:
            self._send_button_pos = send_button_pos

    def run(self) -> None:
        """Run the automation workflow (blocking)."""
        refreshed = self._window_manager.refresh_window_info(self._window)
        if refreshed:
            self._window = refreshed

        self._workflow = AgentWorkflow(
            llm_client=self._llm_client,
            window_manager=self._window_manager,
            screenshot_reader=self._screenshot_reader,
            window_info=self._window,
            prompt=self._prompt,
            rounds=self._max_rounds,
            max_wait_seconds=self._max_wait,
            poll_interval=self._poll_interval,
            manual_chat_rect=self._chat_area,
            manual_input_rect=self._input_area,
            manual_send_btn_pos=self._send_button_pos,
        )

        self._workflow.on_status = self.on_status
        self._workflow.on_message_generated = self.on_message_generated
        self._workflow.on_message_sent = self.on_message_sent
        self._workflow.on_reply_detected = self.on_reply_detected
        self._workflow.on_error = self.on_error
        self._workflow.on_round_complete = self.on_round_complete

        self._workflow.run()

    def stop(self) -> None:
        """Stop the running workflow."""
        if self._workflow:
            self._workflow.stop()

    @staticmethod
    def list_windows() -> list["WindowInfo"]:
        wm = WindowManager()
        return wm.get_all_visible_windows()

    @staticmethod
    def find_window(title_substring: str) -> "WindowInfo | None":
        wm = WindowManager()
        return wm.find_window_by_title(title_substring)

    @staticmethod
    def list_chat_windows() -> list["WindowInfo"]:
        wm = WindowManager()
        return wm.get_chat_windows()


# ── ToolResult-based convenience functions ───────────────────────────────


def list_windows(*, chat_only: bool = False) -> ToolResult:
    """List visible windows on the desktop.

    Parameters
    ----------
    chat_only : bool
        If True, only return windows from known chat applications.

    Returns
    -------
    ToolResult
        With data containing list of window dicts.
    """
    try:
        from . import __version__
        from .core.window_manager import WindowManager

        wm = WindowManager()
        windows = wm.get_all_visible_windows()

        if chat_only:
            windows = [w for w in windows if w.app_type != "other"]

        data = [
            {
                "hwnd": w.hwnd,
                "title": w.title,
                "app_type": w.app_type,
            }
            for w in windows
        ]

        return ToolResult(
            success=True,
            data=data,
            metadata={"count": len(data), "version": __version__},
        )
    except Exception as e:
        return ToolResult(success=False, error=str(e))


def run_automation(
    *,
    hwnd: int | None = None,
    title: str | None = None,
    prompt: str = "You are a friendly assistant. Respond naturally and briefly.",
    rounds: int = 5,
    provider: str = "ollama",
    model: str = "",
    base_url: str = "http://localhost:11434",
    max_wait: float = 10.0,
    poll_interval: float = 3.0,
) -> ToolResult:
    """Run headless GUI automation on a target window.

    Parameters
    ----------
    hwnd : int or None
        Target window handle.
    title : str or None
        Target window title (partial match).
    prompt : str
        Conversation system prompt.
    rounds : int
        Number of conversation rounds.
    provider : str
        LLM provider: ollama, openai, or anthropic.
    model : str
        LLM model name.
    base_url : str
        LLM API URL.
    max_wait : float
        Max seconds to wait for reply.
    poll_interval : float
        Seconds between reply checks.

    Returns
    -------
    ToolResult
        With data containing automation results.
    """
    if not hwnd and not title:
        return ToolResult(success=False, error="Specify hwnd or title")

    try:
        from . import __version__
        from .core.window_manager import WindowManager
        from .core.screenshot import ScreenshotReader
        from .llm.factory import LLMClientFactory
        from .agent.workflow import AgentWorkflow

        wm = WindowManager()

        if hwnd:
            window = wm.get_window_by_hwnd(hwnd)
        else:
            window = wm.find_window_by_title(title)

        if not window:
            return ToolResult(success=False, error="Window not found")

        client = LLMClientFactory.create_client(
            provider=provider,
            base_url=base_url,
            model=model,
        )
        if not client.is_available():
            return ToolResult(
                success=False,
                error=f"LLM backend not available ({provider})",
            )

        reader = ScreenshotReader()
        messages_sent = []
        replies_received = []

        workflow = AgentWorkflow(
            llm_client=client,
            window_manager=wm,
            screenshot_reader=reader,
            window_info=window,
            prompt=prompt,
            rounds=rounds,
            max_wait_seconds=max_wait,
            poll_interval=poll_interval,
        )

        workflow.on_message_sent = lambda m: messages_sent.append(m)
        workflow.on_reply_detected = lambda r: replies_received.append(r)

        workflow.run()

        return ToolResult(
            success=True,
            data={
                "window_title": window.title,
                "rounds": rounds,
                "messages_sent": messages_sent,
                "replies_received": replies_received,
            },
            metadata={
                "provider": provider,
                "model": model,
                "version": __version__,
            },
        )
    except Exception as e:
        return ToolResult(success=False, error=str(e))
