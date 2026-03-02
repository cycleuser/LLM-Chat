# LLM Chat

Vision-based GUI interaction assistant with LLM integration.

A Python package for automating desktop chat applications using vision/OCR capabilities and LLM-powered understanding. Supports any OpenAI-compatible API (Ollama, OpenAI, etc.) and provides a bilingual GUI (English/Chinese).

## Features

- **Vision-based Automation**: Uses OCR to understand GUI elements and automate interactions
- **OpenAI-compatible API**: Supports Ollama (local), OpenAI, and any OpenAI-compatible API
- **Bilingual GUI**: English and Chinese interface with runtime language switching
- **Chat App Detection**: Auto-detects WeChat, QQ, Telegram, and other chat applications
- **Area Detection**: Automatic and manual chat/input area detection
- **Reply Gate**: Smart conversation flow that waits for replies before sending new messages
- **PyPI Ready**: Properly packaged for distribution via pip

## Installation

### From PyPI (when published)

```bash
pip install llm-chat
```

### With optional dependencies

```bash
# With OCR support (recommended)
pip install llm-chat[ocr]

# All optional dependencies
pip install llm-chat[all]
```

### From source

```bash
git clone https://github.com/cycleuser/llm-chat.git
cd llm-chat
pip install -e ".[all,dev]"
```

## Requirements

- Python 3.9+
- Windows (uses Win32 APIs)
- For OCR: EasyOCR, RapidOCR, or pytesseract
- For LLM: Ollama running locally, or any OpenAI-compatible API with API key

## Quick Start

### Launch GUI

```bash
llm-chat
# or
python -m llm_chat
```

### List available windows

```bash
llm-chat list
llm-chat list --chat-only
```

### Headless automation

```bash
llm-chat auto --title "WeChat" --model llama3 --rounds 5
```

### Programmatic usage

```python
from llm_chat import VisionAgent, LLMClientFactory
from llm_chat.core import WindowManager

# Create LLM client (Ollama local)
llm = LLMClientFactory.create_client(
    provider="ollama",
    base_url="http://localhost:11434",
    model="llama3"
)

# Or use OpenAI-compatible API with API key
llm = LLMClientFactory.create_client(
    provider="openai",
    base_url="https://api.openai.com/v1",
    api_key="your-api-key",
    model="gpt-4"
)

# Find target window
wm = WindowManager()
window = wm.find_window_by_title("WeChat")

# Create and run agent
agent = VisionAgent(
    llm_client=llm,
    target_window=window,
    prompt="Be friendly and helpful",
    max_rounds=10,
)

# Run automation
agent.run()
```

## GUI Usage

1. **Connect to LLM**: Enter URL (default: Ollama localhost:11434), optional API key, and click Connect
2. **Select Window**: Click Refresh, then double-click a window
3. **Setup Areas**: Click "Capture & Detect" or manually select areas
4. **Start Chat**: Enter prompt and click "Start Auto Chat"

## Running Screenshots

![Main Window (English)](images/main_window_en.png)

![Main Window (Chinese)](images/main_window_zh.png)

## Development

### Setup development environment

```bash
git clone https://github.com/cycleuser/llm-chat.git
cd llm-chat
pip install -e ".[all,dev]"
```

### Run tests

```bash
pytest tests/ -v
```

### Generate screenshots

```bash
python scripts/generate_screenshots.py
```

### Build and upload to PyPI

```bash
# Windows
publish.bat build    # Build only
publish.bat check    # Build and check
publish.bat test     # Upload to TestPyPI
publish.bat          # Upload to PyPI

# Linux/macOS
chmod +x publish.sh
./publish.sh build   # Build only
./publish.sh check   # Build and check
./publish.sh test    # Upload to TestPyPI
./publish.sh         # Upload to PyPI
```

**Prerequisites for PyPI upload:**
1. Create account on [PyPI](https://pypi.org) and/or [TestPyPI](https://test.pypi.org)
2. Generate API token from account settings
3. Set token as environment variable:
   - Windows: `set TWINE_PASSWORD=pypi-xxxx`
   - Linux/macOS: `export TWINE_PASSWORD=pypi-xxxx`
   - Or create `~/.pypirc` file with credentials

## Project Structure

```
llm-chat/
├── src/llm_chat/
│   ├── __init__.py
│   ├── _version.py          # Single version source
│   ├── api.py                # Public API (VisionAgent)
│   ├── cli.py                # CLI entry point
│   ├── core/                 # Core modules
│   ├── llm/                  # LLM clients
│   ├── agent/                # Agent workflow
│   ├── gui/                  # PySide6 GUI
│   └── models/               # Data models
├── tests/
├── scripts/
├── images/
├── pyproject.toml
└── README.md
```

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgments

- Uses [EasyOCR](https://github.com/JaidedAI/EasyOCR) for text recognition
- Built with [PySide6](https://doc.qt.io/qtforpython-6/) for the GUI
