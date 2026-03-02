"""Test fixtures for llm-chat."""

import pytest


@pytest.fixture
def sample_window_info():
    """Create a sample WindowInfo for testing."""
    from llm_chat.models.window import WindowInfo
    return WindowInfo(
        hwnd=12345,
        title="Test Window",
        class_name="TestClass",
        rect=(100, 100, 800, 600),
        app_type="other",
    )


@pytest.fixture
def sample_chat_messages():
    """Create sample chat messages for testing."""
    from llm_chat.models.message import ChatMessage
    return [
        ChatMessage(sender="other", content="Hello!"),
        ChatMessage(sender="self", content="Hi there!"),
        ChatMessage(sender="other", content="How are you?"),
    ]


@pytest.fixture
def sample_area_result():
    """Create a sample AreaDetectionResult for testing."""
    from llm_chat.models.detection import AreaDetectionResult
    return AreaDetectionResult(
        chat_area_rect=(200, 100, 700, 400),
        input_area_rect=(200, 420, 700, 500),
        method="heuristic",
        confidence=0.5,
    )


@pytest.fixture
def conversation_memory():
    """Create a ConversationMemory for testing."""
    from llm_chat.agent.conversation import ConversationMemory
    memory = ConversationMemory(contact_name="Test User")
    memory.add_other_message("Hello!")
    memory.add_self_message("Hi there!")
    memory.add_other_message("How are you?")
    return memory
