"""Tests for LLM client modules."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from llm_chat.llm.factory import LLMClientFactory
from llm_chat.llm.ollama import OllamaClient


class TestLLMClientFactory:
    """Tests for LLMClientFactory."""

    def test_create_ollama_client(self):
        """Test creating Ollama client."""
        client = LLMClientFactory.create_client(
            provider="ollama",
            base_url="http://localhost:11434",
            model="test-model",
        )
        assert isinstance(client, OllamaClient)
        assert client.model == "test-model"

    def test_unknown_provider(self):
        """Test error on unknown provider."""
        with pytest.raises(ValueError, match="Unknown provider"):
            LLMClientFactory.create_client(provider="unknown")

    def test_get_available_providers(self):
        """Test listing providers."""
        providers = LLMClientFactory.get_available_providers()
        assert "ollama" in providers
        assert "openai" in providers
        assert "anthropic" in providers

    def test_is_provider_supported(self):
        """Test provider support check."""
        assert LLMClientFactory.is_provider_supported("ollama") is True
        assert LLMClientFactory.is_provider_supported("unknown") is False


class TestOllamaClient:
    """Tests for OllamaClient."""

    def test_model_property(self):
        """Test model property."""
        client = OllamaClient(model="llama3")
        assert client.model == "llama3"
        
        client.model = "mistral"
        assert client.model == "mistral"

    def test_base_url_property(self):
        """Test base_url property."""
        client = OllamaClient(base_url="http://localhost:11434")
        assert client.base_url == "http://localhost:11434"

    @patch("requests.Session.get")
    def test_is_available_true(self, mock_get):
        """Test is_available when server responds."""
        mock_get.return_value.status_code = 200
        client = OllamaClient()
        assert client.is_available() is True

    @patch("requests.Session.get")
    def test_is_available_false(self, mock_get):
        """Test is_available when server doesn't respond."""
        mock_get.side_effect = Exception("Connection error")
        client = OllamaClient()
        assert client.is_available() is False

    @patch("requests.Session.get")
    def test_list_models(self, mock_get):
        """Test listing models."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "models": [
                {"name": "llama3"},
                {"name": "mistral"},
            ]
        }
        
        client = OllamaClient()
        models = client.list_models()
        assert "llama3" in models
        assert "mistral" in models

    @patch("requests.Session.get")
    def test_get_chat_models(self, mock_get):
        """Test filtering chat models."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "models": [
                {"name": "llama3"},
                {"name": "nomic-embed-text"},
                {"name": "mistral"},
            ]
        }
        
        client = OllamaClient()
        chat_models = client.get_chat_models()
        assert "llama3" in chat_models
        assert "mistral" in chat_models
        assert "nomic-embed-text" not in chat_models

    def test_validate_messages(self):
        """Test message validation."""
        client = OllamaClient()
        
        # Valid messages
        client.validate_messages([
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
        ])
        
        # Empty messages
        with pytest.raises(ValueError, match="cannot be empty"):
            client.validate_messages([])
        
        # Missing keys
        with pytest.raises(ValueError, match="must have"):
            client.validate_messages([{"role": "user"}])
        
        # Invalid role
        with pytest.raises(ValueError, match="Invalid role"):
            client.validate_messages([{"role": "invalid", "content": "test"}])
