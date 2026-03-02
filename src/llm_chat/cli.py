"""Command-line interface for llm-chat."""

from __future__ import annotations

import argparse
import ctypes
import logging
import sys

from ._version import __version__


def setup_dpi_awareness() -> None:
    """Set DPI awareness for Windows."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def run_gui(args: argparse.Namespace) -> int:
    """Run the GUI application."""
    from PySide6.QtWidgets import QApplication
    from .gui.main_window import MainWindow
    from .gui.i18n import set_locale
    
    setup_dpi_awareness()
    
    # Set locale if specified
    if args.lang:
        set_locale(args.lang)
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    
    return app.exec()


def list_windows(args: argparse.Namespace) -> int:
    """List available windows."""
    from .core.window_manager import WindowManager
    
    wm = WindowManager()
    windows = wm.get_all_visible_windows()
    
    if args.chat_only:
        windows = [w for w in windows if w.app_type != "other"]
    
    if not windows:
        print("No windows found")
        return 0
    
    print(f"Found {len(windows)} windows:\n")
    for w in windows:
        tag = f"[{w.app_type}]" if w.app_type != "other" else ""
        print(f"  {w.hwnd:10} {tag:12} {w.title}")
    
    return 0


def run_auto(args: argparse.Namespace) -> int:
    """Run headless automation."""
    from .core.window_manager import WindowManager
    from .core.screenshot import ScreenshotReader
    from .llm.factory import LLMClientFactory
    from .agent.workflow import AgentWorkflow
    
    # Find window
    wm = WindowManager()
    
    if args.hwnd:
        window = wm.get_window_by_hwnd(args.hwnd)
    elif args.title:
        window = wm.find_window_by_title(args.title)
    else:
        print("Error: Specify --hwnd or --title")
        return 1
    
    if not window:
        print("Error: Window not found")
        return 1
    
    print(f"Target: {window.title}")
    
    # Create LLM client
    try:
        client = LLMClientFactory.create_client(
            provider=args.provider,
            base_url=args.url,
            model=args.model,
        )
        if not client.is_available():
            print(f"Error: LLM backend not available ({args.provider})")
            return 1
    except Exception as e:
        print(f"Error creating LLM client: {e}")
        return 1
    
    print(f"LLM: {args.provider} / {args.model}")
    
    # Create and run workflow
    reader = ScreenshotReader()
    workflow = AgentWorkflow(
        llm_client=client,
        window_manager=wm,
        screenshot_reader=reader,
        window_info=window,
        prompt=args.prompt,
        rounds=args.rounds,
        max_wait_seconds=args.max_wait,
        poll_interval=args.poll_interval,
    )
    
    workflow.on_status = lambda m: print(f"[Status] {m}")
    workflow.on_message_generated = lambda m: print(f"[Generated] {m}")
    workflow.on_message_sent = lambda m: print(f"[Sent] {m}")
    workflow.on_reply_detected = lambda r: print(f"[Reply] {r}")
    workflow.on_error = lambda e: print(f"[Error] {e}")
    workflow.on_round_complete = lambda n: print(f"--- Round {n} completed ---")
    
    print("\nStarting automation...\n")
    workflow.run()
    print("\nAutomation completed")
    
    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="llm-chat",
        description="Vision-based GUI interaction assistant with LLM integration",
    )
    parser.add_argument(
        "--version", "-V",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # GUI command (default)
    gui_parser = subparsers.add_parser("gui", help="Launch GUI application")
    gui_parser.add_argument(
        "--lang",
        choices=["en_US", "zh_CN"],
        help="UI language",
    )
    
    # List command
    list_parser = subparsers.add_parser("list", help="List available windows")
    list_parser.add_argument(
        "--chat-only",
        action="store_true",
        help="Show only chat applications",
    )
    
    # Auto command (headless)
    auto_parser = subparsers.add_parser("auto", help="Run headless automation")
    auto_parser.add_argument(
        "--hwnd",
        type=int,
        help="Target window handle",
    )
    auto_parser.add_argument(
        "--title",
        help="Target window title (partial match)",
    )
    auto_parser.add_argument(
        "--provider",
        default="ollama",
        choices=["ollama", "openai", "anthropic"],
        help="LLM provider",
    )
    auto_parser.add_argument(
        "--url",
        default="http://localhost:11434",
        help="LLM API URL",
    )
    auto_parser.add_argument(
        "--model",
        default="",
        help="LLM model name",
    )
    auto_parser.add_argument(
        "--prompt",
        default="You are a friendly assistant. Respond naturally and briefly.",
        help="Conversation prompt",
    )
    auto_parser.add_argument(
        "--rounds",
        type=int,
        default=5,
        help="Number of conversation rounds",
    )
    auto_parser.add_argument(
        "--max-wait",
        type=float,
        default=60.0,
        help="Max seconds to wait for reply",
    )
    auto_parser.add_argument(
        "--poll-interval",
        type=float,
        default=3.0,
        help="Seconds between reply checks",
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    
    # Default to GUI if no command specified
    if args.command is None or args.command == "gui":
        if not hasattr(args, 'lang'):
            args.lang = None
        return run_gui(args)
    elif args.command == "list":
        return list_windows(args)
    elif args.command == "auto":
        return run_auto(args)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
