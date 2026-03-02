"""Tests for agent modules."""

import pytest
from llm_chat.agent.conversation import ConversationMemory
from llm_chat.agent.prompts import PromptManager


class TestConversationMemory:
    """Tests for ConversationMemory."""

    def test_add_messages(self):
        """Test adding messages."""
        memory = ConversationMemory()
        memory.add_self_message("Hello")
        memory.add_other_message("Hi there")
        
        assert len(memory) == 2
        assert memory.messages[0].sender == "self"
        assert memory.messages[1].sender == "other"

    def test_get_last_messages(self, conversation_memory):
        """Test getting last messages."""
        assert conversation_memory.get_last_other_message() == "How are you?"
        assert conversation_memory.get_last_self_message() == "Hi there!"

    def test_is_last_message_from_self(self):
        """Test checking last message sender."""
        memory = ConversationMemory()
        memory.add_other_message("Hello")
        assert memory.is_last_message_from_self() is False
        
        memory.add_self_message("Hi")
        assert memory.is_last_message_from_self() is True

    def test_format_for_llm(self, conversation_memory):
        """Test LLM formatting."""
        text = conversation_memory.format_for_llm()
        assert "Other:" in text or "Me:" in text
        assert "Hello!" in text
        assert "How are you?" in text

    def test_format_for_display_html(self, conversation_memory):
        """Test HTML formatting."""
        html = conversation_memory.format_for_display_html()
        assert "<html>" in html
        assert "Hello!" in html
        assert "background-color" in html

    def test_clear(self, conversation_memory):
        """Test clearing messages."""
        assert len(conversation_memory) > 0
        conversation_memory.clear()
        assert len(conversation_memory) == 0

    def test_empty_memory(self):
        """Test empty memory edge cases."""
        memory = ConversationMemory()
        assert memory.get_last_other_message() is None
        assert memory.get_last_self_message() is None
        assert memory.is_last_message_from_self() is False
        assert "empty" in memory.format_for_llm().lower()


class TestPromptManager:
    """Tests for PromptManager."""

    def test_user_prompt_property(self):
        """Test user_prompt property."""
        pm = PromptManager(user_prompt="Be helpful")
        assert pm.user_prompt == "Be helpful"
        
        pm.user_prompt = "Be friendly"
        assert pm.user_prompt == "Be friendly"

    def test_get_system_prompt(self):
        """Test system prompt generation."""
        pm = PromptManager(user_prompt="Be helpful")
        prompt = pm.get_system_prompt()
        assert "Be helpful" in prompt
        assert "conversation" in prompt.lower()

    def test_get_first_message_prompt(self):
        """Test first message prompt."""
        pm = PromptManager(user_prompt="Talk about weather")
        prompt = pm.get_first_message_prompt()
        assert "Talk about weather" in prompt
        assert "first" in prompt.lower()

    def test_get_no_reply_prompt(self):
        """Test no-reply prompt."""
        pm = PromptManager()
        prompt = pm.get_no_reply_prompt(60)
        assert "60" in prompt
        assert "WAIT" in prompt

    def test_build_chat_context_first_message(self):
        """Test building context for first message."""
        pm = PromptManager(user_prompt="Be friendly")
        context = pm.build_chat_context(
            conversation_context="",
            is_first_message=True,
        )
        assert "first" in context.lower()

    def test_build_chat_context_with_reply(self):
        """Test building context with previous message."""
        pm = PromptManager()
        context = pm.build_chat_context(
            conversation_context="[Conversation]\nOther: Hello",
            last_other_message="Hello",
            is_first_message=False,
        )
        assert "Hello" in context
        assert "respond" in context.lower() or "reply" in context.lower()
