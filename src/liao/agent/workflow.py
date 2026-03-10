"""Agent workflow orchestration with knowledge base support."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Callable

from .conversation import ConversationMemory
from .chat_parser import OCRChatParser
from .prompts import PromptManager
from ..core.area_detector import ChatAreaDetector
from ..core.input_simulator import InputSimulator, focus_window_hard, send_enter, send_ctrl_enter
from ..models.detection import AreaDetectionResult

if TYPE_CHECKING:
    from ..models.window import WindowInfo
    from ..core.window_manager import WindowManager
    from ..core.screenshot import ScreenshotReader
    from ..llm.base import BaseLLMClient

logger = logging.getLogger(__name__)


class AgentWorkflow:
    """Orchestrates the vision agent automation loop.
    
    Manages the flow of:
    1. Area detection
    2. Initial OCR scan
    3. Reply gate (wait for other's message)
    4. Message generation via LLM
    5. Message sending via input simulation
    6. Reply polling
    
    Example:
        workflow = AgentWorkflow(
            llm_client=client,
            window_manager=wm,
            screenshot_reader=reader,
            window_info=window,
            prompt="Be friendly",
            rounds=5,
        )
        workflow.run()
    """

    def __init__(
        self,
        llm_client: "BaseLLMClient",
        window_manager: "WindowManager",
        screenshot_reader: "ScreenshotReader",
        window_info: "WindowInfo",
        prompt: str = "",
        rounds: int = 10,
        max_wait_seconds: float = 60.0,
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
        
        # KB state
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
        
        # Callbacks
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
        """Get conversation memory."""
        return self._memory

    @property
    def is_running(self) -> bool:
        """Check if workflow is running."""
        return self._running

    def stop(self) -> None:
        """Stop the workflow."""
        self._running = False

    def _emit_status(self, msg: str) -> None:
        if self.on_status:
            self.on_status(msg)

    def _emit_error(self, msg: str) -> None:
        if self.on_error:
            self.on_error(msg)

    def _focus_target(self) -> None:
        """Bring the target window to the foreground before capturing."""
        self._input_sim.focus_window(self._window.hwnd)
        time.sleep(0.3)

    def run(self) -> None:
        """Run the automation workflow."""
        self._running = True
        
        # Setup
        system_msg = {"role": "system", "content": self._prompt_manager.get_system_prompt()}
        self._history = [system_msg]

        # Area detection - focus window first so screenshot captures it
        self._focus_target()
        areas = self._detect_areas()
        if areas is None:
            return
        
        chat_rect = areas.chat_area_rect
        input_rect = areas.input_area_rect
        
        # Initial OCR scan
        if not self._reader.has_ocr():
            self._emit_status("No OCR engine - reply detection unavailable. Install: pip install easyocr")
            logger.warning("No OCR engine; conversation extraction will not work")
        else:
            self._emit_status("Scanning existing conversation...")
        self._focus_target()
        ocr_parser = OCRChatParser(self._reader)
        initial = ocr_parser.parse_chat_area(self._window, chat_rect)
        for msg in initial:
            if msg.sender == "self":
                self._memory.add_self_message(msg.content)
            else:
                self._memory.add_other_message(msg.content)
        
        if initial:
            self._emit_status(f"Found {len(initial)} existing messages")
            self._update_conversation_display()
        else:
            self._emit_status("No existing messages found")

        # KB language detection (once per session)
        if self._kb_enabled and self._kb_manager:
            self._detect_kb_language()

        # Main loop
        round_num = 0
        consecutive_no_reply = 0

        while round_num < self._rounds and self._running:
            # Refresh window
            refreshed = self._wm.refresh_window_info(self._window)
            if not refreshed:
                self._emit_error("Window closed")
                return
            self._window = refreshed

            # Reply gate - wait for other's reply if last message is from self.
            # Skip the gate on round 0 so the bot can initiate conversations
            # and users can test the send functionality immediately.
            if round_num > 0 and self._memory.is_last_message_from_self():
                self._emit_status(f"Waiting for reply... (completed {round_num}/{self._rounds} rounds)")
                new_reply = self._poll_for_reply(ocr_parser, chat_rect, round_num)
                
                if not self._running:
                    return
                
                if new_reply:
                    if self.on_reply_detected:
                        self.on_reply_detected(new_reply)
                    self._memory.add_other_message(new_reply)
                    self._update_conversation_display()
                    consecutive_no_reply = 0
                else:
                    consecutive_no_reply += 1
                    if consecutive_no_reply >= 2:
                        self._emit_status("No reply, skipping round")
                        round_num += 1
                        consecutive_no_reply = 0
                        time.sleep(2)
                        continue
                    
                    # Send a probe message
                    self._emit_status("Timeout, sending follow-up...")
                    probe = self._handle_no_reply(input_rect)
                    if probe:
                        self._memory.add_self_message(probe)
                        if self.on_message_sent:
                            self.on_message_sent(probe)
                        self._update_conversation_display()
                    continue

            # Generate and send
            round_num += 1
            consecutive_no_reply = 0

            # Rebuild history
            self._history = [system_msg]
            context = self._memory.format_for_llm(max_messages=20)
            
            is_first = len(self._memory) == 0
            last_other = self._memory.get_last_other_message()
            previous_self = self._memory.get_recent_self_messages(n=5)
            
            # KB retrieval (before generation)
            kb_context = None
            if self._kb_enabled and self._kb_manager and last_other:
                kb_context = self._retrieve_kb_context(last_other, input_rect)
                if kb_context is None and self._strict_mode:
                    # Strict mode: refuse and skip generation
                    from .prompts import KB_STRICT_REFUSAL
                    self._emit_kb_status("Strict mode: no KB results, sending refusal")
                    refusal = KB_STRICT_REFUSAL
                    refreshed = self._wm.refresh_window_info(self._window)
                    if refreshed:
                        self._window = refreshed
                        ix = (input_rect[0] + input_rect[2]) // 2
                        iy = (input_rect[1] + input_rect[3]) // 2
                        self._input_sim.click_and_type(
                            x=ix, y=iy, text=refusal,
                            hwnd=self._window.hwnd,
                            win_rect=self._window.rect,
                            clear_first=True, move_duration=0.4
                        )
                        self._send_message(input_rect)
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
                generated = self._generate_and_type(input_rect)
                if not generated:
                    if not self._running:
                        return
                    self._emit_error("Generation failed: empty content")
                    time.sleep(2)
                    round_num -= 1
                    continue
                
                # Clean up generated text
                generated = generated.strip().strip('"').strip("'")
                for prefix in ("Me:", "Me: ", "I:", "I: "):
                    if generated.startswith(prefix):
                        generated = generated[len(prefix):].strip()
                
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

            # Send
            self._send_message(input_rect)
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
        """Detect KB source language by sampling documents."""
        try:
            from .kb_helpers import sample_kb_documents, detect_language

            self._emit_kb_status("Detecting KB language...")
            sample = sample_kb_documents(self._kb_manager, self._kb_collections)
            if sample:
                self._kb_source_lang = detect_language(self._client, sample)
                self._emit_kb_status(f"KB language: {self._kb_source_lang}")
            else:
                self._kb_source_lang = None
                self._emit_kb_status("No KB documents found for language detection")
        except Exception as e:
            logger.warning(f"KB language detection failed: {e}")
            self._kb_source_lang = None

    def _retrieve_kb_context(
        self, last_other: str, input_rect: tuple[int, int, int, int]
    ) -> str | None:
        """Retrieve KB context for the current conversation turn.

        Handles cross-lingual translation if KB language differs from
        conversation language.

        Returns:
            KB context string to inject into prompt, or None if no results.
        """
        from .kb_helpers import detect_language, translate_text, languages_differ

        self._emit_kb_status("Searching knowledge base...")

        try:
            query = last_other

            # Cross-lingual: detect conversation language and translate query if needed
            cross_lingual = False
            conv_lang = None
            if self._kb_source_lang:
                conv_lang = detect_language(self._client, last_other)
                if languages_differ(conv_lang, self._kb_source_lang):
                    cross_lingual = True
                    self._emit_kb_status(
                        f"Cross-lingual: {conv_lang} -> {self._kb_source_lang}"
                    )
                    query = translate_text(
                        self._client, last_other, conv_lang, self._kb_source_lang
                    )

            # Search KB
            context_str, sources = self._kb_manager.search_and_synthesize(
                query, self._kb_collections, max_chars=4000
            )

            if not context_str:
                self._emit_kb_status("No relevant KB content found")
                return None

            self._emit_kb_status(f"Found {len(sources)} KB sources")

            # Translate results back to conversation language if cross-lingual
            if cross_lingual and conv_lang:
                self._emit_kb_status("Translating KB results...")
                context_str = translate_text(
                    self._client, context_str, self._kb_source_lang, conv_lang
                )

            return context_str

        except Exception as e:
            logger.warning(f"KB retrieval failed: {e}")
            self._emit_kb_status(f"KB retrieval error: {e}")
            return None

    def _detect_areas(self) -> AreaDetectionResult | None:
        """Detect or use manual areas."""
        if self._manual_chat_rect or self._manual_input_rect:
            self._emit_status("Using manual area selection")
            chat_r = self._manual_chat_rect
            input_r = self._manual_input_rect
            if chat_r and not input_r:
                input_r = (chat_r[0], chat_r[3], chat_r[2], chat_r[3] + 60)
            elif input_r and not chat_r:
                chat_r = (input_r[0], input_r[1] - 300, input_r[2], input_r[1])
            return AreaDetectionResult(
                chat_area_rect=chat_r,
                input_area_rect=input_r,
                method="manual",
                confidence=1.0,
            )
        
        self._emit_status("Detecting areas...")
        detector = ChatAreaDetector(self._reader)
        areas = detector.detect_areas(self._window)
        self._emit_status(f"Detection complete ({areas.method}, {areas.confidence:.0%})")
        return areas

    def _generate_and_type(self, input_rect: tuple[int, int, int, int]) -> str:
        """Generate response and type it into input field."""
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
        
        # Refresh window and type
        refreshed = self._wm.refresh_window_info(self._window)
        if not refreshed:
            return ""
        self._window = refreshed
        
        ix = (input_rect[0] + input_rect[2]) // 2
        iy = (input_rect[1] + input_rect[3]) // 2
        self._input_sim.click_and_type(
            x=ix, y=iy, text=accumulated,
            hwnd=self._window.hwnd,
            win_rect=self._window.rect,
            clear_first=True, move_duration=0.4
        )
        return accumulated

    def _send_message(self, input_rect: tuple[int, int, int, int] | None = None) -> None:
        """Send the typed message by clicking the send button.

        Between _generate_and_type() and this method, Qt signal emissions
        (on_message_generated, conversation_update) cause the Liao GUI to
        update, which steals window focus from the target app on Wayland.
        Therefore we MUST re-focus the target window before any action, and
        use a mouse click on the send button as the primary strategy (key
        presses are unreliable when focus state is uncertain).

        Args:
            input_rect: Input area rectangle, used to estimate send button.
        """
        hwnd = self._window.hwnd
        win_rect = self._window.rect  # (left, top, right, bottom)

        # Always re-focus the target window first - critical on Wayland
        # where the Liao GUI signal handlers can steal focus.
        logger.debug("Send: re-focusing target window %s", hwnd)
        self._input_sim.focus_window(hwnd)
        time.sleep(0.3)

        # Strategy 1: Click manually-set send button position (center of user-selected area)
        if self._manual_send_btn_pos:
            bx, by = self._manual_send_btn_pos
            logger.info("Send Strategy 1: clicking manual send button center at (%d, %d)", bx, by)
            self._input_sim.click_in_window(hwnd, win_rect[0], win_rect[1], bx, by)
            time.sleep(0.3)
            # Also try Enter as backup in case click didn't register
            logger.info("Send Strategy 1: also pressing Enter as backup")
            self._input_sim.press_key("enter")
            time.sleep(0.2)
            return

        # Strategy 2: Click estimated send button position.
        # In WeChat the "发送(S)" button sits at the bottom-right of the
        # input panel.  Use click_in_window for Wayland compatibility.
        if input_rect:
            bx = input_rect[2] - 45   # ~45px from right edge
            by = input_rect[3] - 15   # ~15px from bottom edge
            logger.info("Send Strategy 2: clicking estimated send button at (%d, %d)", bx, by)
            self._input_sim.click_in_window(hwnd, win_rect[0], win_rect[1], bx, by)
            time.sleep(0.5)
            logger.info("Send Strategy 2: click done, continuing to fallbacks")

        # Strategy 3 & 4: Also try Enter and Ctrl+Enter as fallbacks.
        # The window was re-focused above so these key presses should
        # reach the target app.  Click input field center first to
        # ensure keyboard focus is on the text widget.
        logger.info("Send: executing Enter/Ctrl+Enter fallbacks (input_rect=%s)", input_rect is not None)
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
        logger.info("Send: all strategies completed")

    def _handle_no_reply(self, input_rect: tuple[int, int, int, int]) -> str:
        """Handle no-reply timeout by sending a probe."""
        prompt = self._prompt_manager.get_no_reply_prompt(int(self._max_wait))
        try:
            response = self._client.chat(
                self._history + [{"role": "user", "content": prompt}],
                temperature=0.5
            )
            response = response.strip().strip('"').strip("'")
            
            if response.upper() == "WAIT":
                self._emit_status("Continuing to wait...")
                return ""
            
            refreshed = self._wm.refresh_window_info(self._window)
            if not refreshed:
                return ""
            self._window = refreshed
            
            ix = (input_rect[0] + input_rect[2]) // 2
            iy = (input_rect[1] + input_rect[3]) // 2
            self._input_sim.click_and_type(
                x=ix, y=iy, text=response,
                hwnd=self._window.hwnd,
                win_rect=self._window.rect,
                clear_first=True, move_duration=0.3
            )
            self._send_message(input_rect)
            return response
        except Exception as e:
            self._emit_error(f"Follow-up generation failed: {e}")
        return ""

    def _poll_for_reply(
        self,
        ocr_parser: OCRChatParser,
        chat_rect: tuple[int, int, int, int],
        round_num: int
    ) -> str:
        """Poll for new reply from other party."""
        start = time.time()
        while time.time() - start < self._max_wait:
            if not self._running:
                return ""
            
            elapsed = int(time.time() - start)
            self._emit_status(f"Round {round_num}/{self._rounds} - Waiting... ({elapsed}/{int(self._max_wait)}s)")
            time.sleep(self._poll_interval)
            
            if not self._running:
                return ""
            
            refreshed = self._wm.refresh_window_info(self._window)
            if not refreshed:
                return ""
            self._window = refreshed
            
            self._focus_target()
            current = ocr_parser.parse_chat_area(self._window, chat_rect)
            new_others = ocr_parser.find_new_other_messages(current, self._memory)
            
            if new_others:
                # Add all but the last to memory
                for msg in new_others[:-1]:
                    self._memory.add_other_message(msg.content)
                return new_others[-1].content
        
        return ""

    def _is_duplicate(self, new_msg: str) -> bool:
        """Check if message is duplicate of recent self messages."""
        # Use the enhanced duplicate detection from ConversationMemory
        if self._memory.is_duplicate_or_similar(new_msg, threshold=0.6):
            return True
        
        # Also do a simple exact match check
        clean = new_msg.strip().replace(" ", "").replace("\n", "")
        if not clean:
            return True
        
        for msg in self._memory.messages[-10:]:
            if msg.sender == "self":
                old = msg.content.strip().replace(" ", "").replace("\n", "")
                if clean == old:
                    return True
                if len(clean) > 10 and clean in old:
                    return True
                if len(old) > 10 and old in clean:
                    return True
        return False

    def _update_conversation_display(self) -> None:
        """Update conversation display via callback."""
        if self.on_conversation_update:
            html = self._memory.format_for_display_html()
            self.on_conversation_update(html)
