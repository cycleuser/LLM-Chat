"""Background worker threads for GUI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, Signal

from ..agent.workflow import AgentWorkflow

if TYPE_CHECKING:
    from ..models.window import WindowInfo
    from ..core.window_manager import WindowManager
    from ..core.screenshot import ScreenshotReader
    from ..llm.base import BaseLLMClient


class AutoChatWorker(QThread):
    """Worker thread for the auto-conversation loop.

    Runs AgentWorkflow in a background thread to avoid blocking the UI.

    Signals:
        message_generated: Emitted when a message is generated (str)
        message_sent: Emitted when a message is sent (str)
        token_streaming: Emitted during token streaming (str: accumulated text)
        reply_detected: Emitted when a reply is detected (str)
        screenshot_taken: Emitted when screenshot is taken (bytes)
        area_detected: Emitted when areas are detected (AreaDetectionResult)
        status_update: Emitted for status updates (str)
        error_occurred: Emitted on errors (str)
        round_completed: Emitted when a round completes (int: round number)
        conversation_log: Emitted with conversation HTML (str)
    """

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
    kb_status = Signal(str)

    def __init__(
        self,
        llm_client: "BaseLLMClient",
        window_manager: "WindowManager",
        screenshot_reader: "ScreenshotReader",
        window_info: "WindowInfo",
        prompt: str,
        rounds: int = 10,
        max_wait_seconds: float = 10.0,
        poll_interval: float = 3.0,
        manual_chat_rect: tuple[int, int, int, int] | None = None,
        manual_input_rect: tuple[int, int, int, int] | None = None,
        manual_send_btn_pos: tuple[int, int] | None = None,
        kb_config: dict | None = None,
        selected_kbs: list[str] | None = None,
        strict_mode: bool = False,
    ):
        super().__init__()
        self._client = llm_client
        self._wm = window_manager
        self._reader = screenshot_reader
        self._window = window_info
        self._prompt = prompt
        self._rounds = rounds
        self._max_wait = max_wait_seconds
        self._poll_interval = poll_interval
        self._manual_chat_rect = manual_chat_rect
        self._manual_input_rect = manual_input_rect
        self._manual_send_btn_pos = manual_send_btn_pos
        self._kb_config = kb_config
        self._selected_kbs = selected_kbs
        self._strict_mode = strict_mode
        self._workflow: AgentWorkflow | None = None

    def stop(self) -> None:
        """Stop the worker."""
        if self._workflow:
            self._workflow.stop()

    def run(self) -> None:
        """Run the automation workflow."""
        self._workflow = AgentWorkflow(
            llm_client=self._client,
            window_manager=self._wm,
            screenshot_reader=self._reader,
            window_info=self._window,
            prompt=self._prompt,
            rounds=self._rounds,
            max_wait_seconds=self._max_wait,
            poll_interval=self._poll_interval,
            manual_chat_rect=self._manual_chat_rect,
            manual_input_rect=self._manual_input_rect,
            manual_send_btn_pos=self._manual_send_btn_pos,
            kb_config=self._kb_config,
            selected_kbs=self._selected_kbs,
            strict_mode=self._strict_mode,
        )

        # Connect callbacks to signals
        self._workflow.on_status = lambda m: self.status_update.emit(m)
        self._workflow.on_message_generated = lambda m: self.message_generated.emit(m)
        self._workflow.on_message_sent = lambda m: self.message_sent.emit(m)
        self._workflow.on_token_stream = lambda t: self.token_streaming.emit(t)
        self._workflow.on_reply_detected = lambda r: self.reply_detected.emit(r)
        self._workflow.on_error = lambda e: self.error_occurred.emit(e)
        self._workflow.on_round_complete = lambda n: self.round_completed.emit(n)
        self._workflow.on_conversation_update = lambda h: self.conversation_log.emit(h)
        self._workflow.on_kb_status = lambda m: self.kb_status.emit(m)

        # Run workflow
        try:
            self._workflow.run()
        except Exception as e:
            self.error_occurred.emit(str(e))
