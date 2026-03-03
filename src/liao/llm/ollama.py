"""Ollama LLM client implementation."""

from __future__ import annotations

import json
import logging
from typing import Any, Iterator

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .base import BaseLLMClient

logger = logging.getLogger(__name__)


class OllamaClient(BaseLLMClient):
    """Ollama HTTP client for local LLM inference.
    
    Example:
        client = OllamaClient(base_url="http://localhost:11434", model="llama3")
        response = client.chat([{"role": "user", "content": "Hello!"}])
        print(response)
    """

    def __init__(self, base_url: str = "http://localhost:11434", model: str = ""):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._session = self._build_session()

    @staticmethod
    def _build_session() -> requests.Session:
        """Build HTTP session with retry logic."""
        session = requests.Session()
        retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[502, 503, 504])
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

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
        """List available models from Ollama.
        
        Returns:
            List of model names
        """
        try:
            resp = self._session.get(f"{self._base_url}/api/tags", timeout=10)
            resp.raise_for_status()
            models = resp.json().get("models", [])
            return [m.get("name", m.get("model", "")) for m in models]
        except Exception as e:
            logger.warning(f"Failed to list models: {e}")
            return []

    def get_chat_models(self) -> list[str]:
        """List models suitable for chat (excluding embedding models).
        
        Returns:
            List of chat model names, sorted alphabetically
        """
        embed_patterns = ("embed", "nomic", "bge", "e5-", "mxbai")
        models = [
            m for m in self.list_models()
            if not any(p in m.lower() for p in embed_patterns)
        ]
        return sorted(models, key=str.lower)

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
        self.validate_messages(messages)
        model = self._model or self._pick_default()
        
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        if temperature is not None:
            payload["options"] = {"temperature": temperature}
        
        resp = self._session.post(
            f"{self._base_url}/api/chat",
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]

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
        self.validate_messages(messages)
        model = self._model or self._pick_default()
        
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        if temperature is not None:
            payload["options"] = {"temperature": temperature}
        
        resp = self._session.post(
            f"{self._base_url}/api/chat",
            json=payload,
            stream=True,
            timeout=300,
        )
        resp.raise_for_status()
        
        for line in resp.iter_lines():
            if line:
                chunk = json.loads(line)
                token = chunk.get("message", {}).get("content", "")
                if token:
                    yield token

    def is_available(self) -> bool:
        """Check if Ollama is available.
        
        Returns:
            True if Ollama server is responding
        """
        try:
            resp = self._session.get(f"{self._base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def _pick_default(self) -> str:
        """Pick a default model if none specified."""
        chat_models = self.get_chat_models()
        # Prefer gemma3:1b if available
        if "gemma3:1b" in chat_models:
            return "gemma3:1b"
        if chat_models:
            return chat_models[0]
        all_models = self.list_models()
        if "gemma3:1b" in all_models:
            return "gemma3:1b"
        return all_models[0] if all_models else "llama3"
