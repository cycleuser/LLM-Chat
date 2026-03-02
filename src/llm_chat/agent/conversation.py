"""Conversation memory management."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..models.message import ChatMessage

if TYPE_CHECKING:
    pass


class ConversationMemory:
    """Structured conversation memory with sender attribution.
    
    Maintains a history of chat messages with proper sender tracking
    and formatting utilities for LLM consumption and display.
    
    Example:
        memory = ConversationMemory(contact_name="Alice")
        memory.add_other_message("Hello!")
        memory.add_self_message("Hi there!")
        
        # Format for LLM
        context = memory.format_for_llm()
        
        # Format for display
        html = memory.format_for_display_html()
    """

    def __init__(self, contact_name: str = "Other"):
        self._contact_name = contact_name
        self._messages: list[ChatMessage] = []

    @property
    def contact_name(self) -> str:
        """Get contact name."""
        return self._contact_name

    @contact_name.setter
    def contact_name(self, value: str) -> None:
        """Set contact name."""
        self._contact_name = value

    @property
    def messages(self) -> list[ChatMessage]:
        """Get all messages."""
        return self._messages

    def add_self_message(self, content: str, msg_type: str = "text") -> None:
        """Add a message from self.
        
        Args:
            content: Message content
            msg_type: Message type (text, image, etc.)
        """
        self._messages.append(ChatMessage(
            sender="self",
            content=content,
            msg_type=msg_type,
        ))

    def add_other_message(self, content: str, msg_type: str = "text") -> None:
        """Add a message from the other party.
        
        Args:
            content: Message content
            msg_type: Message type (text, image, etc.)
        """
        self._messages.append(ChatMessage(
            sender="other",
            content=content,
            msg_type=msg_type,
        ))

    def format_for_llm(self, max_messages: int = 20) -> str:
        """Format conversation for LLM with highlighted latest exchange.
        
        Args:
            max_messages: Maximum number of recent messages to include
            
        Returns:
            Formatted conversation string
        """
        msgs = self._messages[-max_messages:]
        if not msgs:
            return "[Conversation is empty]"

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
                parts.append("[Conversation History]")
                for m in history:
                    sender = "Me" if m.sender == "self" else "Other"
                    if m.msg_type == "text":
                        parts.append(f"{sender}: {m.content}")
                    else:
                        parts.append(f"{sender}: [{m.msg_type}]")
                parts.append("")
            parts.append("[Current - Please reply to this]")
            for m in current:
                sender = "Me" if m.sender == "self" else "Other"
                if m.msg_type == "text":
                    parts.append(f"{sender}: {m.content}")
                else:
                    parts.append(f"{sender}: [{m.msg_type}]")
            return "\n".join(parts)
        else:
            # All messages, no clear latest exchange
            lines = ["[Conversation]"]
            for m in msgs:
                sender = "Me" if m.sender == "self" else "Other"
                if m.msg_type == "text":
                    lines.append(f"{sender}: {m.content}")
                else:
                    lines.append(f"{sender}: [{m.msg_type}]")
            return "\n".join(lines)

    def format_for_display_html(self, max_messages: int = 20) -> str:
        """Format conversation as HTML for display.
        
        Args:
            max_messages: Maximum number of recent messages to include
            
        Returns:
            HTML string
        """
        msgs = self._messages[-max_messages:]
        if not msgs:
            return "<p style='color:#999; text-align:center;'>Conversation is empty</p>"
        
        parts = [
            "<html><body style='margin:4px; font-family:Segoe UI,Microsoft YaHei,sans-serif; font-size:13px;'>"
        ]
        
        for m in msgs:
            content = (
                m.content.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\n", "<br>")
            )
            if m.msg_type != "text":
                content = f"[{m.msg_type}]"
            
            if m.sender == "self":
                parts.append(
                    "<table width='100%' cellpadding='0' cellspacing='0'><tr>"
                    "<td width='25%'></td><td align='right'><div style='margin:3px 0;'>"
                    "<span style='font-size:11px; color:#888;'>Me</span><br>"
                    f"<span style='background-color:#95EC69; color:#000; padding:6px 10px; border-radius:6px;'>{content}</span>"
                    "</div></td></tr></table>"
                )
            else:
                parts.append(
                    "<table width='100%' cellpadding='0' cellspacing='0'><tr>"
                    "<td align='left'><div style='margin:3px 0;'>"
                    f"<span style='font-size:11px; color:#888;'>{self._contact_name}</span><br>"
                    f"<span style='background-color:#FFFFFF; color:#000; padding:6px 10px; border-radius:6px; border:1px solid #E0E0E0;'>{content}</span>"
                    "</div></td><td width='25%'></td></tr></table>"
                )
        
        parts.append("</body></html>")
        return "".join(parts)

    def get_last_other_message(self) -> str | None:
        """Get the most recent message from other party.
        
        Returns:
            Message content or None
        """
        for m in reversed(self._messages):
            if m.sender == "other":
                return m.content
        return None

    def get_last_self_message(self) -> str | None:
        """Get the most recent message from self.
        
        Returns:
            Message content or None
        """
        for m in reversed(self._messages):
            if m.sender == "self":
                return m.content
        return None

    def is_last_message_from_self(self) -> bool:
        """Check if the last message was from self.
        
        Returns:
            True if last message is from self
        """
        return bool(self._messages) and self._messages[-1].sender == "self"

    def clear(self) -> None:
        """Clear all messages."""
        self._messages.clear()

    def __len__(self) -> int:
        return len(self._messages)
