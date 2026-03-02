"""OpenAI-compatible LLM client implementation."""

from __future__ import annotations

import logging
import os
from typing import Any, Iterator

from .base import BaseLLMClient

logger = logging.getLogger(__name__)


class OpenAIClient(BaseLLMClient):
    """OpenAI-compatible API client.
    
    Supports OpenAI, Azure OpenAI, LocalAI, LM Studio, vLLM, and other
    OpenAI-compatible APIs.
    
    Example:
        client = OpenAIClient(
            api_key="sk-...",
            model="gpt-4",
        )
        response = client.chat([{"role": "user", "content": "Hello!"}])
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = "gpt-3.5-turbo",
        organization: str | None = None,
    ):
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._base_url = base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self._model = model
        self._organization = organization or os.environ.get("OPENAI_ORG_ID")
        self._client = None
        self._init_client()

    def _init_client(self):
        """Initialize OpenAI client if available."""
        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                organization=self._organization,
            )
        except ImportError:
            logger.warning("openai package not installed. Install with: pip install openai")

    @property
    def model(self) -> str:
        """Get current model name."""
        return self._model

    @model.setter
    def model(self, value: str) -> None:
        """Set current model name."""
        self._model = value

    @property
    def base_url(self) -> str:
        """Get base URL."""
        return self._base_url

    def list_models(self) -> list[str]:
        """List available models.
        
        Returns:
            List of model names
        """
        if not self._client:
            return []
        try:
            models = self._client.models.list()
            return [m.id for m in models.data]
        except Exception as e:
            logger.warning(f"Failed to list models: {e}")
            return []

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
            raise RuntimeError("OpenAI client not initialized. Install: pip install openai")
        
        self.validate_messages(messages)
        
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        
        response = self._client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

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
            raise RuntimeError("OpenAI client not initialized. Install: pip install openai")
        
        self.validate_messages(messages)
        
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": True,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        
        stream = self._client.chat.completions.create(**kwargs)
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def is_available(self) -> bool:
        """Check if API is available.
        
        Returns:
            True if API is responding
        """
        if not self._client:
            return False
        try:
            self._client.models.list()
            return True
        except Exception:
            return False
