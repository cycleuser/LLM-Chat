"""
Liao (聊) - Vision-based GUI interaction assistant with LLM integration.

A Python package for automating desktop chat applications using vision/OCR
capabilities and LLM-powered understanding.

Example usage:
    from liao import VisionAgent, LLMClientFactory
    from liao.core import WindowManager

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

__version__ = "0.1.5"

from .api import VisionAgent, ToolResult, list_windows, run_automation
from .llm.factory import LLMClientFactory

__all__ = [
    "__version__",
    "VisionAgent",
    "LLMClientFactory",
    "ToolResult",
    "list_windows",
    "run_automation",
]
