"""Public API for llm-chat."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from .core.window_manager import WindowManager
from .core.screenshot import ScreenshotReader
from .agent.workflow import AgentWorkflow
from .agent.conversation import ConversationMemory

if TYPE_CHECKING:
    from .models.window import WindowInfo
    from .llm.base import BaseLLMClient


class VisionAgent:
    """High-level API for vision-based GUI automation.
    
    This is the main entry point for programmatic usage of llm-chat.
    
    Example:
        from llm_chat import VisionAgent, LLMClientFactory
        from llm_chat.core import WindowManager
        
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
        max_wait_seconds: float = 60.0,
        poll_interval: float = 3.0,
        chat_area: tuple[int, int, int, int] | None = None,
        input_area: tuple[int, int, int, int] | None = None,
        send_button_pos: tuple[int, int] | None = None,
    ):
        """Initialize the VisionAgent.
        
        Args:
            llm_client: LLM client for generating responses
            target_window: Target window to automate
            prompt: System prompt for conversation style
            max_rounds: Maximum conversation rounds
            max_wait_seconds: Maximum seconds to wait for reply
            poll_interval: Seconds between reply checks
            chat_area: Manual chat area rect (left, top, right, bottom)
            input_area: Manual input area rect (left, top, right, bottom)
            send_button_pos: Manual send button position (x, y)
        """
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
        """Get conversation memory.
        
        Returns:
            ConversationMemory with message history
        """
        if self._workflow:
            return self._workflow.memory
        return ConversationMemory()

    @property
    def is_running(self) -> bool:
        """Check if agent is currently running.
        
        Returns:
            True if running
        """
        return self._workflow is not None and self._workflow.is_running

    def set_area_manual(
        self,
        chat_area: tuple[int, int, int, int] | None = None,
        input_area: tuple[int, int, int, int] | None = None,
        send_button_pos: tuple[int, int] | None = None,
    ) -> None:
        """Manually set area positions.
        
        Args:
            chat_area: Chat area rect (left, top, right, bottom)
            input_area: Input area rect (left, top, right, bottom)
            send_button_pos: Send button position (x, y)
        """
        if chat_area:
            self._chat_area = chat_area
        if input_area:
            self._input_area = input_area
        if send_button_pos:
            self._send_button_pos = send_button_pos

    def run(self) -> None:
        """Run the automation workflow (blocking).
        
        This method blocks until the workflow completes or is stopped.
        """
        # Refresh window info
        refreshed = self._window_manager.refresh_window_info(self._window)
        if refreshed:
            self._window = refreshed
        
        # Create workflow
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
        
        # Wire up callbacks
        self._workflow.on_status = self.on_status
        self._workflow.on_message_generated = self.on_message_generated
        self._workflow.on_message_sent = self.on_message_sent
        self._workflow.on_reply_detected = self.on_reply_detected
        self._workflow.on_error = self.on_error
        self._workflow.on_round_complete = self.on_round_complete
        
        # Run
        self._workflow.run()

    def stop(self) -> None:
        """Stop the running workflow."""
        if self._workflow:
            self._workflow.stop()

    @staticmethod
    def list_windows() -> list["WindowInfo"]:
        """List all visible windows.
        
        Returns:
            List of WindowInfo objects
        """
        wm = WindowManager()
        return wm.get_all_visible_windows()

    @staticmethod
    def find_window(title_substring: str) -> "WindowInfo | None":
        """Find window by title substring.
        
        Args:
            title_substring: Substring to search for
            
        Returns:
            WindowInfo or None
        """
        wm = WindowManager()
        return wm.find_window_by_title(title_substring)

    @staticmethod
    def list_chat_windows() -> list["WindowInfo"]:
        """List detected chat application windows.
        
        Returns:
            List of WindowInfo for chat apps (WeChat, QQ, etc.)
        """
        wm = WindowManager()
        return wm.get_chat_windows()
