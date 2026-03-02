"""OCR chat message parser."""

from __future__ import annotations

import re
import logging
from typing import TYPE_CHECKING

from ..models.message import ChatMessage

if TYPE_CHECKING:
    from ..models.window import WindowInfo
    from ..core.screenshot import ScreenshotReader
    from .conversation import ConversationMemory

logger = logging.getLogger(__name__)

# System text patterns to filter (timestamps, status, media)
SYSTEM_TEXT_PATTERNS = [
    re.compile(r"^\d{1,2}:\d{2}(:\d{2})?$"),
    re.compile(r"^(AM|PM|上午|下午)\s*\d{1,2}:\d{2}$", re.IGNORECASE),
    re.compile(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}$"),
    re.compile(r"^(Yesterday|Today|Tomorrow|昨天|前天|今天|星期[一二三四五六日天]|周[一二三四五六日天])$", re.IGNORECASE),
    re.compile(r"^(Read|Sent|Delivered|Typing|已读|已撤回|对方正在输入|消息已发送|以下为新消息)", re.IGNORECASE),
    re.compile(r"^\[(Image|Photo|Voice|Video|File|Location|Contact|Sticker|图片|语音|视频|文件|位置|名片|红包|转账)\]$", re.IGNORECASE),
]


def is_system_text(text: str) -> bool:
    """Check if text is a system message to be filtered.
    
    Args:
        text: Text to check
        
    Returns:
        True if text should be filtered out
    """
    text = text.strip()
    if len(text) < 2:
        return True
    for pattern in SYSTEM_TEXT_PATTERNS:
        if pattern.search(text):
            return True
    return False


class OCRChatParser:
    """Parse OCR results into ChatMessage objects with sender attribution.
    
    Uses text position (left/right alignment) to determine sender.
    
    Example:
        parser = OCRChatParser(screenshot_reader)
        messages = parser.parse_chat_area(window_info, chat_rect)
        for msg in messages:
            print(f"{msg.sender}: {msg.content}")
    """

    def __init__(self, screenshot_reader: "ScreenshotReader"):
        self._reader = screenshot_reader

    def parse_chat_area(
        self,
        window_info: "WindowInfo",
        chat_rect: tuple[int, int, int, int]
    ) -> list[ChatMessage]:
        """Parse chat messages from a region.
        
        Args:
            window_info: Window being analyzed
            chat_rect: Chat area rectangle (screen coords)
            
        Returns:
            List of parsed ChatMessage objects
        """
        image = self._reader.capture_region(window_info, chat_rect)
        if image is None:
            return []
        
        results = self._reader.extract_with_bboxes(image)
        if not results:
            return []
        
        img_w, _ = image.size
        return self._parse_ocr_results(results, img_w)

    def _parse_ocr_results(
        self,
        results: list[tuple[list, str, float]],
        image_width: int
    ) -> list[ChatMessage]:
        """Parse OCR results into messages.
        
        Args:
            results: OCR results (bbox, text, confidence)
            image_width: Width of the image
            
        Returns:
            List of ChatMessage objects
        """
        # Filter system text, collect with position info
        items = []
        for bbox, text, conf in results:
            if is_system_text(text):
                continue
            cx = sum(p[0] for p in bbox) / 4
            cy = sum(p[1] for p in bbox) / 4
            left_x = min(p[0] for p in bbox)
            right_x = max(p[0] for p in bbox)
            top_y = min(p[1] for p in bbox)
            side = "left" if cx < image_width * 0.5 else "right"
            items.append({
                "text": text,
                "cx": cx,
                "cy": cy,
                "left_x": left_x,
                "right_x": right_x,
                "top_y": top_y,
                "side": side,
                "bbox": bbox,
            })

        if not items:
            return []

        # Sort by vertical position
        items.sort(key=lambda b: b["cy"])

        # Group by vertical proximity AND horizontal side
        groups: list[list[dict]] = []
        for item in items:
            if (groups and 
                (item["cy"] - groups[-1][-1]["cy"]) < 40 and 
                item["side"] == groups[-1][-1]["side"]):
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
            # Determine sender based on alignment
            sender = "other" if left_margin < right_margin else "self"
            messages.append(ChatMessage(sender=sender, content=text))

        return messages

    def find_new_messages(
        self,
        current: list[ChatMessage],
        memory: "ConversationMemory"
    ) -> list[ChatMessage]:
        """Find messages not already in memory.
        
        Args:
            current: Currently parsed messages
            memory: Existing conversation memory
            
        Returns:
            List of new messages
        """
        known = {self._normalize(m.content) for m in memory.messages}
        new = []
        for msg in current:
            norm = self._normalize(msg.content)
            if norm and norm not in known:
                # Also check for partial matches
                if not any(norm in k or k in norm for k in known if len(k) > 5):
                    new.append(msg)
        return new

    def find_new_other_messages(
        self,
        current: list[ChatMessage],
        memory: "ConversationMemory"
    ) -> list[ChatMessage]:
        """Find new messages from other party only.
        
        Args:
            current: Currently parsed messages
            memory: Existing conversation memory
            
        Returns:
            List of new messages from other party
        """
        new_others = [m for m in self.find_new_messages(current, memory) if m.sender == "other"]
        if not new_others:
            return []
        
        # Filter out fragments that are likely misattributed pieces of self's messages
        recent_self = [m.content for m in memory.messages if m.sender == "self"][-5:]
        return [m for m in new_others if not self._is_likely_fragment(m.content, recent_self)]

    @staticmethod
    def _is_likely_fragment(text: str, recent_self_texts: list[str]) -> bool:
        """Check if text is likely a misattributed fragment.
        
        Args:
            text: Text to check
            recent_self_texts: Recent messages from self
            
        Returns:
            True if text is likely a fragment
        """
        text = text.strip()
        if not text:
            return True
        
        # Very short text ending in continuation punctuation
        if len(text) < 6 and text[-1:] in (",", "，", "、", "-", "—", ":", "："):
            return True
        
        # Very short text after stripping punctuation
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
        """Normalize text for comparison.
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized text
        """
        return text.strip().replace(" ", "").replace("\n", "")
