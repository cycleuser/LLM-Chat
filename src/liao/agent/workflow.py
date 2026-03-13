"""Agent workflow orchestration with knowledge base support."""

from __future__ import annotations

import logging
import sys
import time
from typing import TYPE_CHECKING, Callable

from .conversation import ConversationMemory
from .chat_parser import OCRChatParser
from .prompts import PromptManager
from ..core.area_detector import ChatAreaDetector
from ..core.input_simulator import InputSimulator
from ..models.detection import AreaDetectionResult

if TYPE_CHECKING:
    from ..models.window import WindowInfo
    from ..core.window_manager import WindowManager
    from ..core.screenshot import ScreenshotReader
    from ..llm.base import BaseLLMClient

logger = logging.getLogger(__name__)

IS_MACOS = sys.platform == "darwin"


class AgentWorkflow:
    """Orchestrates the vision agent automation loop.

    Manages the flow of:
    1. Area detection
    2. Initial OCR scan
    3. Reply gate (wait for other's message)
    4. Message generation via LLM
    5. Message sending via input simulation
    6. Reply polling
    """

    def __init__(
        self,
        llm_client: "BaseLLMClient",
        window_manager: "WindowManager",
        screenshot_reader: "ScreenshotReader",
        window_info: "WindowInfo",
        prompt: str = "",
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
        self._client = llm_client
        self._wm = window_manager
        self._reader = screenshot_reader
        self._window = window_info
        self._prompt_manager = PromptManager(prompt)
        self._rounds = rounds
        self._max_wait = max_wait_seconds
        self._poll_interval = poll_interval
        self._manual_chat_rect = manual_chat_rect
        self._manual_input_rect = manual_input_rect
        self._manual_send_btn_pos = manual_send_btn_pos

        self._running = False
        self._memory = ConversationMemory()
        self._input_sim = InputSimulator()
        self._history: list[dict] = []

        self._chat_input = None
        self._macos_detector = None

        self._kb_enabled = False
        self._kb_manager = None
        self._kb_collections: list[str] | None = None
        self._strict_mode = strict_mode
        self._kb_source_lang: str | None = None

        if kb_config and kb_config.get("enabled"):
            try:
                from liao.knowledge.kb_config import KBConfig
                from liao.knowledge.kb_manager import KBManager

                cfg = KBConfig(
                    chroma_dir=kb_config.get("chroma_dir", ""),
                    embedding_model=kb_config.get("embedding_model", "nomic-embed-text"),
                    ollama_url=kb_config.get("ollama_url", "http://localhost:11434"),
                )
                mgr = KBManager(cfg)
                if mgr.retriever.is_available:
                    self._kb_manager = mgr
                    self._kb_collections = selected_kbs if selected_kbs else None
                    self._kb_enabled = True
                    logger.info("KB enabled with collections: %s", self._kb_collections or "all")
                else:
                    logger.warning("KB configured but ChromaDB not available")
            except Exception as e:
                logger.warning(f"Failed to initialize KB: {e}")

        self.on_status: Callable[[str], None] | None = None
        self.on_message_generated: Callable[[str], None] | None = None
        self.on_message_sent: Callable[[str], None] | None = None
        self.on_token_stream: Callable[[str], None] | None = None
        self.on_reply_detected: Callable[[str], None] | None = None
        self.on_error: Callable[[str], None] | None = None
        self.on_round_complete: Callable[[int], None] | None = None
        self.on_conversation_update: Callable[[str], None] | None = None
        self.on_kb_status: Callable[[str], None] | None = None

    @property
    def memory(self) -> ConversationMemory:
        return self._memory

    @property
    def is_running(self) -> bool:
        return self._running

    def stop(self) -> None:
        self._running = False

    def _emit_status(self, msg: str) -> None:
        if self.on_status:
            self.on_status(msg)

    def _emit_error(self, msg: str) -> None:
        if self.on_error:
            self.on_error(msg)

    def _focus_target(self) -> None:
        self._input_sim.focus_window(self._window.hwnd)
        time.sleep(0.3)

    def _get_chat_input(self):
        """Get or create ChatInput instance (macOS)."""
        if self._chat_input is None:
            from ..core.chat_input import ChatInput

            self._chat_input = ChatInput()
        return self._chat_input

    def _get_macos_detector(self):
        """Get or create MacOSAreaDetector instance."""
        if self._macos_detector is None:
            from ..core.macos_area_detector import MacOSAreaDetector

            self._macos_detector = MacOSAreaDetector()
        return self._macos_detector

    def run(self) -> None:
        """Run the automation workflow."""
        self._running = True

        system_msg = {"role": "system", "content": self._prompt_manager.get_system_prompt()}
        self._history = [system_msg]

        self._focus_target()
        areas = self._detect_areas()
        if areas is None:
            return

        chat_rect = areas.chat_area_rect
        input_rect = areas.input_area_rect

        if not self._reader.has_ocr():
            self._emit_status("No OCR engine - reply detection unavailable")
            logger.warning("No OCR engine")
        else:
            self._emit_status("Scanning existing conversation...")
        self._focus_target()
        ocr_parser = OCRChatParser(self._reader)
        initial = ocr_parser.parse_chat_area(self._window, chat_rect)

        print(f"\n{'=' * 50}")
        print("初始对话扫描:")
        for msg in initial:
            sender = "自己" if msg.sender == "self" else "对方"
            print(f"  [{sender}]: {msg.content}")
            if msg.sender == "self":
                self._memory.add_self_message(msg.content)
            else:
                self._memory.add_other_message(msg.content)
        print(f"{'=' * 50}\n")

        if initial:
            last_sender = "自己" if initial[-1].sender == "self" else "对方"
            self._emit_status(f"Found {len(initial)} existing messages, last: {last_sender}")
            self._update_conversation_display()
        else:
            self._emit_status("No existing messages found")

        if self._kb_enabled and self._kb_manager:
            self._detect_kb_language()

        round_num = 0

        while round_num < self._rounds and self._running:
            refreshed = self._wm.refresh_window_info(self._window)
            if not refreshed:
                self._emit_error("Window closed")
                return
            self._window = refreshed

            last_is_self = self._memory.is_last_message_from_self()
            has_messages = len(self._memory) > 0

            if has_messages and last_is_self:
                self._emit_status(f"Waiting for reply... ({round_num}/{self._rounds})")
                new_reply = self._poll_for_reply(ocr_parser, chat_rect, round_num)

                if not self._running:
                    return

                if new_reply:
                    print(f"\n<<< 收到回复: {new_reply}")
                    if self.on_reply_detected:
                        self.on_reply_detected(new_reply)
                    self._memory.add_other_message(new_reply)
                    self._update_conversation_display()
                    self._emit_status(f"Got reply: {new_reply[:50]}...")
                else:
                    self._emit_status("No reply received, waiting...")
                    round_num += 1
                    time.sleep(2)
                    continue

            round_num += 1

            self._history = [system_msg]
            context = self._memory.format_for_llm(max_messages=20)

            is_first = len(self._memory) == 0
            last_other = self._memory.get_last_other_message()
            previous_self = self._memory.get_recent_self_messages(n=5)

            kb_context = None
            if self._kb_enabled and self._kb_manager and last_other:
                kb_context = self._retrieve_kb_context(last_other, input_rect)
                if kb_context is None and self._strict_mode:
                    from .prompts import KB_STRICT_REFUSAL

                    self._emit_kb_status("Strict mode: no KB results, sending refusal")
                    refusal = KB_STRICT_REFUSAL
                    refreshed = self._wm.refresh_window_info(self._window)
                    if refreshed:
                        self._window = refreshed
                        self._send_via_input(refusal, input_rect)
                        self._memory.add_self_message(refusal)
                        if self.on_message_generated:
                            self.on_message_generated(refusal)
                        if self.on_message_sent:
                            self.on_message_sent(refusal)
                        self._update_conversation_display()
                    if self.on_round_complete:
                        self.on_round_complete(round_num)
                    time.sleep(1.5)
                    continue

            user_content = self._prompt_manager.build_chat_context(
                conversation_context=context,
                last_other_message=last_other,
                is_first_message=is_first,
                previous_self_messages=previous_self,
                kb_context=kb_context,
            )
            self._history.append({"role": "user", "content": user_content})

            self._emit_status(f"Round {round_num}/{self._rounds} - Generating...")

            try:
                generated = self._generate_and_send(input_rect)
                if not generated:
                    if not self._running:
                        return
                    self._emit_error("Generation failed: empty content")
                    time.sleep(2)
                    round_num -= 1
                    continue

                generated = generated.strip().strip('"').strip("'")
                for prefix in ("Me:", "Me: ", "I:", "I: "):
                    if generated.startswith(prefix):
                        generated = generated[len(prefix) :].strip()

                if self._is_duplicate(generated):
                    self._emit_status("Duplicate message detected, skipping")
                    time.sleep(1)
                    round_num -= 1
                    continue

                self._memory.add_self_message(generated)
                if self.on_message_generated:
                    self.on_message_generated(generated)
                self._update_conversation_display()

            except Exception as e:
                self._emit_error(f"Generation failed: {e}")
                if not self._running:
                    return
                time.sleep(2)
                round_num -= 1
                continue

            if not self._running:
                return

            self._emit_status(f"Round {round_num}/{self._rounds} - Sent")
            if self.on_message_sent:
                self.on_message_sent(generated)
            if self.on_round_complete:
                self.on_round_complete(round_num)

            if round_num >= self._rounds:
                break
            if not self._running:
                return

            time.sleep(1.5)

        self._emit_status(f"Completed {round_num}/{self._rounds} rounds")
        self._running = False

    def _emit_kb_status(self, msg: str) -> None:
        if self.on_kb_status:
            self.on_kb_status(msg)

    def _detect_kb_language(self) -> None:
        try:
            from .kb_helpers import sample_kb_documents, detect_language

            self._emit_kb_status("Detecting KB language...")
            sample = sample_kb_documents(self._kb_manager, self._kb_collections)
            if sample:
                self._kb_source_lang = detect_language(self._client, sample)
                self._emit_kb_status(f"KB language: {self._kb_source_lang}")
            else:
                self._kb_source_lang = None
                self._emit_kb_status("No KB documents found")
        except Exception as e:
            logger.warning(f"KB language detection failed: {e}")
            self._kb_source_lang = None

    def _retrieve_kb_context(
        self, last_other: str, input_rect: tuple[int, int, int, int]
    ) -> str | None:
        from .kb_helpers import detect_language, translate_text, languages_differ

        self._emit_kb_status("Searching knowledge base...")

        try:
            query = last_other

            cross_lingual = False
            conv_lang = None
            if self._kb_source_lang:
                conv_lang = detect_language(self._client, last_other)
                if languages_differ(conv_lang, self._kb_source_lang):
                    cross_lingual = True
                    self._emit_kb_status(f"Cross-lingual: {conv_lang} -> {self._kb_source_lang}")
                    query = translate_text(
                        self._client, last_other, conv_lang, self._kb_source_lang
                    )

            self._emit_kb_status(f"Query: {query[:50]}...")
            results = self._kb_manager.retriever.search(
                query=query,
                n_results=5,
                collection_names=self._kb_collections,
            )

            if not results:
                self._emit_kb_status("No KB results found")
                return None

            context = self._kb_manager.retriever.format_context(results)
            if cross_lingual:
                self._emit_kb_status(f"Translating {len(results)} KB results...")
                context = translate_text(self._client, context, self._kb_source_lang, conv_lang)

            self._emit_kb_status(f"Found {len(results)} KB results")
            return context

        except Exception as e:
            logger.warning(f"KB retrieval failed: {e}")
            self._emit_kb_status(f"KB retrieval error: {e}")
            return None

    def _detect_areas(self) -> AreaDetectionResult | None:
        """Detect areas using automatic detection only.

        完全依赖自动检测，忽略手动设置（手动坐标有DPI问题）。
        OCR失败时使用固定比例布局。
        """
        self._emit_status("正在自动检测区域...")
        print(f"\n>>> 自动检测区域 (窗口: {self._window.rect})")

        if IS_MACOS:
            detector = self._get_macos_detector()
            result = detector.detect_areas(self._window)
            if result:
                print(f"    自动检测聊天区域: {result.chat_rect}")
                print(f"    自动检测输入区域: {result.input_rect}")
                self._emit_status(f"检测完成 ({result.method}, {result.confidence:.0%})")
                return AreaDetectionResult(
                    chat_area_rect=result.chat_rect,
                    input_area_rect=result.input_rect,
                    method=result.method,
                    confidence=result.confidence,
                )
            self._emit_error("自动检测失败，使用默认布局")
            # 使用默认布局
            rect = self._window.rect
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]
            chat_left = rect[0] + int(w * 0.35)
            chat_top = rect[1] + int(h * 0.05)
            chat_right = rect[2] - int(w * 0.01)
            chat_bottom = rect[1] + int(h * 0.85)
            input_top = chat_bottom
            input_bottom = rect[3] - int(h * 0.01)

            return AreaDetectionResult(
                chat_area_rect=(chat_left, chat_top, chat_right, chat_bottom),
                input_area_rect=(chat_left, input_top, chat_right, input_bottom),
                method="fallback",
                confidence=0.6,
            )

        detector = ChatAreaDetector(self._reader)
        areas = detector.detect_areas(self._window)
        print(f"    自动检测聊天区域: {areas.chat_area_rect}")
        print(f"    自动检测输入区域: {areas.input_area_rect}")
        self._emit_status(f"检测完成 ({areas.method}, {areas.confidence:.0%})")
        return areas

    def _generate_and_send(self, input_rect: tuple[int, int, int, int]) -> str:
        """Generate response and send it."""
        accumulated = ""

        for token in self._client.chat_stream(self._history, temperature=0.65):
            if not self._running:
                return accumulated
            accumulated += token
            if self.on_token_stream:
                self.on_token_stream(accumulated)

        accumulated = accumulated.strip()
        if not accumulated:
            return ""

        refreshed = self._wm.refresh_window_info(self._window)
        if not refreshed:
            return ""
        self._window = refreshed

        if IS_MACOS:
            self._send_via_input(accumulated, input_rect)
        else:
            ix = (input_rect[0] + input_rect[2]) // 2
            iy = (input_rect[1] + input_rect[3]) // 2
            self._input_sim.click_and_type(
                x=ix,
                y=iy,
                text=accumulated,
                hwnd=self._window.hwnd,
                win_rect=self._window.rect,
                clear_first=True,
                move_duration=0.4,
            )
            self._send_message(input_rect)

        return accumulated

    def _send_via_input(
        self, text: str, input_rect: tuple[int, int, int, int] | None = None
    ) -> None:
        """Send message on macOS using ChatInput."""
        logger.info(f"macOS send_message: {len(text)} chars")

        chat_input = self._get_chat_input()
        chat_input.send_message(text, self._window, method="enter")

    def _send_message(self, input_rect: tuple[int, int, int, int] | None = None) -> None:
        """Send the typed message (non-macOS)."""
        hwnd = self._window.hwnd
        win_rect = self._window.rect

        logger.debug("Send: re-focusing target window %s", hwnd)
        self._input_sim.focus_window(hwnd)
        time.sleep(0.3)

        if self._manual_send_btn_pos:
            bx, by = self._manual_send_btn_pos
            logger.info("Send Strategy 1: clicking manual send button at (%d, %d)", bx, by)
            self._input_sim.click_in_window(hwnd, win_rect[0], win_rect[1], bx, by)
            time.sleep(0.3)
            logger.info("Send Strategy 1: also pressing Enter as backup")
            self._input_sim.press_key("enter")
            time.sleep(0.2)
            return

        if input_rect:
            bx = input_rect[2] - 45
            by = input_rect[3] - 15
            logger.info("Send Strategy 2: clicking estimated send button at (%d, %d)", bx, by)
            self._input_sim.click_in_window(hwnd, win_rect[0], win_rect[1], bx, by)
            time.sleep(0.5)

        logger.info("Send: executing Enter/Ctrl+Enter fallbacks")
        if input_rect:
            ix = (input_rect[0] + input_rect[2]) // 2
            iy = (input_rect[1] + input_rect[3]) // 2
            logger.info("Send Strategy 3: clicking input center at (%d, %d)", ix, iy)
            self._input_sim.click_in_window(hwnd, win_rect[0], win_rect[1], ix, iy)
            time.sleep(0.1)

        logger.info("Send Strategy 3: pressing Enter")
        self._input_sim.press_key("enter")
        time.sleep(0.3)

        logger.info("Send Strategy 4: pressing Ctrl+Enter")
        self._input_sim.hotkey("ctrl", "enter")
        time.sleep(0.3)

    def _handle_no_reply(self, input_rect: tuple[int, int, int, int]) -> str:
        """Handle no-reply timeout by sending a probe."""
        prompt = self._prompt_manager.get_no_reply_prompt(int(self._max_wait))
        try:
            response = self._client.chat(
                self._history + [{"role": "user", "content": prompt}], temperature=0.5
            )
            response = response.strip().strip('"').strip("'")

            if response.upper() == "WAIT":
                self._emit_status("Continuing to wait...")
                return ""

            refreshed = self._wm.refresh_window_info(self._window)
            if not refreshed:
                return ""
            self._window = refreshed

            if IS_MACOS:
                self._send_via_input(response, input_rect)
            else:
                ix = (input_rect[0] + input_rect[2]) // 2
                iy = (input_rect[1] + input_rect[3]) // 2
                self._input_sim.click_and_type(
                    x=ix,
                    y=iy,
                    text=response,
                    hwnd=self._window.hwnd,
                    win_rect=self._window.rect,
                    clear_first=True,
                    move_duration=0.3,
                )
                self._send_message(input_rect)
            return response
        except Exception as e:
            self._emit_error(f"Follow-up generation failed: {e}")
        return ""

    def _poll_for_reply(
        self, ocr_parser: OCRChatParser, chat_rect: tuple[int, int, int, int], round_num: int
    ) -> str:
        """Poll for new reply from other party."""
        start = time.time()
        while time.time() - start < self._max_wait:
            if not self._running:
                return ""

            elapsed = int(time.time() - start)
            self._emit_status(
                f"Round {round_num}/{self._rounds} - Waiting... ({elapsed}/{int(self._max_wait)}s)"
            )
            time.sleep(self._poll_interval)

            if not self._running:
                return ""

            refreshed = self._wm.refresh_window_info(self._window)
            if not refreshed:
                return ""
            self._window = refreshed

            self._focus_target()
            current = ocr_parser.parse_chat_area(self._window, chat_rect)
            new_msgs = ocr_parser.find_new_other_messages(current, self._memory)

            if new_msgs:
                newest = new_msgs[-1]
                logger.info("New reply detected: %s", newest.content[:60])
                return newest.content

        return ""

    def _is_duplicate(self, text: str) -> bool:
        """Check if text duplicates or is too similar to recent self messages."""
        recent = [m.content for m in self._memory.messages if m.sender == "self"][-5:]
        normalized = text.replace(" ", "").replace("\n", "").lower()

        for msg in recent:
            msg_normalized = msg.replace(" ", "").replace("\n", "").lower()

            # 完全匹配
            if normalized == msg_normalized:
                return True

            # 高相似度检查（一个包含另一个超过80%）
            if len(normalized) > 5 and len(msg_normalized) > 5:
                if normalized in msg_normalized or msg_normalized in normalized:
                    return True

                # 检查重叠字符比例
                common = sum(1 for c in normalized if c in msg_normalized)
                if common / max(len(normalized), len(msg_normalized)) > 0.8:
                    return True

        return False

    def _update_conversation_display(self) -> None:
        if self.on_conversation_update:
            self.on_conversation_update(self._memory.format_for_display_html())
