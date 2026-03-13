"""Conversation memory management."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from ..models.message import ChatMessage

if TYPE_CHECKING:
    pass


def _get_conversations_dir() -> Path:
    """Get the conversations directory, creating it if needed."""
    home = Path.home()
    conv_dir = home / ".liao" / "conversations"
    conv_dir.mkdir(parents=True, exist_ok=True)
    return conv_dir


class ConversationMemory:
    """Structured conversation memory with sender attribution.

    Maintains a history of chat messages with proper sender tracking
    and formatting utilities for LLM consumption and display.
    Supports persistence to markdown files.

    Example:
        memory = ConversationMemory(contact_name="Alice")
        memory.add_other_message("Hello!")
        memory.add_self_message("Hi there!")

        # Format for LLM
        context = memory.format_for_llm()

        # Save to file
        memory.save_to_file()
    """

    def __init__(self, contact_name: str = "Other", session_id: str | None = None):
        self._contact_name = contact_name
        self._messages: list[ChatMessage] = []
        self._session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self._file_path: Path | None = None
        self._sent_messages: set[str] = set()  # Track sent messages to avoid repeats

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

    @property
    def session_id(self) -> str:
        """Get session ID."""
        return self._session_id

    def add_self_message(self, content: str, msg_type: str = "text") -> None:
        """Add a message from self.

        Args:
            content: Message content
            msg_type: Message type (text, image, etc.)
        """
        self._messages.append(
            ChatMessage(
                sender="self",
                content=content,
                msg_type=msg_type,
            )
        )
        self._sent_messages.add(self._normalize_for_comparison(content))
        self._auto_save()

    def add_other_message(self, content: str, msg_type: str = "text") -> None:
        """Add a message from the other party.

        Args:
            content: Message content
            msg_type: Message type (text, image, etc.)
        """
        self._messages.append(
            ChatMessage(
                sender="other",
                content=content,
                msg_type=msg_type,
            )
        )
        self._auto_save()

    def _normalize_for_comparison(self, text: str) -> str:
        """Normalize text for similarity comparison."""
        # Remove punctuation, lowercase, remove extra spaces
        text = re.sub(r"[^\w\s]", "", text.lower())
        return " ".join(text.split())

    def is_duplicate_or_similar(self, content: str, threshold: float = 0.7) -> bool:
        """Check if content is too similar to previous self messages.

        Args:
            content: Message to check
            threshold: Similarity threshold (0-1)

        Returns:
            True if content is duplicate or too similar
        """
        normalized = self._normalize_for_comparison(content)

        # Exact match
        if normalized in self._sent_messages:
            return True

        # Check similarity with recent self messages (last 10)
        recent_self = [m.content for m in self._messages[-20:] if m.sender == "self"]
        for prev in recent_self:
            prev_norm = self._normalize_for_comparison(prev)
            # Simple similarity: check if one contains most of the other
            if len(normalized) > 0 and len(prev_norm) > 0:
                # Check overlap
                if normalized in prev_norm or prev_norm in normalized:
                    return True
                # Check word overlap
                words1 = set(normalized.split())
                words2 = set(prev_norm.split())
                if words1 and words2:
                    overlap = len(words1 & words2) / max(len(words1), len(words2))
                    if overlap >= threshold:
                        return True
        return False

    def get_recent_self_messages(self, n: int = 5) -> list[str]:
        """Get the n most recent self messages for context.

        Args:
            n: Number of messages to return

        Returns:
            List of message contents
        """
        return [m.content for m in self._messages if m.sender == "self"][-n:]

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
        self._sent_messages.clear()

    def __len__(self) -> int:
        return len(self._messages)

    def _get_file_path(self) -> Path:
        """Get the file path for this conversation."""
        if self._file_path is None:
            conv_dir = _get_conversations_dir()
            safe_name = re.sub(r"[^\w\-]", "_", self._contact_name)[:20]
            filename = f"{self._session_id}_{safe_name}.md"
            self._file_path = conv_dir / filename
        return self._file_path

    def _auto_save(self) -> None:
        """Auto-save after each message."""
        try:
            self.save_to_file()
        except Exception:
            pass  # Silent fail for auto-save

    def save_to_file(self) -> Path:
        """Save conversation to markdown file.

        Returns:
            Path to the saved file
        """
        path = self._get_file_path()

        lines = [
            f"# Conversation with {self._contact_name}",
            "",
            f"**Session**: {self._session_id}",
            f"**Started**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Messages**: {len(self._messages)}",
            "",
            "---",
            "",
        ]

        for m in self._messages:
            sender = "**Me**" if m.sender == "self" else f"**{self._contact_name}**"
            content = m.content.replace("\n", "\n> ")
            if m.msg_type != "text":
                content = f"[{m.msg_type}]"
            lines.append(f"{sender}:")
            lines.append(f"> {content}")
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def load_from_file(self, path: Path | str) -> bool:
        """Load conversation from markdown file.

        Args:
            path: Path to the markdown file

        Returns:
            True if loaded successfully
        """
        path = Path(path)
        if not path.exists():
            return False

        try:
            content = path.read_text(encoding="utf-8")
            self._messages.clear()
            self._sent_messages.clear()

            # Parse markdown format
            current_sender = None
            current_content = []

            for line in content.split("\n"):
                if line.startswith("**Me**:"):
                    if current_sender and current_content:
                        msg = "\n".join(current_content).strip()
                        if current_sender == "self":
                            self._messages.append(ChatMessage(sender="self", content=msg))
                            self._sent_messages.add(self._normalize_for_comparison(msg))
                        else:
                            self._messages.append(ChatMessage(sender="other", content=msg))
                    current_sender = "self"
                    current_content = []
                elif line.startswith("**") and line.endswith("**:"):
                    if current_sender and current_content:
                        msg = "\n".join(current_content).strip()
                        if current_sender == "self":
                            self._messages.append(ChatMessage(sender="self", content=msg))
                            self._sent_messages.add(self._normalize_for_comparison(msg))
                        else:
                            self._messages.append(ChatMessage(sender="other", content=msg))
                    current_sender = "other"
                    current_content = []
                elif line.startswith("> ") and current_sender:
                    current_content.append(line[2:])

            # Handle last message
            if current_sender and current_content:
                msg = "\n".join(current_content).strip()
                if current_sender == "self":
                    self._messages.append(ChatMessage(sender="self", content=msg))
                    self._sent_messages.add(self._normalize_for_comparison(msg))
                else:
                    self._messages.append(ChatMessage(sender="other", content=msg))

            self._file_path = path
            return True
        except Exception:
            return False

    @staticmethod
    def list_saved_conversations() -> list[Path]:
        """List all saved conversation files.

        Returns:
            List of conversation file paths, newest first
        """
        conv_dir = _get_conversations_dir()
        files = list(conv_dir.glob("*.md"))
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return files
