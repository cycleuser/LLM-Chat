"""
LLM Chat - Vision-based GUI interaction assistant with LLM integration.

A Python package for automating desktop chat applications using vision/OCR
capabilities and LLM-powered understanding.

Example usage:
    from llm_chat import VisionAgent, LLMClientFactory
    from llm_chat.core import WindowManager

    # Create LLM client
    llm = LLMClientFactory.create_client(
        provider="ollama",
        base_url="http://localhost:11434",
        model="llama3"
    )

    # Find target window
    wm = WindowManager()
    windows = wm.get_all_visible_windows()
    target = windows[0]

    # Create and run agent
    agent = VisionAgent(llm_client=llm, target_window=target)
    agent.run()
"""

from ._version import __version__
from .api import VisionAgent
from .llm.factory import LLMClientFactory

__all__ = [
    "__version__",
    "VisionAgent",
    "LLMClientFactory",
]
