"""Abstract base class for LLM clients."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterator


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients.
    
    All LLM backend implementations must inherit from this class
    and implement the required methods.
    
    Example implementation:
        class MyLLMClient(BaseLLMClient):
            def chat(self, messages, temperature=None):
                # Implementation
                pass
            
            def chat_stream(self, messages, temperature=None):
                # Implementation
                yield token
    """

    @property
    @abstractmethod
    def model(self) -> str:
        """Get current model name."""
        pass

    @model.setter
    @abstractmethod
    def model(self, value: str) -> None:
        """Set current model name."""
        pass

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        """Send chat completion request and get response.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            temperature: Optional temperature parameter (0.0-2.0)
            
        Returns:
            Assistant response text
        """
        pass

    @abstractmethod
    def chat_stream(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> Iterator[str]:
        """Send chat completion request and stream response tokens.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            temperature: Optional temperature parameter (0.0-2.0)
            
        Yields:
            Response tokens as they are generated
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the LLM backend is available and responding.
        
        Returns:
            True if backend is reachable
        """
        pass

    @abstractmethod
    def list_models(self) -> list[str]:
        """List available models from the backend.
        
        Returns:
            List of model names
        """
        pass

    def validate_messages(self, messages: list[dict[str, str]]) -> None:
        """Validate message format.
        
        Args:
            messages: Messages to validate
            
        Raises:
            ValueError: If messages are invalid
        """
        if not messages:
            raise ValueError("Messages list cannot be empty")
        for msg in messages:
            if "role" not in msg or "content" not in msg:
                raise ValueError("Each message must have 'role' and 'content' keys")
            if msg["role"] not in ("system", "user", "assistant"):
                raise ValueError(f"Invalid role: {msg['role']}")
