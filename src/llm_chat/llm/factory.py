"""LLM client factory."""

from __future__ import annotations

from typing import Any

from .base import BaseLLMClient
from .ollama import OllamaClient
from .openai_client import OpenAIClient
from .anthropic_client import AnthropicClient


class LLMClientFactory:
    """Factory for creating LLM clients.
    
    Example:
        # Create Ollama client
        client = LLMClientFactory.create_client(
            provider="ollama",
            base_url="http://localhost:11434",
            model="llama3"
        )
        
        # Create OpenAI client
        client = LLMClientFactory.create_client(
            provider="openai",
            api_key="sk-...",
            model="gpt-4"
        )
        
        # Create Anthropic client
        client = LLMClientFactory.create_client(
            provider="anthropic",
            api_key="sk-ant-...",
            model="claude-3-sonnet-20240229"
        )
    """

    PROVIDERS = {
        "ollama": OllamaClient,
        "openai": OpenAIClient,
        "anthropic": AnthropicClient,
        # Aliases
        "azure": OpenAIClient,
        "lmstudio": OpenAIClient,
        "localai": OpenAIClient,
        "vllm": OpenAIClient,
        "claude": AnthropicClient,
    }

    @classmethod
    def create_client(cls, provider: str, **kwargs: Any) -> BaseLLMClient:
        """Create an LLM client instance.
        
        Args:
            provider: Provider name ("ollama", "openai", "anthropic", etc.)
            **kwargs: Provider-specific arguments
            
        Returns:
            BaseLLMClient instance
            
        Raises:
            ValueError: If provider is unknown
        """
        provider_lower = provider.lower()
        if provider_lower not in cls.PROVIDERS:
            available = ", ".join(sorted(set(cls.PROVIDERS.keys())))
            raise ValueError(f"Unknown provider: {provider}. Available: {available}")
        
        client_class = cls.PROVIDERS[provider_lower]
        return client_class(**kwargs)

    @classmethod
    def get_available_providers(cls) -> list[str]:
        """Get list of available provider names.
        
        Returns:
            List of unique provider names
        """
        return sorted(set(cls.PROVIDERS.keys()))

    @classmethod
    def is_provider_supported(cls, provider: str) -> bool:
        """Check if a provider is supported.
        
        Args:
            provider: Provider name
            
        Returns:
            True if provider is supported
        """
        return provider.lower() in cls.PROVIDERS
