"""Area detection result data model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AreaDetectionResult:
    """Result of chat/input area detection.
    
    Attributes:
        chat_area_rect: Bounding rectangle of chat message area (left, top, right, bottom)
        input_area_rect: Bounding rectangle of input text area (left, top, right, bottom)
        method: Detection method used ("ocr", "heuristic", "manual")
        confidence: Detection confidence score (0.0 to 1.0)
    """
    
    chat_area_rect: tuple[int, int, int, int]
    input_area_rect: tuple[int, int, int, int]
    method: str = "heuristic"
    confidence: float = 0.5

    @property
    def chat_width(self) -> int:
        """Width of chat area in pixels."""
        return self.chat_area_rect[2] - self.chat_area_rect[0]

    @property
    def chat_height(self) -> int:
        """Height of chat area in pixels."""
        return self.chat_area_rect[3] - self.chat_area_rect[1]

    @property
    def chat_center(self) -> tuple[int, int]:
        """Center point of chat area (x, y)."""
        return (
            (self.chat_area_rect[0] + self.chat_area_rect[2]) // 2,
            (self.chat_area_rect[1] + self.chat_area_rect[3]) // 2,
        )

    @property
    def input_width(self) -> int:
        """Width of input area in pixels."""
        return self.input_area_rect[2] - self.input_area_rect[0]

    @property
    def input_height(self) -> int:
        """Height of input area in pixels."""
        return self.input_area_rect[3] - self.input_area_rect[1]

    @property
    def input_center(self) -> tuple[int, int]:
        """Center point of input area (x, y)."""
        return (
            (self.input_area_rect[0] + self.input_area_rect[2]) // 2,
            (self.input_area_rect[1] + self.input_area_rect[3]) // 2,
        )

    def __str__(self) -> str:
        return (
            f"AreaDetectionResult(method={self.method!r}, confidence={self.confidence:.0%}, "
            f"chat={self.chat_width}x{self.chat_height}, input={self.input_width}x{self.input_height})"
        )
