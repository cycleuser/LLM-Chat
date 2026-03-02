"""Anthropic Claude LLM client implementation."""

from __future__ import annotations

import logging
import os
from typing import Any, Iterator

from .base import BaseLLMClient

logger = logging.getLogger(__name__)


class AnthropicClient(BaseLLMClient):
    """Anthropic Claude API client.
    
    Example:
        client = AnthropicClient(
            api_key="sk-ant-...",
            model="claude-3-sonnet-20240229",
        )
        response = client.chat([{"role": "user", "content": "Hello!"}])
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-3-sonnet-20240229",
        max_tokens: int = 4096,
    ):
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._model = model
        self._max_tokens = max_tokens
        self._client = None
        self._init_client()

    def _init_client(self):
        """Initialize Anthropic client if available."""
        try:
            from anthropic import Anthropic
            self._client = Anthropic(api_key=self._api_key)
        except ImportError:
            logger.warning("anthropic package not installed. Install with: pip install anthropic")

    @property
    def model(self) -> str:
        """Get current model name."""
        return self._model

    @model.setter
    def model(self, value: str) -> None:
        """Set current model name."""
        self._model = value

    def list_models(self) -> list[str]:
        """List available Claude models.
        
        Returns:
            List of model names (hardcoded since Anthropic doesn't have a list endpoint)
        """
        return [
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
            "claude-3-5-sonnet-20240620",
            "claude-2.1",
            "claude-2.0",
        ]

    def _prepare_messages(
        self,
        messages: list[dict[str, str]]
    ) -> tuple[str | None, list[dict[str, str]]]:
        """Prepare messages for Anthropic API.
        
        Extracts system message and converts format.
        
        Args:
            messages: Input messages
            
        Returns:
            Tuple of (system_prompt, messages)
        """
        system_prompt = None
        api_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                api_messages.append({
                    "role": msg["role"],
                    "content": msg["content"],
                })
        
        return system_prompt, api_messages

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        """Send chat completion request.
        
        Args:
            messages: Chat messages
            temperature: Optional temperature
            
        Returns:
            Assistant response text
        """
        if not self._client:
            raise RuntimeError("Anthropic client not initialized. Install: pip install anthropic")
        
        self.validate_messages(messages)
        system_prompt, api_messages = self._prepare_messages(messages)
        
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": api_messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if temperature is not None:
            kwargs["temperature"] = temperature
        
        response = self._client.messages.create(**kwargs)
        return response.content[0].text if response.content else ""

    def chat_stream(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> Iterator[str]:
        """Stream chat completion response.
        
        Args:
            messages: Chat messages
            temperature: Optional temperature
            
        Yields:
            Response tokens
        """
        if not self._client:
            raise RuntimeError("Anthropic client not initialized. Install: pip install anthropic")
        
        self.validate_messages(messages)
        system_prompt, api_messages = self._prepare_messages(messages)
        
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": api_messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if temperature is not None:
            kwargs["temperature"] = temperature
        
        with self._client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                yield text

    def is_available(self) -> bool:
        """Check if API is available.
        
        Returns:
            True if API key is set and client initialized
        """
        return self._client is not None and bool(self._api_key)
