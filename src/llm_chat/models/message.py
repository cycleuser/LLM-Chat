"""Chat message data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ChatMessage:
    """A single chat message with sender attribution.
    
    Attributes:
        sender: Message sender ("self" or "other")
        content: Message text content
        msg_type: Message type ("text", "image", "voice", "video", "file", etc.)
        timestamp: Optional timestamp string
        created_at: When this message object was created
    """
    
    sender: str  # "self" or "other"
    content: str
    msg_type: str = "text"
    timestamp: str | None = None
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def is_self(self) -> bool:
        """Check if message is from self."""
        return self.sender == "self"

    @property
    def is_other(self) -> bool:
        """Check if message is from other party."""
        return self.sender == "other"

    @property
    def is_text(self) -> bool:
        """Check if message is a text message."""
        return self.msg_type == "text"

    def __str__(self) -> str:
        sender_label = "Me" if self.is_self else "Other"
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"[{sender_label}] {content_preview}"
