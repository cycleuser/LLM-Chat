"""Tests for core modules."""

import pytest
from llm_chat.models.window import WindowInfo
from llm_chat.models.message import ChatMessage
from llm_chat.models.detection import AreaDetectionResult


class TestWindowInfo:
    """Tests for WindowInfo model."""

    def test_properties(self, sample_window_info):
        """Test WindowInfo properties."""
        w = sample_window_info
        assert w.width == 700
        assert w.height == 500
        assert w.center == (450, 350)
        assert w.left == 100
        assert w.top == 100
        assert w.right == 800
        assert w.bottom == 600

    def test_str_representation(self, sample_window_info):
        """Test string representation."""
        s = str(sample_window_info)
        assert "Test Window" in s
        assert "700x500" in s


class TestChatMessage:
    """Tests for ChatMessage model."""

    def test_self_message(self):
        """Test self message properties."""
        msg = ChatMessage(sender="self", content="Hello")
        assert msg.is_self is True
        assert msg.is_other is False
        assert msg.is_text is True

    def test_other_message(self):
        """Test other message properties."""
        msg = ChatMessage(sender="other", content="Hi")
        assert msg.is_self is False
        assert msg.is_other is True

    def test_non_text_message(self):
        """Test non-text message."""
        msg = ChatMessage(sender="other", content="", msg_type="image")
        assert msg.is_text is False

    def test_str_representation(self):
        """Test string representation."""
        msg = ChatMessage(sender="self", content="Hello world!")
        s = str(msg)
        assert "[Me]" in s
        assert "Hello world!" in s


class TestAreaDetectionResult:
    """Tests for AreaDetectionResult model."""

    def test_properties(self, sample_area_result):
        """Test AreaDetectionResult properties."""
        a = sample_area_result
        assert a.chat_width == 500
        assert a.chat_height == 300
        assert a.chat_center == (450, 250)
        assert a.input_width == 500
        assert a.input_height == 80
        assert a.input_center == (450, 460)

    def test_str_representation(self, sample_area_result):
        """Test string representation."""
        s = str(sample_area_result)
        assert "heuristic" in s
        assert "50%" in s
